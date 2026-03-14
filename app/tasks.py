import re
import shlex
import base64
import requests
from bs4 import BeautifulSoup
from celery import shared_task
from app.core.helpers import check_http_protocol
from celery.exceptions import SoftTimeLimitExceeded
from app.db.session import SessionLocal
from app.models.scan import Scan
from app.models.target import Target
from app.models.vulnerability import Vulnerability
from app.models.tool_job import ToolJob
from app.models.package_todo import PackageTodo
import time, subprocess, redis, asyncio
from datetime import datetime
import random
import json
from app.core.config import settings

# Redis client for caching tool output and scan data
_redis = redis.from_url(settings.REDIS_URL)


async def generate_ghunt_session(oauth_token: str, creds_path: str) -> bool:
    """Generate GHunt session from OAuth token.
    
    This function creates the creds.m file needed by GHunt by:
    1. Exchanging the OAuth token for a master token
    2. Generating cookies and OSIDs
    3. Saving everything to the creds.m file
    """
    import httpx
    
    # GHunt's internal modules for auth
    import sys
    sys.path.insert(0, '/opt/ghunt')
    
    from ghunt.helpers import auth
    from ghunt.objects.base import GHuntCreds
    
    as_client = httpx.AsyncClient(follow_redirects=True)
    
    try:
        # Exchange OAuth token for master token
        master_token, services, owner_email, owner_name = await auth.android_master_auth(
            as_client, oauth_token
        )
        print(f"[+] Connected account: {owner_email}")
        
        # Create GHuntCreds object
        ghunt_creds = GHuntCreds(creds_path)
        ghunt_creds.android.master_token = master_token
        ghunt_creds.android.authorization_tokens = {}
        ghunt_creds.cookies = {"a": "a"}  # Dummy data
        ghunt_creds.osids = {"a": "a"}  # Dummy data
        
        # Generate cookies and osids
        print("[+] Generating cookies and osids...")
        await auth.gen_cookies_and_osids(as_client, ghunt_creds)
        
        # Save credentials
        ghunt_creds.save_creds()
        print(f"[+] Session saved to {creds_path}")
        
        await as_client.aclose()
        return True
        
    except Exception as e:
        print(f"[-] Error generating session: {e}")
        await as_client.aclose()
        return False


def setup_ghunt_session(ghunt_dir: str) -> bool:
    """Setup GHunt session from OAuth token in credentials file."""
    creds_file = "/app/ghunt_credentials.json"
    
    if not os.path.exists(creds_file):
        return False
    
    try:
        with open(creds_file, 'r') as f:
            creds_data = json.load(f)
        
        oauth_token = creds_data.get("oauth_token", "").strip()
        
        if not oauth_token or oauth_token == "YOUR_OAUTH_TOKEN_HERE":
            print("[-] No OAuth token found in ghunt_credentials.json")
            print("    Add 'oauth_token' field with your token (starts with 'oauth2_4/')")
            return False
        
        # Check if we already have a valid session
        creds_path = os.path.join(ghunt_dir, "creds.m")
        if os.path.exists(creds_path):
            # Try to load and validate existing session
            try:
                import base64
                import json
                with open(creds_path, 'r') as f:
                    data = json.loads(base64.b64decode(f.read()).decode())
                if data.get('android', {}).get('master_token'):
                    print("[+] Using existing GHunt session")
                    return True
            except:
                pass  # Invalid session, regenerate
        
        # Generate new session from OAuth token
        print("[+] Generating GHunt session from OAuth token...")
        return asyncio.run(generate_ghunt_session(oauth_token, creds_path))
        
    except Exception as e:
        print(f"[-] Error setting up GHunt session: {e}")
        return False

# Cache TTL settings (in seconds)
CACHE_TTL = {
    "scan_status": 300,      # 5 minutes
    "scan_data": 600,         # 10 minutes
    "vulnerability_list": 3600,  # 1 hour
}


def get_cached_scan(scan_id: int) -> dict | None:
    """Get scan data from Redis cache."""
    cache_key = f"scan:data:{scan_id}"
    cached = _redis.get(cache_key)
    if cached:
        return json.loads(cached)
    return None


def set_cached_scan(scan_id: int, data: dict, ttl: int = None):
    """Set scan data in Redis cache."""
    cache_key = f"scan:data:{scan_id}"
    _redis.setex(cache_key, ttl or CACHE_TTL["scan_data"], json.dumps(data))


