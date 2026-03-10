import re
import shlex
import base64
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from app.db.session import SessionLocal
from app.models.scan import Scan
from app.models.target import Target
from app.models.vulnerability import Vulnerability
from app.models.tool_job import ToolJob
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


# ---------------------------------------------------------------
# Tool command mappings
# ---------------------------------------------------------------
TOOL_COMMANDS = {
    "nmap":           ["nmap", "{args}", "{target}"],
    "theHarvester":   ["theHarvester", "-d", "{target}", "-b", "{sources}"],
    "amass":          ["amass", "{mode}", "{args}", "{target_flag}", "{target}"],  # Mode: enum or intel
    "ffuf":           ["ffuf", "-u", "{target}/FUZZ", "-w", "/usr/share/seclists/Discovery/Web-Content/common.txt", "{args}"],
    "secretfinder":   ["python3", "/opt/SecretFinder/SecretFinder.py", "-i", "{target}", "-o", "cli"],
    "pymeta":         ["python3", "/opt/pymeta/pymeta.py", "-d", "{target}"],
    "mosint":         ["mosint", "{target}"],
    "ghunt":          ["python3", "/opt/ghunt/main.py", "email", "{target}"],
    "osmedeus":       ["osmedeus", "scan", "-t", "{target}"],
}


@shared_task(name="app.tasks.run_tool_task", soft_time_limit=600, time_limit=700)
def run_tool_task(job_id: int):
    import os
    db = SessionLocal()
    job = db.query(ToolJob).filter(ToolJob.id == job_id).first()
    if not job:
        db.close()
        return "Job not found"

    # Validate and sanitize inputs before processing
    if not validate_target(job.target):
        job.output = "[ERROR] Invalid target format. Only domains, IP addresses, or URLs are allowed."
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        db.commit()
        db.close()
        return f"ToolJob {job_id} failed: Invalid target"

    # Special validation for nmap - only accept IP addresses
    if job.tool_name == "nmap":
        ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if not re.match(ip_pattern, job.target):
            job.output = "[ERROR] Nmap only accepts IP addresses. Please enter an IP address."
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            db.commit()
            db.close()
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

    # Set timeout based on tool type (some tools need more time)
    tool_timeouts = {
        "theHarvester": 600,   # 10 minutes
        "amass": 900,          # 15 minutes
        "osmedeus": 1800,      # 30 minutes
        "nmap": 300,           # 5 minutes
        "ffuf": 300,           # 5 minutes
        "finalrecon": 300,     # 5 minutes
        "secretfinder": 300,   # 5 minutes
        "pymeta": 300,         # 5 minutes
        "mosint": 300,         # 5 minutes
        "ghunt": 300,          # 5 minutes
    }
    timeout = tool_timeouts.get(job.tool_name, 300)

    job.status = "running"
    db.commit()

    try:
        # Handle SoftTimeLimitExceeded from Celery
        template = TOOL_COMMANDS.get(job.tool_name)
        if not template:
            raise ValueError(f"Unknown tool: {job.tool_name}")

        # Check if tool path exists
        for part in template:
            if part.startswith('/opt/') or part.startswith('/usr/'):
                tool_path = part.split()[1] if ' ' in part else part
                if not os.path.exists(tool_path):
                    job.output = f"[ERROR] Tool not found: {job.tool_name}. Please ensure the tool is installed."
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    db.close()
                    return f"ToolJob {job_id} failed: Tool not found"

        # Build command with sanitized inputs
        safe_sources = sanitize_input(job.sources or "crtsh,rapiddns,duckduckgo,waybackarchive,subdomaincenter")
        safe_mode = sanitize_input(job.mode or "enum")  # Default to enum mode for amass
        safe_target_flag = sanitize_input(job.target_flag or "-d")  # Default to -d for enum
        
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

    except SoftTimeLimitExceeded:
        output = "[ERROR] Task exceeded maximum execution time and was terminated."
        job.status = "failed"
    except subprocess.TimeoutExpired:
        output = f"[ERROR] Tool timed out after {timeout} seconds."
        job.status = "failed"
    except Exception as e:
        output = f"[ERROR] {str(e)}"
        job.status = "failed"
    else:
        job.status = "completed"

    # Strip ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', output)

    job.output = output
    job.completed_at = datetime.utcnow()
    db.commit()
    db.close()

    # Cache result in Redis (TTL 1 hour)
    _redis.setex(f"tool:result:{job_id}", 3600, output)

    return f"ToolJob {job_id} finished with status: {job.status}"
