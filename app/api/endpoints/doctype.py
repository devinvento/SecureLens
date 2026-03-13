from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.doctype import DocType, DocField
from app.schemas.doctype import DocTypeCreate, DocType as DocTypeSchema
from app.core.doctype_service import DocTypeService

router = APIRouter()

@router.post("/", response_model=DocTypeSchema)
def create_doctype(doctype_in: DocTypeCreate, db: Session = Depends(get_db)):
    # Check if exists
    existing = db.query(DocType).filter(DocType.name == doctype_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="DocType already exists")
    
    # Create DocType
    db_doctype = DocType(
        name=doctype_in.name,
        description=doctype_in.description,
        table_name=doctype_in.table_name,
        is_submittable=doctype_in.is_submittable,
        module=doctype_in.module
    )
    db.add(db_doctype)
    db.flush() # Get ID

    # Create Fields
    for field_in in doctype_in.fields:
        db_field = DocField(
            parent_doctype_id=db_doctype.id,
            **field_in.dict()
        )
        db.add(db_field)
    
    db.commit()
    db.refresh(db_doctype)

    # Trigger Sync
    DocTypeService.sync_table(db, db_doctype.id)

    return db_doctype

@router.get("/", response_model=List[DocTypeSchema])
def list_doctypes(db: Session = Depends(get_db)):
    return db.query(DocType).all()

@router.get("/{name}", response_model=DocTypeSchema)
def get_doctype(name: str, db: Session = Depends(get_db)):
    doctype = db.query(DocType).filter(DocType.name == name).first()
    if not doctype:
        raise HTTPException(status_code=404, detail="DocType not found")
    return doctype