def invalidate_scan_cache(scan_id: int):
    """Invalidate scan cache after completion."""
    cache_key = f"scan:data:{scan_id}"
    _redis.delete(cache_key)
    # Also invalidate status cache
    status_key = f"scan:status:{scan_id}"
    _redis.delete(status_key)


def get_scan_status_from_cache(scan_id: int) -> str | None:
    """Get scan status from Redis cache (fast lookup for API endpoints)."""
    status_key = f"scan:status:{scan_id}"
    status = _redis.get(status_key)
    return status.decode('utf-8') if status else None


def get_scan_vuln_count(scan_id: int) -> int | None:
    """Get vulnerability count from cache."""
    count_key = f"scan:vuln_count:{scan_id}"
    count = _redis.get(count_key)
    return int(count) if count else None


def sanitize_input(value: str) -> str:
    """Sanitize input to prevent command injection."""
    if not value:
        return ""
    # Only allow safe characters: alphanumeric, dots, hyphens, underscores, colons, slashes, spaces, commas, http
    sanitized = re.sub(r'[^a-zA-Z0-9.\-_:/ ,]', '', value)
    return sanitized


def validate_target(target: str) -> bool:
    """Validate that target is a valid domain or IP address."""
    if not target:
        return False
    # Allow domains, IPs, and URLs with http/https prefix
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    url_pattern = r'^https?://'
    
    return bool(
        re.match(domain_pattern, target) or
        re.match(ip_pattern, target) or
        re.match(url_pattern, target)
    )


@shared_task(name="app.tasks.run_scan_task")
def run_scan_task(scan_id: int):
    db = SessionLocal()
    
    # Try to get from cache first
    cached_scan = get_cached_scan(scan_id)
    if cached_scan:
        # If scan is already completed or running, don't reprocess
        if cached_scan.get("status") in ["completed", "running"]:
            db.close()
            return f"Scan {scan_id} already {cached_scan.get('status')}"
    
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        db.close()
        return "Scan not found"
    
    # Cache the scan data
    scan_data = {
        "id": scan.id,
        "target_id": scan.target_id,
        "status": "running",
        "created_at": scan.created_at.isoformat() if scan.created_at else None
    }
    set_cached_scan(scan_id, scan_data)
    
    # Update status in cache for quick polling
    _redis.setex(f"scan:status:{scan_id}", CACHE_TTL["scan_status"], "running")
    
    scan.status = "running"
    db.commit()

    # Simulate a web penetration testing scan against the target
    # In a real app we'd call Nmap, Nikto, OWASP ZAP, etc. here
    target_id = scan.target_id
    target_obj = db.query(Target).filter(Target.id == target_id).first()
    target_url = target_obj.url if target_obj else "localhost"
    
    # Sanitize target (extract hostname)
    host = re.sub(r'^https?://', '', target_url).split('/')[0].split(':')[0]
    
    try:
        # Run a basic Nmap scan for the main scanner
        # -F: Fast mode, -sV: Service version
        cmd = ["nmap", "-F", "-sV", host]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        scan_output = result.stdout + (result.stderr if result.stderr else "")
        
        # Simple parsing for mock vulnerabilities
        if "open" in scan_output.lower():
            severities = ["Low", "Medium", "High"]
            for i in range(random.randint(2, 5)):
                db.add(Vulnerability(
                    scan_id=scan.id,
                    title=f"Port Service Discovery {i+1}",
                    severity=random.choice(severities),
                    description=f"Potential service identified on {host}. Summary: {scan_output[:200]}..."
                ))
    except Exception as e:
        print(f"Scan error: {e}")

    # Generate mock vulnerabilities based on target ID or just randomly
    vulns = []
    severities = ["Low", "Medium", "High", "Critical"]
    for i in range(random.randint(1, 4)):
        vulns.append(Vulnerability(
            scan_id=scan.id,
            title=f"Mock Vulnerability {i+1}",
            severity=random.choice(severities),
            description="This is a mock vulnerability found by the SecureLens Python Engine mock scanner."
        ))

    db.add_all(vulns)
    scan.status = "completed"
    scan.completed_at = datetime.utcnow()
    db.commit()
    
    # Invalidate cache after completion
    invalidate_scan_cache(scan_id)
    # Update status cache to completed
    _redis.setex(f"scan:status:{scan_id}", CACHE_TTL["scan_status"], "completed")
    
    # Cache vulnerability count for quick access
    _redis.setex(f"scan:vuln_count:{scan_id}", CACHE_TTL["vulnerability_list"], len(vulns))
    
    db.close()
    
    return f"Scan {scan_id} completed successfully"


