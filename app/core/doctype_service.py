from typing import List, Dict, Any, Type
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Text, Float, MetaData, inspect
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from app.db.session import engine, Base
from app.models.doctype import DocType, DocField

class DocTypeService:
    @staticmethod
    def get_sqlalchemy_type(fieldtype: str):
        mapping = {
            "Data": String(255),
            "Int": Integer,
            "Float": Float,
            "Check": Boolean,
            "Text": Text,
            "Date": DateTime,
            "Datetime": DateTime,
            "Select": String(255)
        }
        return mapping.get(fieldtype, String(255))

    @classmethod
    def sync_table(cls, db: Session, doctype_id: int):
        doctype = db.query(DocType).filter(DocType.id == doctype_id).first()
        if not doctype:
            return

        table_name = doctype.table_name
        fields = doctype.fields
        
        inspector = inspect(engine)
        metadata = MetaData()
        metadata.reflect(bind=engine)

        columns = [
            Column("id", Integer, primary_key=True, autoincrement=True),
        ]

        for field in fields:
            col = Column(
                field.fieldname,
                cls.get_sqlalchemy_type(field.fieldtype),
                nullable=not field.reqd,
                unique=field.unique,
                index=field.search_index,
                default=field.default_value
            )
            columns.append(col)

        if not inspector.has_table(table_name):
            # Create table
            new_table = Table(table_name, metadata, *columns)
            new_table.create(bind=engine)
        else:
            # Alter table (Simplified: Only add missing columns)
            existing_columns = [c['name'] for c in inspector.get_columns(table_name)]
            for col in columns:
                if col.name not in existing_columns:
                    # Execute DDL to add column
                    column_type = str(col.type.compile(engine.dialect))
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    unique = "UNIQUE" if col.unique else ""
                    
                    # Basic DDL for adding column (PostgreSQL/SQLite compatible)
                    ddl = f'ALTER TABLE {table_name} ADD COLUMN {col.name} {column_type} {nullable} {unique}'
                    db.execute(text(ddl))
            db.commit()

    @classmethod
    def get_dynamic_model(cls, table_name: str):
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        if table_name in metadata.tables:
            table = metadata.tables[table_name]
            # Create a dynamic class that inherits from Base
            class DynamicModel(Base):
                __table__ = table
                
            return DynamicModel
        return None
