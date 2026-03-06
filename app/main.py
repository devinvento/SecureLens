import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)

# Get the base directory (parent of app folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Setup Jinja2 templates - point to /app/templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.auto_reload = True

# Mount static files - serves both /static and root files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(api_router, prefix="/api")

# Serve dashboard.html from templates
@app.get("/dashboard.html", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Serve scans.html from templates
@app.get("/scans.html", response_class=HTMLResponse)
async def scans(request: Request):
    return templates.TemplateResponse("scans.html", {"request": request})

# Serve lab.html from templates
@app.get("/lab.html", response_class=HTMLResponse)
async def lab(request: Request):
    return templates.TemplateResponse("lab.html", {"request": request})

# Serve tools.html from templates
@app.get("/tools.html", response_class=HTMLResponse)
async def tools_page(request: Request):
    return templates.TemplateResponse("tools.html", {"request": request})

# Serve db_playground.html from templates
@app.get("/db_playground.html", response_class=HTMLResponse)
async def db_playground(request: Request):
    return templates.TemplateResponse("db_playground.html", {"request": request})



# Serve index.html from static folder (original format without extends)
@app.get("/index.html", response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(BASE_DIR, "static/index.html"))

# Root path - redirect to index.html
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static/index.html"))
