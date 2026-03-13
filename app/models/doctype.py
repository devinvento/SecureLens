from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class DocType(Base):
    __tablename__ = "doctypes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    table_name = Column(String, unique=True, nullable=False)
    is_submittable = Column(Boolean, default=False)
    module = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    modified_at = Column(DateTime(timezone=True), onupdate=func.now())

    fields = relationship("DocField", back_populates="doctype", cascade="all, delete-orphan")

class DocField(Base):
    __tablename__ = "docfields"

    id = Column(Integer, primary_key=True, index=True)
    parent_doctype_id = Column(Integer, ForeignKey("doctypes.id"), nullable=False)
    label = Column(String, nullable=False)
    fieldname = Column(String, nullable=False)
    fieldtype = Column(String, nullable=False) # Data, Int, Float, Check, Text, Select, Date, Datetime
    options = Column(Text, nullable=True) # For Select or Link fields
    reqd = Column(Boolean, default=False)
    unique = Column(Boolean, default=False)
    search_index = Column(Boolean, default=False)
    default_value = Column(String, nullable=True)
    idx = Column(Integer, default=0)

    doctype = relationship("DocType", back_populates="fields")
