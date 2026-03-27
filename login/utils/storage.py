from __future__ import annotations
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from config import USER_DATA_DIR, TRACKING_DIR


def _user_path(username: str) -> str:
    return os.path.join(USER_DATA_DIR, f"{username.lower()}.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_user(username: str) -> Optional[dict]:
    p = _user_path(username)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user(user: dict) -> None:
    with open(_user_path(user["username"]), "w", encoding="utf-8") as f:
        json.dump(user, f, indent=2, ensure_ascii=False)


def user_exists(username: str) -> bool:
    return os.path.exists(_user_path(username))


def email_exists(email: str) -> bool:
    for fname in os.listdir(USER_DATA_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(USER_DATA_DIR, fname), "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("email", "").lower() == email.lower():
                    return True
        except Exception:
            pass
    return False


def create_user(username: str, email: str, password_hash: str, name: str = "") -> dict:
    user = {
        "user_id":       f"user_{uuid.uuid4().hex[:8]}",
        "username":      username.lower(),
        "email":         email.lower(),
        "password_hash": password_hash,
        "profile": {
            "name":             name or username,
            "created_at":       _now(),
            "last_login":       _now(),
            "preferences_set":  False,
        },
        "preferences": {
            "liked_categories":    [],
            "disliked_categories": [],
            "description":         "",
            "extracted_keywords":  [],
            "language":            "en",
            "region":              "India",
        },
        "tracked_topics": [],
        "bookmarks":      [],
    }
    save_user(user)
    return user


def update_last_login(username: str) -> None:
    user = load_user(username)
    if user:
        user["profile"]["last_login"] = _now()
        save_user(user)


def update_preferences(
    username: str,
    liked_categories: list,
    disliked_categories: list,
    description: str,
    extracted_keywords: list,
) -> dict:
    user = load_user(username)
    if not user:
        raise ValueError(f"User '{username}' not found")
    user["preferences"]["liked_categories"]    = liked_categories
    user["preferences"]["disliked_categories"] = disliked_categories
    user["preferences"]["description"]         = description
    user["preferences"]["extracted_keywords"]  = extracted_keywords
    user["profile"]["preferences_set"]         = True
    save_user(user)
    return user


def _tracking_path(username: str, topic_id: str) -> str:
    safe = topic_id.replace("/", "_").replace(" ", "_")
    return os.path.join(TRACKING_DIR, f"{username.lower()}_{safe}.json")


def add_tracked_topic(username: str, topic_name: str, keywords: list,
                      expanded_topics: Optional[list] = None) -> dict:
    user = load_user(username)
    if not user:
        raise ValueError(f"User '{username}' not found")

    topic_id   = f"topic_{uuid.uuid4().hex[:8]}"
    created_at = _now()

    user["tracked_topics"].append({
        "topic_id":   topic_id,
        "topic_name": topic_name,
        "keywords":   keywords,
        "created_at": created_at,
        "is_active":  True,
    })
    save_user(user)

    tracking = {
        "user_id":  user["user_id"],
        "username": user["username"],
        "main_topic": {
            "topic_id":   topic_id,
            "topic_name": topic_name,
            "created_at": created_at,
        },
        "expanded_topics": expanded_topics or [],
        "keywords":        keywords,
        "tracked_news":    [],
        "stats": {
            "total_news_matched": 0,
            "last_updated":       created_at,
        },
    }
    with open(_tracking_path(username, topic_id), "w", encoding="utf-8") as f:
        json.dump(tracking, f, indent=2, ensure_ascii=False)

    return tracking


def toggle_bookmark(user: dict, news_id: str):
    bm = user.get("bookmarks", [])
    if news_id in bm:
        bm.remove(news_id)
        added = False
    else:
        bm.append(news_id)
        added = True
    user["bookmarks"] = bm
    save_user(user)
    return user, added
