from fastapi import FastAPI
from app.core.config import settings
from fastapi.staticfiles import StaticFiles
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix="/api")

app.mount("/", StaticFiles(directory="static", html=True), name="static")
