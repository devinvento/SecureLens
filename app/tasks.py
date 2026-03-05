import re
from celery import shared_task
from app.db.session import SessionLocal
from app.models.scan import Scan
from app.models.target import Target
from app.models.vulnerability import Vulnerability
from app.models.tool_job import ToolJob
import time, subprocess, redis
from datetime import datetime
import random
from app.core.config import settings

# Redis client for caching tool output
_redis = redis.from_url(settings.REDIS_URL)


def sanitize_input(value: str) -> str:
    """Sanitize input to prevent command injection."""
    if not value:
        return ""
    # Only allow safe characters: alphanumeric, dots, hyphens, underscores, colons, slashes, http
    sanitized = re.sub(r'[^a-zA-Z0-9.\-_:/]', '', value)
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
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        db.close()
        return "Scan not found"
    
    scan.status = "running"
    db.commit()

    # Simulate a web penetration testing scan against the target
    # In a real app we'd call Nmap, Nikto, OWASP ZAP, etc. here
    time.sleep(10)  # mock scan time

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
    db.close()
    
    return f"Scan {scan_id} completed successfully"


# ---------------------------------------------------------------
# Tool command mappings
# ---------------------------------------------------------------
TOOL_COMMANDS = {
    "nmap":           ["nmap", "{args}", "{target}"],
    "theHarvester":   ["theHarvester", "-d", "{target}", "-b", "all"],
    "finalrecon":     ["python3", "/opt/FinalRecon/finalrecon.py", "--url", "{target}"],
    "amass":          ["amass", "enum", "-d", "{target}"],
    "ffuf":           ["ffuf", "-u", "{target}/FUZZ", "-w", "/usr/share/seclists/Discovery/Web-Content/common.txt", "{args}"],
    "secretfinder":   ["python3", "/opt/SecretFinder/SecretFinder.py", "-i", "{target}", "-o", "cli"],
    "pymeta":         ["python3", "/opt/pymeta/pymeta.py", "-d", "{target}"],
    "mosint":         ["mosint", "{target}"],
    "ghunt":          ["python3", "/opt/GHunt/hunt.py", "email", "{target}"],
    "osmedeus":       ["osmedeus", "scan", "-t", "{target}"],
}


@shared_task(name="app.tasks.run_tool_task")
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

    # Sanitize target and args to prevent command injection
    safe_target = sanitize_input(job.target)
    safe_args = sanitize_input(job.args or "")

    job.status = "running"
    db.commit()

    try:
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
        cmd = []
        for part in template:
            part = part.replace("{target}", safe_target).replace("{args}", safe_args)
            # Remove empty placeholders
            if part and part != "{target}" and part != "{args}":
                cmd.append(part)

        # Security: Use shell=False to prevent shell injection
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute timeout
            shell=False,  # SECURITY: Prevent shell injection
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr

    except subprocess.TimeoutExpired:
        output = "[ERROR] Tool timed out after 5 minutes."
        job.status = "failed"
    except Exception as e:
        output = f"[ERROR] {str(e)}"
        job.status = "failed"
    else:
        job.status = "completed"

    job.output = output
    job.completed_at = datetime.utcnow()
    db.commit()
    db.close()

    # Cache result in Redis (TTL 1 hour)
    _redis.setex(f"tool:result:{job_id}", 3600, output)

    return f"ToolJob {job_id} finished with status: {job.status}"
