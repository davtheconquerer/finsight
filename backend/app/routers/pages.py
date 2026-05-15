from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import APP_VERSION, settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def render(name: str, request: Request, **extra):
    return templates.TemplateResponse(
        request, name, {**extra, "demo_mode": settings.demo_mode, "version": APP_VERSION}
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return render("dashboard.html", request)


@router.get("/transcodes", response_class=HTMLResponse)
async def transcodes_page(request: Request):
    return render("transcodes.html", request)


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return render("history.html", request)


@router.get("/media/{item_id}", response_class=HTMLResponse)
async def media_detail_page(request: Request, item_id: int):
    return render("media_detail.html", request, item_id=item_id)


@router.get("/newsletter", response_class=HTMLResponse)
async def newsletter_page(request: Request):
    return render("newsletter.html", request)


@router.get("/library", response_class=HTMLResponse)
async def library_page(request: Request):
    return render("janitor.html", request)


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    return render("user_stats.html", request)
