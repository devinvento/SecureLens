import re
import socket
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, validator
from app.db.session import get_db
from app.models.tool_job import ToolJob
from app.tasks import run_tool_task, validate_target
from app.api.deps import get_current_user
from app.core.config import settings
import redis

router = APIRouter()
_redis = redis.from_url(settings.REDIS_URL)


# ── Schemas ──────────────────────────────────────────────────────
class ToolRunRequest(BaseModel):
    tool_name: str
    target: str
    args: Optional[str] = ""

    @validator('target')
    def validate_target(cls, v):
        if not validate_target(v):
            raise ValueError('Invalid target format. Only domains, IP addresses, or URLs are allowed.')
        return v


class ToolJobResponse(BaseModel):
    id: int
    tool_name: str
    target: str
    args: Optional[str]
    status: str
    output: Optional[str]
    created_at: str
    completed_at: Optional[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            tool_name=obj.tool_name,
            target=obj.target,
            args=obj.args,
            status=obj.status,
            output=obj.output,
            created_at=str(obj.created_at),
            completed_at=str(obj.completed_at) if obj.completed_at else None,
        )


# ── Endpoints ─────────────────────────────────────────────────────
@router.get("/", response_model=List[ToolJobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    jobs = db.query(ToolJob).order_by(ToolJob.created_at.desc()).limit(50).all()
    return [ToolJobResponse.from_orm(j) for j in jobs]


@router.post("/run", response_model=ToolJobResponse)
def run_tool(
    req: ToolRunRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.tasks import TOOL_COMMANDS
    if req.tool_name not in TOOL_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {req.tool_name}")

    job = ToolJob(tool_name=req.tool_name, target=req.target, args=req.args, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    run_tool_task.delay(job.id)
    return ToolJobResponse.from_orm(job)


@router.get("/{job_id}", response_model=ToolJobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Try Redis cache first for output
    cached = _redis.get(f"tool:result:{job_id}")

    job = db.query(ToolJob).filter(ToolJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resp = ToolJobResponse.from_orm(job)
    if cached and not resp.output:
        resp.output = cached.decode()
    return resp


@router.get("/lookup/{domain:path}")
def lookup_domain(domain: str, current_user=Depends(get_current_user)):
    try:
        # If input looks like a URL (contains //), extract hostname
        if "//" in domain:
            parsed = urlparse(domain)
            domain = parsed.hostname or domain.split('/')[0]
        
        # Further sanitize if it still has paths after it
        domain = domain.split('/')[0]
        
        ip = socket.gethostbyname(domain)
        return {"domain": domain, "ip": ip, "status": "success"}
    except Exception as e:
        return {"domain": domain, "ip": None, "status": "error", "message": str(e)}
