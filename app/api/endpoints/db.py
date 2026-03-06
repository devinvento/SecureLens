from fastapi import APIRouter, Request, HTTPException, Body, Depends
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from app.db.session import get_db, engine
from app.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/containers")
async def list_db_containers():
    """List available databases (System DB + any Docker containers detected)"""
    containers = [
        {'name': 'system_db', 'site': 'SecureLens (Internal)', 'type': 'postgres'}
    ]
    # Optionally we could still add other docker containers, 
    # but the user feedback suggests focusing on the "fixed" one.
    return {"success": True, "containers": containers}

@router.post("/tables")
async def list_db_tables(payload: dict = Body(...), db: Session = Depends(get_db)):
    """List tables in the database"""
    container = payload.get('container')
    
    if container == 'system_db':
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            return {"success": True, "tables": sorted(tables), "database": settings.DATABASE_URL.split('/')[-1]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    return {"success": False, "error": "External container support disabled. Use system_db."}

@router.post("/query")
async def execute_db_query(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Execute SQL query"""
    container = payload.get('container')
    query = payload.get('query')
    
    if not query:
        return {"success": False, "error": "Query required"}
    
    if container == 'system_db':
        try:
            # We use the provided DB session
            result = db.execute(text(query))
            
            # If it's a SELECT query, returning results
            if result.returns_rows:
                rows = result.fetchall()
                headers = list(result.keys())
                
                results = []
                for row in rows:
                    results.append(dict(zip(headers, row)))
                    
                return {"success": True, "results": results, "count": len(results)}
            else:
                db.commit()
                return {"success": True, "results": [], "count": result.rowcount, "message": "Query executed successfully"}
                
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "External container support disabled. Use system_db."}