def run_gospider_with_form_analysis(target: str, timeout: int = 300) -> str:
    """
    Run gospider to crawl a target and analyze forms for interesting parameters.
    
    This function:
    1. Runs gospider to crawl the target site
    2. Extracts forms from discovered URLs
    3. Identifies interesting parameters (cmd, exec, url, redirect, file, path, upload)
    4. Saves results to package_todo table
    
    Returns:
        str: Output message
    """
    import requests
    from bs4 import BeautifulSoup
    import subprocess
    import json
    from urllib.parse import urljoin
    
    output = ""
    interesting_params = ["cmd", "exec", "url", "redirect", "file", "path", "upload"]
    
    output += "[*] Crawling site using gospider...\n"
    
    # Run gospider to discover URLs
    result = subprocess.run(
        ["gospider", "-s", target, "-d", "2", "--quiet"],
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    urls = set()
    
    for line in result.stdout.splitlines():
        if line.startswith("http"):
            urls.add(line.strip())
    
    output += f"[+] Found {len(urls)} URLs\n"
    
    forms_data = []
    seen_forms = set()
    
    for url in urls:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")
            
            forms = soup.find_all("form")
            
            for form in forms:
                action = form.get("action")
                method = form.get("method", "GET").upper()
                
                if action:
                    action = urljoin(url, action)
                
                form_id = f"{action}-{method}"
                
                if form_id in seen_forms:
                    continue
                
                seen_forms.add(form_id)
                
                fields = []
                has_password = False
                has_file = False
                csrf_token = False
                interesting_fields = []
                
                for field in form.find_all(["input", "textarea", "select"]):
                    name = field.get("name")
                    ftype = field.get("type", "text")
                    
                    if ftype == "password":
                        has_password = True
                    
                    if ftype == "file":
                        has_file = True
                    
                    if name and "csrf" in name.lower():
                        csrf_token = True
                    
                    # Check for interesting parameters
                    if name:
                        name_lower = name.lower()
                        for interesting in interesting_params:
                            if interesting in name_lower:
                                interesting_fields.append({
                                    "name": name,
                                    "type": interesting,
                                    "match": interesting
                                })
                                break
                    
                    fields.append({
                        "name": name,
                        "type": ftype
                    })
                
                form_type = "normal"
                
                if has_password:
                    form_type = "login"
                
                if has_file:
                    form_type = "file_upload"
                
                forms_data.append({
                    "page": url,
                    "action": action,
                    "method": method,
                    "type": form_type,
                    "csrf_token": csrf_token,
                    "interesting_params": interesting_fields,
                    "fields": fields
                })
        
        except Exception as e:
            pass
    
    output += f"\n===== FORM ANALYSIS COMPLETE =====\n\n"
    
    # Store form data in package_todo table
    form_report_json = json.dumps(forms_data, indent=4)
    output += f"[+] Form analysis complete, found {len(forms_data)} forms\n"
    
    # Create PackageTodo entry
    db = SessionLocal()
    try:
        package_todo = PackageTodo(
            target=target,
            package_name="gospider",
            section="web-fuzzing",
            data=form_report_json,
            status="completed"
        )
        db.add(package_todo)
        db.commit()
        output += f"[+] Form data saved to package_todo (id: {package_todo.id})\n"
    except Exception as e:
        output += f"[-] Error saving to package_todo: {e}\n"
    finally:
        db.close()
    
    return output


# ---------------------------------------------------------------
# Tool command mappings
# ---------------------------------------------------------------

TOOL_COMMANDS = {
    "nmap":         ["nmap", "{args}", "{target}"],
    "subfinder":    ["subfinder", "-silent", "-d", "{target}"],
    "amass":          ["amass", "{mode}", "{args}", "{target_flag}", "{target}"],
    "assetfinder":  ["assetfinder", "--subs-only", "{target}"],
    "findomain":    ["findomain", "-t", "{target}", "-q"],
    "theHarvester": ["theHarvester", "-d", "{target}", "-b", "{sources}", "-f", "{target}.xml"],
    "sublist3r":    ["sublist3r", "-d", "{target}", "-o", "{target}_subdomains.txt"],
    "masscan":      ["masscan", "{args}", "-oL", "{target}_masscan.txt", "{target}"],
    "httpx":        ["httpx", "-l", "{target}", "-threads", "50", "-silent"],
    "nuclei":       ["nuclei", "-u", "{target}", "{args}"],
    "xff":          ["xff", "-u", "{target}", "-e"],
    "nikto":        ["nikto", "-h", "{target}"],
    "wpscan":       ["wpscan", "--url", "{target}", "--enumerate", "vp", "--batch"],
    "wafw00f":      ["wafw00f", "{target}"],
    "dig":          ["dig", "{target}"],
    "whois":        ["whois", "{target}"],
    "dnsenum":      ["dnsenum", "{target}"],
    "fierce":       ["fierce", "--domain", "{target}"],
    "cybersec":     ["cybersec", "-t", "{target}"],
    "recon-ng":     ["recon-ng", "-r", "/app/reconng_commands.txt"],
    "gobuster":     ["gobuster", "dir", "-u", "{target}", "-w", "/opt/SecLists/Discovery/Web-Content/common.txt", "-t", "30", "-b", "404,403", "--timeout", "10s","-r"],
    "dirb":         ["dirb", "{target}", "/opt/SecLists/Discovery/Web-Content/common.txt"],
    "ffuf":         ["ffuf", "-u", "{target}/FUZZ", "-w", "/opt/SecLists/Discovery/Web-Content/common.txt", "{args}"],
    "whatweb":      ["whatweb", "{args}", "-a", "3", "-v", "--color=never", "{target}"],
    "gospider":     ["gospider", "-s", "{target}", "-d", "2", "--quiet"],
    "feroxbuster":  ["feroxbuster", "-u", "{target}", "-w", "/opt/SecLists/Discovery/Web-Content/common.txt", "-k", "--silent"],
    "secretfinder": [
        "bash",
        "-c",
        "gau {target} 2>/dev/null | grep -Ei '\\.js(\\?|$)' | grep -Ev 'cdn-cgi|jquery|bootstrap|wp-includes' | sort -u | while read -r url; do code=$(curl -L -s -A 'Mozilla/5.0' -o /tmp/js.tmp -w '%{http_code}' \"$url\"); if [ \"$code\" = \"200\" ]; then echo \"[+] $url\"; python3 /opt/LinkFinder/linkfinder.py -i /tmp/js.tmp -o cli 2>/dev/null; python3 /opt/SecretFinder/SecretFinder.py -i /tmp/js.tmp -o cli 2>/dev/null; fi; done"
    ],
    "ghunt":        ["ghunt", "email", "{target}"],
    "pymeta":       ["pymeta", "-d", "{target}"],
    "mosint":       ["mosint", "-t", "{target}"],
    "osmedeus":     ["osmedeus", "scan", "-t", "{target}"],
}



@shared_task(name="app.tasks.run_tool_task", soft_time_limit=3600, time_limit=3700)
def run_tool_task(job_id: int):
    import os
    db = SessionLocal()
    try:
        job = db.query(ToolJob).filter(ToolJob.id == job_id).first()
        if not job:
            return "Job not found"

        # Validate and sanitize inputs before processing
        if not validate_target(job.target):
            job.output = "[ERROR] Invalid target format. Only domains, IP addresses, or URLs are allowed."
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            db.commit()
            return f"ToolJob {job_id} failed: Invalid target"

        # Special validation for nmap - only accept IP addresses
        if job.tool_name == "nmap":
            ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
            if not re.match(ip_pattern, job.target):
                job.output = "[ERROR] Nmap only accepts IP addresses. Please enter an IP address."
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                db.commit()
                return f"ToolJob {job_id} failed: Nmap requires IP address"

        # Sanitize target and args to prevent command injection
        safe_target = sanitize_input(job.target)
        safe_args = sanitize_input(job.args or "")

        # Special sanitization for theHarvester (requires domain only)
        if job.tool_name == "theHarvester":
            # Remove http:// or https://
            safe_target = re.sub(r'^https?://', '', safe_target)
            # Remove www.
            safe_target = re.sub(r'^www\.', '', safe_target)
            # Remove trailing slashes
            safe_target = safe_target.rstrip('/')
            # For theHarvester, also check if args contains domain info

        # Special handling for ffuf - check http/https and use working protocol
        if job.tool_name in ["ffuf", "whatweb", "secretfinder", "gospider"]:
            safe_target = check_http_protocol(safe_target)

        # Set timeout based on tool type (some tools need more time)
        tool_timeouts = {
            "theHarvester": 600,   # 10 minutes
            "amass": 900,          # 15 minutes
            "osmedeus": 1800,      # 30 minutes
            "nmap": 300,           # 5 minutes
            "ffuf": 20000,           # 5 minutes
            "finalrecon": 300,     # 5 minutes
            "secretfinder": 300,   # 5 minutes
            "pymeta": 300,         # 5 minutes
            "mosint": 300,         # 5 minutes
            "ghunt": 300,          # 5 minutes
            "whatweb": 300,        # 5 minutes
            "gobuster": 3000,      # 50 minutes
            "gospider": 600,       # 10 minutes
            "feroxbuster": 900,    # 15 minutes
        }
        timeout = tool_timeouts.get(job.tool_name, 300)

        job.status = "running"
        db.commit()

        # Record start time for execution tracking
        start_time = time.time()
        output = "" # Initialize output here

        try:
            # Handle SoftTimeLimitExceeded from Celery
            template = TOOL_COMMANDS.get(job.tool_name)
            if not template:
                raise ValueError(f"Unknown tool: {job.tool_name}")

            # Check if tool binary exists (only for /opt/tools/ and /usr/local/bin/ paths)
            for part in template:
                # Only check for actual binary tool paths, not wordlists/data directories
                if part.startswith(('/opt/tools/', '/usr/local/bin/')):
                    tool_path = part.split()[1] if ' ' in part else part
                    if not os.path.exists(tool_path):
                        job.output = f"[ERROR] Tool not found: {job.tool_name}. Please ensure the tool is installed."
                        job.status = "failed"
                        job.completed_at = datetime.utcnow()
                        db.commit()
                        return f"ToolJob {job_id} failed: Tool not found"

            # Build command with sanitized inputs
            safe_sources = sanitize_input(job.sources or "crtsh,rapiddns,duckduckgo,waybackarchive,subdomaincenter")
            safe_mode = sanitize_input(job.mode or "enum")  # Default to enum mode for amass
            safe_target_flag = sanitize_input(job.target_flag or "-d")  # Default to -d for enum
            
            # Default args for specific tools
            # safe_args is already defined above, this block was for specific defaults
            if job.tool_name == "masscan" and not safe_args:
                safe_args = "-p1-10000"  # Default ports for masscan
            
            cmd = []
            for part in template:
                if part == "{target}":
                    cmd.append(safe_target)
                elif part == "{args}":
                    if safe_args:
                        cmd.extend(shlex.split(safe_args))
                elif part == "{sources}":
                    cmd.append(safe_sources)
                elif part == "{mode}":
                    cmd.append(safe_mode)
                elif part == "{target_flag}":
                    cmd.append(safe_target_flag)
                else:
                    # Handle cases where placeholders are part of a string (less common in our current TOOL_COMMANDS but safer)
                    p = part.replace("{target}", safe_target).replace("{sources}", safe_sources).replace("{mode}", safe_mode).replace("{target_flag}", safe_target_flag)
                    if "{args}" in p:
                        if safe_args:
                             # This case is tricky if args are in middle of string, but our current tools don't do that
                             p = p.replace("{args}", safe_args)
                             cmd.extend(shlex.split(p))
                        else:
                             p = p.replace("{args}", "")
                             if p: cmd.append(p)
                    else:
                        cmd.append(p)

            # Show the command in output
            command_str = ' '.join(cmd)
            output = f"[COMMAND] {command_str}\n\n"

            # Setup specific tool environment before execution
            if job.tool_name == "ghunt" and os.path.exists("/app/ghunt_credentials.json"):
                import shutil
                for d in ["~/.ghunt", "~/.malfrats/ghunt"]:
                    ghunt_dir = os.path.expanduser(d)
                    os.makedirs(ghunt_dir, exist_ok=True)
                    # Copy OAuth credentials file
                    shutil.copy("/app/ghunt_credentials.json", os.path.join(ghunt_dir, "credentials.json"))
                    # Generate session from OAuth token if available
                    setup_ghunt_session(ghunt_dir)

            # Run gospider with form analysis
            if job.tool_name == "gospider":
                output += run_gospider_with_form_analysis(safe_target, timeout)
            else:
                # Security: Use shell=False to prevent shell injection
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,  # Dynamic timeout based on tool type
                    shell=False,  # SECURITY: Prevent shell injection
                )
                output += result.stdout or ""
                if result.stderr:
                    output += "\n--- STDERR ---\n" + result.stderr
            
            job.status = "completed" # Set status to completed if no exception occurred

        except SoftTimeLimitExceeded:
            output += "\n[ERROR] Task exceeded maximum execution time and was terminated."
            job.status = "failed"
        except subprocess.TimeoutExpired:
            output += f"\n[ERROR] Tool timed out after {timeout} seconds."
            job.status = "failed"
        except Exception as e:
            output += f"\n[ERROR] {str(e)}"
            job.status = "failed"
        
        # Strip ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Generate summary of output
        def generate_summary(output_text: str) -> str:
            if not output_text:
                return "No output"
            lines = output_text.strip().split('\n')
            # Take first 10 lines for summary
            summary_lines = lines[:10]
            summary = '\n'.join(summary_lines)
            if len(lines) > 10:
                summary += f"\n... and {len(lines) - 10} more lines"
            return summary

        job.output = output
        job.summary = generate_summary(output)
        job.execution_time = execution_time
        job.completed_at = datetime.utcnow()
        db.commit()

        # Cache result in Redis (TTL 1 hour)
        _redis.setex(f"tool:result:{job_id}", 3600, output)

        return f"ToolJob {job_id} finished with status: {job.status}"
    finally:
        db.close()


