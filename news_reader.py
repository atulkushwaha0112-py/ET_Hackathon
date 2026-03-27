import os
import json
import re
from datetime import datetime, timezone
from typing import Optional
from email.utils import parsedate_to_datetime
from config import NEWS_DATA_DIR, ALL_CATEGORIES


def _load_category(cat_key: str) -> list:
    candidates = [
        os.path.join(NEWS_DATA_DIR, f"{cat_key}.json"),
        os.path.join(NEWS_DATA_DIR, cat_key, "data.json"),
        os.path.join(NEWS_DATA_DIR, cat_key, f"{cat_key}.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for a in data:
                        a.setdefault("_cat", cat_key)
                    return data
                if isinstance(data, dict):
                    for val in data.values():
                        if isinstance(val, list):
                            for a in val:
                                a.setdefault("_cat", cat_key)
                            return val
            except Exception as e:
                print(f"[reader] {path}: {e}")
            break
    return []


def _parse_time(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    return None


def _news_id(article: dict) -> str:
    pt = article.get("published_time", "")
    if pt:
        return re.sub(r"[^\w\-:+]", "_", pt)
    return str(abs(hash(article.get("url", str(article)))))


def _score(article: dict, liked: set, disliked: set, keywords: list) -> float:
    s = 0.5
    cat = article.get("_cat", "")
    if cat in liked:
        s += 0.3
    if cat in disliked:
        s -= 0.5
    if keywords:
        text = (article.get("title", "") + " " + article.get("short_desc", "")).lower()
        hits = sum(1 for kw in keywords if kw.lower() in text)
        s += min(hits * 0.05, 0.2)
    return round(max(0.0, min(1.0, s)), 3)


def _clean(article: dict) -> dict:
    return {k: v for k, v in article.items() if not k.startswith("_")}


def get_personalised_feed(user: dict, limit: int = 60,
                          category_filter: Optional[str] = None) -> dict:
    prefs    = user.get("preferences", {})
    liked    = set(prefs.get("liked_categories", []))
    disliked = set(prefs.get("disliked_categories", []))
    kws      = prefs.get("extracted_keywords", [])

    if category_filter and category_filter in ALL_CATEGORIES:
        cats = [category_filter]
    elif liked:
        cats = list(liked)
    else:
        cats = ["top_news", "latest_news"]

    all_arts = []
    for cat in cats:
        all_arts.extend(_load_category(cat))

    # Deduplicate
    seen, unique = set(), []
    for a in all_arts:
        nid = _news_id(a)
        if nid not in seen:
            seen.add(nid)
            a["news_id"] = nid
            unique.append(a)

    # Score + sort
    for a in unique:
        a["_score"]  = _score(a, liked, disliked, kws)
        a["_pub_dt"] = _parse_time(a.get("published_time", ""))

    for_you = sorted(unique, key=lambda a: (a["_score"], a["_pub_dt"].timestamp() if a["_pub_dt"] else 0), reverse=True)[:limit]

    by_cat = {}
    for a in unique:
        k = a.get("_cat", "other")
        by_cat.setdefault(k, [])
        by_cat[k].append(a)

    for k in by_cat:
        by_cat[k].sort(key=lambda a: (a["_pub_dt"].timestamp() if a["_pub_dt"] else 0), reverse=True)
        by_cat[k] = by_cat[k][:20]

    return {
        "for_you":          [_clean(a) for a in for_you],
        "by_category":      {k: [_clean(a) for a in v] for k, v in by_cat.items()},
        "total":            len(unique),
        "categories_loaded": cats,
    }


def get_category_feed(cat_key: str, limit: int = 30) -> list:
    arts = _load_category(cat_key)
    for a in arts:
        a["news_id"] = _news_id(a)
        a["_pub_dt"] = _parse_time(a.get("published_time", ""))
    arts.sort(key=lambda a: (a["_pub_dt"].timestamp() if a["_pub_dt"] else 0), reverse=True)
    return [_clean(a) for a in arts[:limit]]


def get_bookmarked_articles(user: dict) -> list:
    bookmarks = set(user.get("bookmarks", []))
    if not bookmarks:
        return []
    found = []
    for cat in ALL_CATEGORIES:
        for a in _load_category(cat):
            nid = _news_id(a)
            if nid in bookmarks:
                a["news_id"] = nid
                found.append(_clean(a))
                bookmarks.discard(nid)
        if not bookmarks:
            break
    return found


def find_article_by_id(news_id: str) -> dict | None:
    """Find a single article by its news_id across all categories."""
    for cat in ALL_CATEGORIES:
        for a in _load_category(cat):
            nid = _news_id(a)
            if nid == news_id:
                a["news_id"] = nid
                return _clean(a)
    return None


# ── Stop words for keyword extraction ─────────────────────────────────────────
_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "of", "in", "to", "for",
    "with", "on", "at", "from", "by", "about", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out", "off",
    "over", "under", "again", "further", "then", "once", "and", "but", "or",
    "nor", "not", "no", "so", "if", "that", "this", "these", "those",
    "it", "its", "he", "she", "they", "them", "his", "her", "their",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "all", "each", "every", "some", "any", "few", "more", "most", "other",
    "up", "down", "just", "now", "also", "very", "much", "too", "than",
    "amid", "says", "set", "check", "per", "rs",
}


def extract_keywords_from_title(title: str) -> list[str]:
    """Extract meaningful keywords from a news title."""
    words = re.findall(r"[a-zA-Z]{3,}", title.lower())
    return [w for w in words if w not in _STOP_WORDS]


def find_related_news(title: str, limit: int = 50) -> list[dict]:
    """Find all news articles related to a title by keyword matching."""
    keywords = extract_keywords_from_title(title)
    if not keywords:
        return []

    results = []
    seen = set()

    for cat in ALL_CATEGORIES:
        for a in _load_category(cat):
            nid = _news_id(a)
            if nid in seen:
                continue
            seen.add(nid)

            text = (
                (a.get("title", "") + " " + a.get("short_desc", "") + " " + a.get("long_desc", ""))
                .lower()
            )
            hits = sum(1 for kw in keywords if kw in text)
            # Need at least 2 keyword hits or 30% match
            threshold = max(2, len(keywords) * 0.3)
            if hits >= threshold:
                a["news_id"] = nid
                a["_match_score"] = hits
                a["_pub_dt"] = _parse_time(a.get("published_time", ""))
                results.append(a)

    # Sort by published time (newest first)
    results.sort(
        key=lambda a: (a["_pub_dt"].timestamp() if a.get("_pub_dt") else 0),
        reverse=True,
    )

    return [_clean(a) | {"match_score": a.get("_match_score", 0)} for a in results[:limit]]


