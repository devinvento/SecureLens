from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.target import Target
from app.schemas.schemas import TargetCreate, TargetResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[TargetResponse])
def get_targets(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return db.query(Target).all()

@router.post("/", response_model=TargetResponse)
def create_target(target: TargetCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_target = Target(**target.dict())
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    return db_target
