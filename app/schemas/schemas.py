from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TargetBase(BaseModel):
    name: str
    url: str
    description: Optional[str] = None

class TargetCreate(TargetBase):
    pass

class TargetResponse(TargetBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class ScanBase(BaseModel):
    target_id: int

class ScanCreate(ScanBase):
    pass

class ScanResponse(ScanBase):
    id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class VulnerabilityResponse(BaseModel):
    id: int
    scan_id: int
    title: str
    severity: str
    description: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True
