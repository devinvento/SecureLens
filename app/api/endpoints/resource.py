from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, update, delete
from app.db.session import get_db, engine
from app.models.doctype import DocType
from app.core.doctype_service import DocTypeService

router = APIRouter()

async def get_model_or_404(doctype_name: str, db: Session):
    doctype = db.query(DocType).filter(DocType.name == doctype_name).first()
    if not doctype:
        raise HTTPException(status_code=404, detail=f"DocType {doctype_name} not found")
    
    model = DocTypeService.get_dynamic_model(doctype.table_name)
    if not model:
        raise HTTPException(status_code=500, detail="Failed to load dynamic model")
    return model

@router.get("/{doctype_name}")
async def list_resource(doctype_name: str, db: Session = Depends(get_db)):
    model = await get_model_or_404(doctype_name, db)
    result = db.execute(select(model)).scalars().all()
    return result

@router.get("/{doctype_name}/{id}")
async def get_resource(doctype_name: str, id: int, db: Session = Depends(get_db)):
    model = await get_model_or_404(doctype_name, db)
    result = db.query(model).filter(model.id == id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Resource not found")
    return result

@router.post("/{doctype_name}")
async def create_resource(doctype_name: str, data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    model = await get_model_or_404(doctype_name, db)
    db_obj = model(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.put("/{doctype_name}/{id}")
async def update_resource(doctype_name: str, id: int, data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    model = await get_model_or_404(doctype_name, db)
    db_obj = db.query(model).filter(model.id == id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    for key, value in data.items():
        setattr(db_obj, key, value)
    
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.delete("/{doctype_name}/{id}")
async def delete_resource(doctype_name: str, id: int, db: Session = Depends(get_db)):
    model = await get_model_or_404(doctype_name, db)
    db_obj = db.query(model).filter(model.id == id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    db.delete(db_obj)
    db.commit()
    return {"message": "Deleted successfully"}
