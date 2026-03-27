"""
article_router.py
─────────────────
Endpoints for the article reading page:
  GET  /article/read?news_id=...             → HTML article page
  POST /article/summarise                    → Ollama summarisation
  POST /article/track                        → Track this news (uses published_time as unique ID)
"""
import httpx

from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from templates import dashboard_render
from login.utils.dependencies import get_current_user
from login.utils.storage import toggle_bookmark, load_user, save_user
from login.utils.ollama_utils import summarise_article, chat_with_context_ai
from login.utils.schemas import ChatContextRequest
from news_reader import find_article_by_id
from config import ALL_CATEGORIES

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────
class SummariseRequest(BaseModel):
    news_id: str
    title: str = ""
    long_desc: str = ""
    url: str = ""


class TrackRequest(BaseModel):
    news_id: str
    title: str = ""


# ── Article reading page ─────────────────────────────────────────────────────
@router.get("/read", response_class=HTMLResponse)
async def article_page(request: Request, current_user: dict = Depends(get_current_user)):
    """Serves the article reading HTML. The front-end fetches article data via JS."""
    return dashboard_render("article.html", {
        "all_categories": ALL_CATEGORIES,
    })


# ── Summarise endpoint ───────────────────────────────────────────────────────
@router.post("/summarise")
async def summarise_article_endpoint(body: SummariseRequest, current_user: dict = Depends(get_current_user)):
    article = find_article_by_id(body.news_id)
    if not article:
        content = body.long_desc
    else:
        content = article.get("long_desc") or article.get("short_desc") or body.long_desc

    return StreamingResponse(
        summarise_article(title=body.title, content=content, original_url=body.url),
        media_type="text/plain"
    )


# ── Track this news ──────────────────────────────────────────────────────────
@router.post("/track")
async def track_news(body: TrackRequest, current_user: dict = Depends(get_current_user)):
    """Add news_id (published_time based) to user's tracked_topics list."""
    user = load_user(current_user["username"])
    if not user:
        raise HTTPException(404, "User not found")

    tracked = user.get("tracked_topics", [])

    # Check if already tracked
    for t in tracked:
        if t.get("news_id") == body.news_id:
            return {"message": "Already tracked", "tracked": True, "news_id": body.news_id}

    tracked.append({
        "news_id": body.news_id,
        "title": body.title,
        "tracked_at": datetime.now(timezone.utc).isoformat(),
    })
    user["tracked_topics"] = tracked
    save_user(user)

    return {"message": "You are now tracking this topic."}


@router.post("/chat")
async def chat_with_article(
    body: ChatContextRequest,
    current_user: dict = Depends(get_current_user),
):
    if not body.messages:
        raise HTTPException(400, "Message history cannot be empty")
        
    return StreamingResponse(
        chat_with_context_ai(body.context_text, [m.model_dump() for m in body.messages]),
        media_type="text/plain"
    )
