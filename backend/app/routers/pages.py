from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/transcodes", response_class=HTMLResponse)
async def transcodes_page(request: Request):
    return templates.TemplateResponse("transcodes.html", {"request": request})


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


@router.get("/media/{item_id}", response_class=HTMLResponse)
async def media_detail_page(request: Request, item_id: int):
    return templates.TemplateResponse(
        "media_detail.html", {"request": request, "item_id": item_id}
    )


@router.get("/newsletter", response_class=HTMLResponse)
async def newsletter_page(request: Request):
    return templates.TemplateResponse("newsletter.html", {"request": request})
