from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class DocFieldBase(BaseModel):
    label: str
    fieldname: str
    fieldtype: str
    options: Optional[str] = None
    reqd: bool = False
    unique: bool = False
    search_index: bool = False
    default_value: Optional[str] = None
    idx: int = 0

class DocFieldCreate(DocFieldBase):
    pass

class DocField(DocFieldBase):
    id: int
    parent_doctype_id: int

    class Config:
        orm_mode = True

class DocTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    table_name: str
    is_submittable: bool = False
    module: Optional[str] = None

class DocTypeCreate(DocTypeBase):
    fields: List[DocFieldCreate]

class DocType(DocTypeBase):
    id: int
    created_at: datetime
    modified_at: Optional[datetime]
    fields: List[DocField]

    class Config:
        orm_mode = True
