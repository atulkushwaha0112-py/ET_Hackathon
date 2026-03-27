"""
╔══════════════════════════════════════════════════════════════╗
║         Economic Times — Production Scraper v1.0             ║
║  Strategy : RSS feed (discovery) + requests/BS4 (content)   ║
║  Storage  : NEWS_DATA/<category>.json  (append/dedup)        ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ════════════════════════════════════════════════════════════════
#                  ⚙️  CONFIGURATION — EDIT HERE
# ════════════════════════════════════════════════════════════════

ARTICLES_PER_CATEGORY = 2       # articles to fetch per category per cycle
MAX_DESC_LEN          = 1500     # max chars for long_desc (None = unlimited)
REST_TIME             = 200     # seconds to sleep after ALL categories done
WAIT                  = 3.0     # seconds to sleep between category fetches
NEWS_DATA_DIR         = "NEWS_DATA_ET"

# ════════════════════════════════════════════════════════════════

BASE_ET = "https://economictimes.indiatimes.com"

# ── Verified active ET RSS feed URLs (feedspot / ET official) ──
# Format: { "category_name": "full_rss_url" }
CATEGORY_RSS_MAP = {
    # ── Top News ──────────────────────────────────────────────
    "top_news":         f"{BASE_ET}/rssfeedsdefault.cms",
    "latest_news":      f"{BASE_ET}/News/rssfeeds/1715249553.cms",

    # ── Markets ───────────────────────────────────────────────
    "markets":          f"{BASE_ET}/markets/rssfeeds/1977021501.cms",
    "stocks":           f"{BASE_ET}/markets/stocks/rssfeeds/2146842.cms",
    "ipo":              f"{BASE_ET}/markets/ipos/fpos/rssfeeds/14655708.cms",
    "cryptocurrency":   f"{BASE_ET}/markets/cryptocurrency/rssfeeds/82519373.cms",
    "commodities":      f"{BASE_ET}/markets/commodities/rssfeeds/1808152121.cms",
    "forex":            f"{BASE_ET}/markets/forex/rssfeeds/1150221130.cms",
    "bonds":            f"{BASE_ET}/markets/bonds/rssfeeds/2146846.cms",

    # ── News ──────────────────────────────────────────────────
    "india_news":       f"{BASE_ET}/news/india/rssfeeds/81582957.cms",
    "economy":          f"{BASE_ET}/news/economy/rssfeeds/1373380680.cms",
    "politics":         f"{BASE_ET}/news/politics-and-nation/rssfeeds/1052732854.cms",
    "international":    f"{BASE_ET}/news/international/rssfeeds/858478126.cms",
    "company":          f"{BASE_ET}/news/company/rssfeeds/2143429.cms",
    "defence":          f"{BASE_ET}/news/defence/rssfeeds/46687796.cms",
    "science":          f"{BASE_ET}/news/science/rssfeeds/39872847.cms",
    "environment":      f"{BASE_ET}/news/environment/rssfeeds/2647163.cms",
    "sports":           f"{BASE_ET}/news/sports/rssfeeds/26407562.cms",
    "elections":        f"{BASE_ET}/news/elections/rssfeeds/65869819.cms",

    # ── Industry ──────────────────────────────────────────────
    "industry":         f"{BASE_ET}/industry/rssfeeds/13352306.cms",
    "tech_industry":    f"{BASE_ET}/tech/rssfeeds/13357270.cms",
    "healthcare":       f"{BASE_ET}/industry/healthcare/biotech/rssfeeds/13358050.cms",
    "services":         f"{BASE_ET}/industry/services/rssfeeds/13354120.cms",
    "media_ent":        f"{BASE_ET}/industry/media/entertainment/rssfeeds/13357212.cms",
    "transportation":   f"{BASE_ET}/industry/transportation/rssfeeds/13353990.cms",
    "renewables":       f"{BASE_ET}/industry/renewables/rssfeeds/81585238.cms",
    "banking_finance":  f"{BASE_ET}/industry/banking/finance/rssfeeds/13358250.cms",

    # ── Tech & Startups ───────────────────────────────────────
    "startups":         f"{BASE_ET}/tech/startups/rssfeeds/78570540.cms",
    "funding":          f"{BASE_ET}/tech/funding/rssfeeds/78570550.cms",
    "information_tech": f"{BASE_ET}/tech/information-tech/rssfeeds/78570530.cms",
    "tech_internet":    f"{BASE_ET}/tech/technology/rssfeeds/78570561.cms",
    "education":    f"{BASE_ET}/education/rssfeeds/913168846.cms",

    # ── Personal Finance / Wealth ─────────────────────────────
    "wealth":           f"{BASE_ET}/wealth/rssfeeds/837555174.cms",
    "mutual_funds":     f"{BASE_ET}/mf/rssfeeds/359241701.cms",
    "personal_finance": f"{BASE_ET}/wealth/personal-finance-news/rssfeeds/49674901.cms",
    "insurance":        f"{BASE_ET}/wealth/insure/rssfeeds/47119917.cms",
    "tax":              f"{BASE_ET}/wealth/tax/rssfeeds/47119912.cms",

    # ── Small Biz ─────────────────────────────────────────────
    "small_biz":        f"{BASE_ET}/small-biz/rssfeeds/5575607.cms",
    "entrepreneurship": f"{BASE_ET}/small-biz/entrepreneurship/rssfeeds/11993034.cms",
    "gst":              f"{BASE_ET}/small-biz/gst/rssfeeds/58475404.cms",

    # ── Jobs / Careers ────────────────────────────────────────
    "jobs":             f"{BASE_ET}/jobs/rssfeeds/107115.cms",

    # ── Opinion ───────────────────────────────────────────────
    "opinion":          f"{BASE_ET}/opinion/rssfeeds/897228639.cms",
    "et_editorial":     f"{BASE_ET}/opinion/et-editorial/rssfeeds/3376910.cms",

    # ── Magazines / Lifestyle ─────────────────────────────────
    "travel":           f"{BASE_ET}/magazines/travel/rssfeeds/640246854.cms",
    "et_magazine":      f"{BASE_ET}/magazines/et-magazine/rssfeeds/7771003.cms",

    # ── NRI ───────────────────────────────────────────────────
    "nri":              f"{BASE_ET}/nri/rssfeeds/7771250.cms",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://www.google.com/",
    "DNT":             "1",
    "Upgrade-Insecure-Requests": "1",
}

session = requests.Session()
session.headers.update(HEADERS)

os.makedirs(NEWS_DATA_DIR, exist_ok=True)


# ════════════════════════════════════════════════════════════════
#                     JSON DATABASE HELPERS
# ════════════════════════════════════════════════════════════════

def db_path(category: str) -> str:
    return os.path.join(NEWS_DATA_DIR, f"{category}.json")


def db_load(category: str) -> list[dict]:
    path = db_path(category)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def db_save(category: str, articles: list[dict]) -> None:
    """Atomic write — no corruption on interrupt."""
    path = db_path(category)
    tmp  = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)


def db_append(category: str, article: dict) -> bool:
    """
    Prepend article if URL not already stored.
    Newest is always at index 0 → db_pop() returns latest.
    Returns True if saved, False if duplicate.
    """
    articles     = db_load(category)
    existing_urls = {a["url"] for a in articles}
    if article["url"] in existing_urls:
        return False
    articles.insert(0, article)
    db_save(category, articles)
    return True


def db_pop(category: str) -> dict | None:
    """Remove and return the latest (newest) article."""
    articles = db_load(category)
    if not articles:
        return None
    latest = articles.pop(0)
    db_save(category, articles)
    return latest


# ════════════════════════════════════════════════════════════════
#                     NETWORK HELPERS
# ════════════════════════════════════════════════════════════════

def safe_get(url: str, timeout: int = 12) -> requests.Response | None:
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (403, 429, 503):
                time.sleep(3 * (attempt + 1))
            else:
                break
        except requests.exceptions.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


# ════════════════════════════════════════════════════════════════
#                   RSS FEED DISCOVERY
# ════════════════════════════════════════════════════════════════

def fetch_rss_stubs(category: str, limit: int) -> list[dict]:
    rss_url = CATEGORY_RSS_MAP[category]
    resp    = safe_get(rss_url)
    if not resp:
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return []

    ns    = {"media": "http://search.yahoo.com/mrss/"}
    items = root.findall(".//item")[:limit]
    stubs = []

    for item in items:
        def txt(tag, default=""):
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text else default

        thumbnail = None
        for mt in ("media:content", "media:thumbnail"):
            el = item.find(mt, ns)
            if el is not None:
                thumbnail = el.get("url")
                if thumbnail:
                    break

        keywords   = [c.text.strip() for c in item.findall("category") if c.text]
        raw_desc   = txt("description")
        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)

        url = txt("link") or txt("guid")
        if not url:
            continue

        stubs.append({
            "title":          txt("title"),
            "url":            url,
            "short_desc":     clean_desc[:300],
            "published_time": txt("pubDate"),
            "keywords":       keywords,
            "thumbnail":      thumbnail,
        })

    return stubs


# ════════════════════════════════════════════════════════════════
#                  ARTICLE CONTENT EXTRACTION
# ════════════════════════════════════════════════════════════════

def _try_json_ld(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data  = json.loads(script.string or "")
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                for item in node.get("@graph", [node]):
                    body = item.get("articleBody", "")
                    if body and len(body) > 80:
                        return body
        except Exception:
            pass
    return ""


def _try_dom_selectors(soup: BeautifulSoup) -> str:
    # ET-specific selectors
    for attrs in [
        {"class": "artText"},
        {"class": "article-body"},
        {"id":    "article-content"},
        {"role":  "article"},
        {"itemprop": "articleBody"},
    ]:
        el = soup.find(attrs=attrs)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 100:
                return text

    # Heuristic: div with most direct <p> children
    best_div, best_count = None, 0
    for div in soup.find_all("div"):
        paras = div.find_all("p", recursive=False)
        if len(paras) > best_count:
            best_count = len(paras)
            best_div   = div

    if best_div and best_count >= 3:
        seen, blocks = set(), []
        for p in best_div.find_all("p"):
            t = p.get_text(" ", strip=True)
            if len(t) > 40 and t not in seen:
                seen.add(t)
                blocks.append(t)
        result = " ".join(blocks)
        if len(result) > 100:
            return result
    return ""


def _try_readability(soup: BeautifulSoup) -> str:
    noise = re.compile(
        r"(cookie|subscribe|sign[ -]?in|follow us|download app|"
        r"advertisement|copyright|all rights reserved|terms of use|"
        r"privacy policy|read more|also read|trending|newsletter|"
        r"ET prime|login to read|exclusive for subscribers)", re.I
    )
    seen, blocks = set(), []
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if len(t) < 40 or noise.search(t) or t in seen:
            continue
        seen.add(t)
        blocks.append(t)
    return " ".join(blocks) if len(blocks) >= 2 else ""


def _try_meta(soup: BeautifulSoup) -> str:
    for attr, name in [("property", "og:description"), ("name", "description")]:
        tag = soup.find("meta", attrs={attr: name})
        if tag and tag.get("content", "").strip():
            return tag["content"].strip()
    return ""


def get_content(soup: BeautifulSoup) -> str:
    for fn in (_try_json_ld, _try_dom_selectors, _try_readability, _try_meta):
        result = fn(soup)
        if result and len(result) > 60:
            return result
    return "Content could not be extracted (likely paywalled or JS-rendered)."


def get_author(soup: BeautifulSoup) -> str:
    for attr, name in [
        ("name",     "author"),
        ("property", "author"),
        ("property", "article:author"),
    ]:
        tag = soup.find("meta", attrs={attr: name})
        if tag and tag.get("content", "").strip():
            return tag["content"].strip()
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data  = json.loads(script.string or "")
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                a = node.get("author")
                if isinstance(a, dict):
                    return a.get("name", "")
                if isinstance(a, list) and a:
                    return a[0].get("name", "")
        except Exception:
            pass
    return "Economic Times"


def get_modified_time(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", property="article:modified_time")
    return tag["content"].strip() if tag and tag.get("content") else ""


def get_category_from_page(soup: BeautifulSoup, url: str, fallback: str) -> str:
    tag = soup.find("meta", property="article:section")
    if tag and tag.get("content"):
        return tag["content"].strip()
    try:
        part = url.split("indiatimes.com/")[1].split("/")[0]
        if part and "articleshow" not in part:
            return part.replace("-", " ").title()
    except Exception:
        pass
    return fallback.replace("_", " ").title()


def get_thumbnail_from_page(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", property="og:image")
    return tag["content"].strip() if tag and tag.get("content") else None


# ════════════════════════════════════════════════════════════════
#                        ENRICHMENT
# ════════════════════════════════════════════════════════════════

def enrich(stub: dict, category: str) -> dict | None:
    url  = stub.get("url", "")
    if not url:
        return None

    # Skip ET Prime paywalled URLs
    if "/prime/" in url and "rssfeeds" not in url:
        pass  # still try — meta description may be enough

    resp = safe_get(url)
    if not resp:
        return None

    soup      = BeautifulSoup(resp.text, "html.parser")
    long_desc = get_content(soup)

    if MAX_DESC_LEN and len(long_desc) > MAX_DESC_LEN:
        long_desc = long_desc[:MAX_DESC_LEN].rsplit(" ", 1)[0] + "…"

    return {
        "title":          stub["title"],
        "url":            url,
        "category":       get_category_from_page(soup, url, category),
        "author":         get_author(soup),
        "published_time": stub.get("published_time", ""),
        "modified_time":  get_modified_time(soup),
        "keywords":       stub.get("keywords", []),
        "short_desc":     stub.get("short_desc", ""),
        "long_desc":      long_desc,
        "thumbnail":      stub.get("thumbnail") or get_thumbnail_from_page(soup),
        "source":         "Economic Times",
    }


# ════════════════════════════════════════════════════════════════
#                        MAIN LOOP
# ════════════════════════════════════════════════════════════════

def run_cycle(cycle: int) -> None:
    print(f"\n{'═'*60}")
    print(f"  Cycle #{cycle}  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")

    categories = list(CATEGORY_RSS_MAP.keys())

    for cat_idx, category in enumerate(categories):
        print(f"\n  [{cat_idx+1}/{len(categories)}] Category: {category.upper()}")

        stubs = fetch_rss_stubs(category, ARTICLES_PER_CATEGORY)
        if not stubs:
            print("    ⚠️  No stubs from RSS — skipping")
        else:
            for stub in stubs:
                # Dedup check BEFORE fetching full page
                existing = {a["url"] for a in db_load(category)}
                if stub["url"] in existing:
                    print(f"    ⏭  Already stored: {stub['title'][:60]}")
                    continue

                print(f"    ↓  Fetching: {stub['url']}")
                article = enrich(stub, category)

                if article:
                    appended = db_append(category, article)
                    status   = "✅ Saved" if appended else "⏭  Duplicate"
                    print(f"    {status}: {article['title'][:60]}")
                else:
                    print(f"    ❌ Failed: {stub['title'][:60]}")

        if cat_idx < len(categories) - 1:
            print(f"\n    ⏳ Waiting {WAIT}s before next category…")
            time.sleep(WAIT)

    # ── End-of-cycle summary ───────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  Cycle #{cycle} complete.")
    print(f"  DB snapshot:")
    for category in categories:
        count = len(db_load(category))
        print(f"    {category:<20} → {count:>4} articles  ({db_path(category)})")
    print(f"{'─'*60}")
    print(f"\n  💤 Resting for {REST_TIME}s …\n")


if __name__ == "__main__":
    print("\n  Economic Times Scraper v1.0 — continuous mode")
    print(f"  Storage  : {os.path.abspath(NEWS_DATA_DIR)}/")
    print(f"  Feeds    : {len(CATEGORY_RSS_MAP)} categories")
    print(f"  Per run  : {ARTICLES_PER_CATEGORY} articles × {len(CATEGORY_RSS_MAP)} categories")
    print(f"  WAIT     : {WAIT}s between categories")
    print(f"  REST_TIME: {REST_TIME}s after full cycle\n")

    cycle = 1
    while True:
        try:
            run_cycle(cycle)
            cycle += 1
            time.sleep(REST_TIME)
        except KeyboardInterrupt:
            print("\n\n  👋 Stopped by user.")
            break