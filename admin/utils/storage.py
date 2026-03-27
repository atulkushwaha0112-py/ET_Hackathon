import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import ADMIN_DATA_DIR

def _admin_path(username: str) -> str:
    return os.path.join(ADMIN_DATA_DIR, f"{username.lower()}.json")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_admin(username: str) -> Optional[dict]:
    p = _admin_path(username)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_admin(admin: dict) -> None:
    with open(_admin_path(admin["username"]), "w", encoding="utf-8") as f:
        json.dump(admin, f, indent=2, ensure_ascii=False)

def admin_exists(username: str) -> bool:
    return os.path.exists(_admin_path(username))

def create_admin(username: str, password_hash: str) -> dict:
    admin = {
        "admin_id": f"admin_{uuid.uuid4().hex[:8]}",
        "username": username.lower(),
        "password_hash": password_hash,
        "created_at": _now(),
        "last_login": _now(),
    }
    save_admin(admin)
    return admin

def update_admin_last_login(username: str) -> None:
    admin = load_admin(username)
    if admin:
        admin["last_login"] = _now()
        save_admin(admin)
