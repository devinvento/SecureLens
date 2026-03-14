import re
import socket
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, validator
from app.db.session import get_db
from app.models.tool_job import ToolJob
from app.models.package_todo import PackageTodo
from app.tasks import run_tool_task, validate_target
from app.api.deps import get_current_user
from app.core.config import settings
import redis
import ipaddress

router = APIRouter()
_redis = redis.from_url(settings.REDIS_URL)


# ── Schemas ──────────────────────────────────────────────────────
class ToolRunRequest(BaseModel):
    tool_name: str
    target: str
    args: Optional[str] = ""
    sources: Optional[str] = ""
    domain: Optional[str] = ""  # Original domain for tools like theHarvester
    mode: Optional[str] = ""  # For tools like amass that have different modes (enum, intel)
    target_flag: Optional[str] = ""  # For amass: -d for enum, -org for intel
    credentials: Optional[str] = ""  # For GHunt OAuth credentials

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
    sources: Optional[str]
    mode: Optional[str]
    target_flag: Optional[str]
    status: str
    output: Optional[str]
    summary: Optional[str]
    execution_time: Optional[float]
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
            sources=obj.sources,
            mode=obj.mode,
            target_flag=obj.target_flag,
            status=obj.status,
            output=obj.output,
            summary=obj.summary,
            execution_time=obj.execution_time,
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

    # For theHarvester, use domain if provided
    final_target = req.target
    if req.tool_name == "theHarvester" and req.domain:
        final_target = req.domain
    
    # Save GHunt credentials if provided
    if req.tool_name == "ghunt" and req.credentials:
        with open("/app/ghunt_credentials.json", "w") as f:
            f.write(req.credentials)
    
    job = ToolJob(tool_name=req.tool_name, target=final_target, args=req.args, sources=req.sources, mode=req.mode, target_flag=req.target_flag, status="pending")
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


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    job = db.query(ToolJob).filter(ToolJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    db.delete(job)
    db.commit()
    return {"status": "success", "message": f"Job {job_id} deleted."}


@router.get("/lookup/{domain:path}")
def lookup_domain(domain: str, current_user=Depends(get_current_user)):
    try:
        # Extract hostname if URL
        if "//" in domain:
            parsed = urlparse(domain)
            domain = parsed.hostname or domain.split('/')[0]

        # Remove paths
        domain = domain.split('/')[0]

        # Remove www.
        if domain.startswith("www."):
            domain = domain[4:]

        # Check if already IP
        try:
            ipaddress.ip_address(domain)
            return {"domain": domain, "ip": domain, "status": "success"}
        except ValueError:
            pass

        # Resolve domain
        ip = socket.gethostbyname(domain)

        return {"domain": domain, "ip": ip, "status": "success"}

    except Exception as e:
        return {"domain": domain, "ip": None, "status": "error", "message": str(e)}
