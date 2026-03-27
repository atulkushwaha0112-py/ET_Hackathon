from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from templates import dashboard_render
from login.utils.dependencies import get_current_user
from login.utils.storage import toggle_bookmark
from news_reader import get_personalised_feed, get_category_feed, get_bookmarked_articles
from config import ALL_CATEGORIES, CATEGORY_GROUPS

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user: dict = Depends(get_current_user)):
    return dashboard_render("dashboard.html", {
        "user":            current_user,
        "all_categories":  ALL_CATEGORIES,
        "category_groups": CATEGORY_GROUPS,
    })


@router.get("/feed")
async def personalised_feed(
    limit: int = Query(default=60, ge=1, le=200),
    category: str = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    return get_personalised_feed(user=current_user, limit=limit, category_filter=category)


@router.get("/feed/category/{category_key}")
async def category_feed(
    category_key: str,
    limit: int = Query(default=30, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    if category_key not in ALL_CATEGORIES:
        raise HTTPException(404, f"Unknown category: {category_key}")
    articles = get_category_feed(category_key, limit=limit)
    return {
        "category_key":  category_key,
        "category_name": ALL_CATEGORIES[category_key],
        "articles":      articles,
        "count":         len(articles),
    }


@router.get("/feed/bookmarks")
async def bookmarks_feed(current_user: dict = Depends(get_current_user)):
    articles = get_bookmarked_articles(current_user)
    return {"articles": articles, "count": len(articles)}


@router.post("/bookmark/{news_id:path}")
async def bookmark(news_id: str, current_user: dict = Depends(get_current_user)):
    updated, added = toggle_bookmark(current_user, news_id)
    return {
        "news_id":         news_id,
        "bookmarked":      added,
        "total_bookmarks": len(updated.get("bookmarks", [])),
    }


@router.get("/categories")
async def list_categories(current_user: dict = Depends(get_current_user)):
    liked    = set(current_user["preferences"].get("liked_categories", []))
    disliked = set(current_user["preferences"].get("disliked_categories", []))
    return {
        "categories": [
            {"key": k, "name": n, "liked": k in liked, "disliked": k in disliked}
            for k, n in ALL_CATEGORIES.items()
        ],
        "groups": CATEGORY_GROUPS,
    }
