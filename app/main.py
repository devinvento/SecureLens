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

# Serve tool pages from templates folder (organized by category)
@app.get("/tools/enumeration.html", response_class=HTMLResponse)
async def enumeration_page(request: Request):
    return templates.TemplateResponse("tools/enumeration.html", {"request": request})

# Serve scanning.html from templates
@app.get("/tools/scanning.html", response_class=HTMLResponse)
async def scanning_page(request: Request):
    return templates.TemplateResponse("tools/scanning.html", {"request": request})

# Serve information-gathering.html from templates
@app.get("/tools/information-gathering.html", response_class=HTMLResponse)
async def information_gathering_page(request: Request):
    return templates.TemplateResponse("tools/information-gathering.html", {"request": request})

# Serve web-fuzzing.html from templates
@app.get("/tools/web-fuzzing.html", response_class=HTMLResponse)
async def web_fuzzing_page(request: Request):
    return templates.TemplateResponse("tools/web-fuzzing.html", {"request": request})

# Serve vulnerability-assessment.html from templates
@app.get("/tools/vulnerability-assessment.html", response_class=HTMLResponse)
async def vulnerability_assessment_page(request: Request):
    return templates.TemplateResponse("tools/vulnerability-assessment.html", {"request": request})

# Serve ffuf.html from templates (if exists)
@app.get("/tools/ffuf.html", response_class=HTMLResponse)
async def ffuf_tool_page(request: Request):
    return templates.TemplateResponse("tools/ffuf.html", {"request": request})

# Serve db_playground.html from templates
@app.get("/db_playground.html", response_class=HTMLResponse)
async def db_playground(request: Request):
    return templates.TemplateResponse("db_playground.html", {"request": request})

@app.get("/profile.html", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

@app.get("/roles.html", response_class=HTMLResponse)
async def roles_page(request: Request):
    return templates.TemplateResponse("roles.html", {"request": request})

@app.get("/users.html", response_class=HTMLResponse)
async def users_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})

@app.get("/permissions.html", response_class=HTMLResponse)
async def permissions_page(request: Request):
    return templates.TemplateResponse("permissions.html", {"request": request})



# Serve index.html from static folder (original format without extends)
@app.get("/index.html", response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(BASE_DIR, "static/index.html"))

# Root path - redirect to index.html
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static/index.html"))
