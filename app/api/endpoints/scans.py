from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.scan import Scan
from app.models.target import Target
from app.schemas.schemas import ScanCreate, ScanResponse
from app.tasks import run_scan_task
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[ScanResponse])
def get_scans(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(Scan).order_by(Scan.created_at.desc()).all()

@router.post("/launch", response_model=ScanResponse)
def launch_scan(scan_req: ScanCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    target = db.query(Target).filter(Target.id == scan_req.target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    scan = Scan(target_id=target.id, status="pending")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    
    # Trigger celery task
    run_scan_task.delay(scan.id)
    
    return scan
