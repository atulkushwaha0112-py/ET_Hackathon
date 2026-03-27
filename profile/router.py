from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from templates import profile_render
from login.utils.dependencies import get_current_user
from config import ALL_CATEGORIES

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def profile_page(request: Request, current_user: dict = Depends(get_current_user)):
    return profile_render("profile.html", {"all_categories": ALL_CATEGORIES})
