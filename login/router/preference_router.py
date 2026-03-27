from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse

from templates import login_render
from login.utils.schemas import PreferenceRequest
from login.utils.storage import update_preferences
from login.utils.dependencies import get_current_user
from login.utils.ollama_utils import extract_categories_from_description
from config import ALL_CATEGORIES, CATEGORY_GROUPS

router = APIRouter()


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return login_render("preferences.html", {
        "category_groups": CATEGORY_GROUPS,
        "all_categories":  ALL_CATEGORIES,
    })


@router.get("/categories")
async def get_categories():
    return {"groups": CATEGORY_GROUPS, "all_categories": ALL_CATEGORIES}


@router.post("/extract-from-description")
async def extract_ai(body: dict, current_user: dict = Depends(get_current_user)):
    description = body.get("description", "").strip()
    if not description:
        raise HTTPException(400, "Description cannot be empty")
    keys = await extract_categories_from_description(description)
    return {
        "extracted_categories": keys,
        "category_names": {k: ALL_CATEGORIES[k] for k in keys if k in ALL_CATEGORIES},
        "count": len(keys),
    }


@router.post("/save")
async def save_preferences(body: PreferenceRequest, current_user: dict = Depends(get_current_user)):
    ai_extracted = []
    if body.use_ai_extraction and body.description:
        ai_extracted = await extract_categories_from_description(body.description)

    final_liked = list(set(body.liked_categories + ai_extracted))
    invalid = [k for k in final_liked if k not in ALL_CATEGORIES]
    if invalid:
        raise HTTPException(400, f"Invalid category keys: {invalid}")

    user = update_preferences(
        username=current_user["username"],
        liked_categories=final_liked,
        disliked_categories=body.disliked_categories,
        description=body.description or "",
        extracted_keywords=ai_extracted,
    )
    return {
        "message":          "Preferences saved",
        "liked_categories": user["preferences"]["liked_categories"],
        "ai_extracted":     ai_extracted,
        "preferences_set":  True,
    }


@router.get("/me")
async def my_preferences(current_user: dict = Depends(get_current_user)):
    p = current_user["preferences"]
    return {
        "liked_categories":    p["liked_categories"],
        "disliked_categories": p["disliked_categories"],
        "description":         p.get("description", ""),
        "extracted_keywords":  p.get("extracted_keywords", []),
        "preferences_set":     current_user["profile"].get("preferences_set", False),
    }
