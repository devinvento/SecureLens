from fastapi import APIRouter
from app.api.endpoints import auth, targets, scans, dashboard, tools, db

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(db.router, prefix="/db", tags=["db"])

