import httpx
import json
import re
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, ALL_CATEGORIES

VALID_KEYS = list(ALL_CATEGORIES.keys())

SYSTEM_PROMPT = """You are a news preference extraction assistant.
Given a user's self-description, extract the most relevant news category keys.

RULES:
1. Only return keys from the provided valid_categories list.
2. Return ONLY a JSON array of strings — no explanation, no markdown, no extra text.
3. Include 3-10 categories that best match the user's interests.
4. Never include a key that is NOT in valid_categories.

Example output: ["stocks", "startups", "economy"]
"""


async def extract_categories_from_description(description: str) -> list:
    prompt = (
        f"Valid categories: {json.dumps(VALID_KEYS)}\n\n"
        f'User description: "{description}"\n\n'
        "Return a JSON array of matching category keys only."
    )
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip()
            extracted = json.loads(raw)
            if isinstance(extracted, list):
                return [k for k in extracted if k in VALID_KEYS]
    except Exception as e:
        print(f"[Ollama] extraction failed: {e}")
    return []


async def extract_tracking_keywords(topic_name: str) -> dict:
    prompt = (
        f'Topic: "{topic_name}"\n\n'
        'Return JSON with keys "keywords" (5-10 strings) and "expanded_topics" (3-5 strings). '
        "No markdown, no extra text."
    )
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "system": "You are a news tracking assistant. Return only valid JSON.",
        "stream": False,
        "options": {"temperature": 0.3},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip()
            result = json.loads(raw)
            return {
                "keywords":        result.get("keywords", [topic_name.lower()]),
                "expanded_topics": result.get("expanded_topics", []),
            }
    except Exception as e:
        print(f"[Ollama] tracking keyword extraction failed: {e}")
    return {"keywords": topic_name.lower().split(), "expanded_topics": []}


async def summarise_article(title: str, content: str, original_url: str = "") -> str:
    """Summarise a news article using Ollama. No predictions, just facts."""
    text = f"Title: {title}\n\nContent: {content}" if content else f"Title: {title}"

    prompt = (
        f"Summarise the following news article in simple, easy-to-understand language.\n\n"
        f"RULES:\n"
        f"1. Keep it factual — do NOT make predictions or speculate.\n"
        f"2. Use 3-5 short paragraphs.\n"
        f"3. Use simple words a non-expert can understand.\n"
        f"4. End with: \"To read the full article, visit the original source.\"\n\n"
        f"Article:\n{text}"
    )

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "system": "You are a news summariser. Summarise factually, no predictions, no opinions. Keep it simple and short.",
        "stream": True,
        "options": {"temperature": 0.3},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line: continue
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
        if original_url:
            yield f"\n\nTo read more, visit: {original_url}"
    except Exception as e:
        print(f"[Ollama] summarisation stream failed: {e}")
        yield "\n\nConnection to AI failed."


async def summarise_timeline(topic_title: str, articles: list[dict]) -> str:
    """Summarise a timeline of tracked news articles in a super simple, creative way."""
    # Build a compact timeline text from articles
    timeline_entries = []
    for a in articles[:15]:  # Limit to 15 most relevant
        entry = f"- {a.get('published_time', 'Unknown time')}: {a.get('title', '')}. {a.get('short_desc', '')}"
        timeline_entries.append(entry)

    timeline_text = "\n".join(timeline_entries)

    prompt = (
        f'Topic being tracked: "{topic_title}"\n\n'
        f"Here are news articles about this topic in timeline order:\n\n"
        f"{timeline_text}\n\n"
        f"TASK: Create a fun, super easy-to-understand summary of this news timeline.\n\n"
        f"RULES:\n"
        f"1. Write like you're explaining to a 10-year-old child — simple words, short sentences.\n"
        f"2. Use a storytelling style — like telling a story of what happened.\n"
        f"3. Use emojis to make it engaging and visual.\n"
        f"4. Start with a one-line summary, then tell the story in timeline order.\n"
        f"5. Keep it factual — NO predictions, NO opinions, NO speculation.\n"
        f"6. End with: 'That's the story so far! Stay tuned for more updates.'\n"
        f"7. Maximum 200 words.\n"
    )

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "system": (
            "You are a friendly news explainer for kids. "
            "Summarise news timelines in a fun, simple, factual way. "
            "Use emojis, short sentences, and storytelling. "
            "Never predict or speculate. Keep it short and engaging."
        ),
        "stream": True,
        "options": {"temperature": 0.5},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line: continue
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
    except Exception as e:
        print(f"[Ollama] timeline stream summarisation failed: {e}")
        yield " Oops! Connection dropped."


async def chat_with_context_ai(context_text: str, messages: list[dict]) -> str:
    """
    Stateful chat with the AI about a specific context (article or timeline).
    Injects a hidden system prompt to keep the AI focused.
    `messages` format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    system_prompt = (
        "You are a friendly, creative, and helpful AI assistant interacting with a user about the news.\n"
        "Use simple, easy-to-understand language. Feel free to use emojis to make it looks good and creative.\n"
        "If they ask about the content, refer to the following context:\n\n"
        "================\n"
        f"{context_text}\n"
        "================\n\n"
        "Do NOT mention 'the context provided above' explicitly to the user. Just speak naturally."
    )

    # Prepend the system prompt to the user's message history
    formatted_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        formatted_messages.append({"role": m["role"], "content": m["content"]})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": formatted_messages,
        "stream": True,
        "options": {"temperature": 0.6},
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line: continue
                    data = json.loads(line)
                    if "message" in data:
                        yield data["message"].get("content", "")
    except Exception as e:
        print(f"[Ollama] Context chat stream failed: {e}")
        yield " [Connection lost]"