@shared_task(name="app.tasks.run_automation_task", soft_time_limit=15000, time_limit=16000)
def run_automation_task(master_job_id: int):
    """
    Orchestrator for the Web Fuzzing Automation Flow.
    Runs tools in sequence: WhatWeb -> Gospider -> (LinkFinder, SecretFinder) & (Feroxbuster -> ffuf -> PyMeta)
    """
    db = SessionLocal()
    try:
        master_job = db.query(ToolJob).filter(ToolJob.id == master_job_id).first()
        if not master_job:
            return "Master Job not found"

        target = master_job.target
        master_job.status = "running"
        master_job.output = f"[*] Starting Automation Flow for {target}\n"
        db.commit()

        steps = [
            {"name": "WhatWeb", "tool": "whatweb", "args": "-a 3 -v"},
            {"name": "Gospider", "tool": "gospider", "args": ""},
            {"name": "SecretFinder/LinkFinder", "tool": "secretfinder", "args": ""},
            {"name": "Feroxbuster", "tool": "feroxbuster", "args": ""},
            {"name": "ffuf (param fuzz)", "tool": "ffuf", "args": "-u https://TARGET/?FUZZ=value -w /opt/SecLists/Discovery/Web-Content/burp-parameter-names.txt -fc 404"},
            {"name": "PyMeta", "tool": "pymeta", "args": ""}
        ]

        total_steps = len(steps)
        start_time = time.time()

        for i, step in enumerate(steps):
            step_num = i + 1
            master_job.output += f"\n[+] Step {step_num}/{total_steps}: Initializing {step['name']}...\n"
            master_job.summary = f"Step {step_num}/{total_steps}: Running {step['name']}"
            db.commit()

            # Create a separate job for this tool so it shows up in the UI
            tool_args = step['args'].replace("TARGET", target)
            sub_job = ToolJob(
                tool_name=step['tool'],
                target=target,
                args=tool_args,
                status="pending"
            )
            db.add(sub_job)
            db.commit()
            db.refresh(sub_job)

            master_job.output += f"[*] Job #{sub_job.id} created for {step['name']}\n"
            db.commit()

            # Run the tool task synchronously (we are already in a worker)
            # We import and call it to avoid circular dependency or Celery overhead if possible,
            # but run_tool_task is already in this file.
            try:
                run_tool_task(sub_job.id)
                # Refresh from DB to get output
                db.refresh(sub_job)
                if sub_job.status == "completed":
                    master_job.output += f"[SUCCESS] {step['name']} completed.\n"
                else:
                    master_job.output += f"[WARNING] {step['name']} finished with status: {sub_job.status}\n"
            except Exception as e:
                master_job.output += f"[ERROR] Step {step['name']} failed: {str(e)}\n"

            db.commit()

        master_job.status = "completed"
        master_job.output += f"\n\n[DONE] Automation flow completed in {time.time() - start_time:.2f}s\n"
        master_job.summary = "Automation flow completed successfully"
        master_job.completed_at = datetime.utcnow()
        master_job.execution_time = time.time() - start_time
        db.commit()
    except Exception as e:
        if 'master_job' in locals() and master_job:
            master_job.status = "failed"
            master_job.output += f"\n[FATAL ERROR] Automation interrupted: {str(e)}\n"
            master_job.summary = f"Automation failed"
            master_job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
    return f"Automation {master_job_id} completed"
