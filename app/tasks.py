from celery import shared_task
from app.db.session import SessionLocal
from app.models.scan import Scan
from app.models.target import Target
from app.models.vulnerability import Vulnerability
import time
from datetime import datetime
import random

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
