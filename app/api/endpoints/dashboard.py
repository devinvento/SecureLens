from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict
from app.db.session import get_db
from app.models.vulnerability import Vulnerability
from app.models.scan import Scan
from app.models.target import Target
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
def get_dashboard_metrics(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    total_vulns = db.query(Vulnerability).count()
    total_scans = db.query(Scan).count()
    total_targets = db.query(Target).count()

    # Vulnerabilities by severity
    severity_counts = db.query(Vulnerability.severity, func.count(Vulnerability.id)).group_by(Vulnerability.severity).all()
    vuln_by_severity = {s[0]: s[1] for s in severity_counts}

    # Top vulnerable hosts
    # Target join Scan join Vulnerability
    top_hosts_query = (
        db.query(Target.name, func.count(Vulnerability.id).label("count"))
        .join(Scan, Target.id == Scan.target_id)
        .join(Vulnerability, Scan.id == Vulnerability.scan_id)
        .group_by(Target.id)
        .order_by(func.count(Vulnerability.id).desc())
        .limit(5)
        .all()
    )
    top_hosts = [{"name": h[0], "vuln_count": h[1]} for h in top_hosts_query]

    return {
        "summary": {
            "total_vulnerabilities": total_vulns,
            "total_scans": total_scans,
            "total_targets": total_targets
        },
        "vulnerabilities_by_severity": vuln_by_severity,
        "top_hosts": top_hosts
    }
