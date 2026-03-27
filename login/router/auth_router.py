from fastapi import APIRouter, HTTPException, status, Response, Request, Depends
from fastapi.responses import HTMLResponse

from templates import login_render
from login.utils.schemas import RegisterRequest, LoginRequest, ChangePasswordRequest
from login.utils.auth_utils import hash_password, verify_password, create_access_token
from login.utils.storage import user_exists, email_exists, create_user, load_user, update_last_login
from admin.utils.storage import load_admin, update_admin_last_login
from login.utils.dependencies import get_current_user

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return login_render("login.html", {})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return login_render("register.html", {})


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response):
    if user_exists(body.username):
        raise HTTPException(409, "Username already taken. Please choose another.")
    if email_exists(body.email):
        raise HTTPException(409, "An account with this email already exists.")

    user  = create_user(body.username, body.email, hash_password(body.password), body.name or "")
    token = create_access_token({"sub": user["username"]})
    
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, max_age=86400, samesite="lax",
    )
    
    return {
        "access_token":    token,
        "token_type":      "bearer",
        "username":        user["username"],
        "preferences_set": False,
    }


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    admin = load_admin(body.username)
    if admin and verify_password(body.password, admin["password_hash"]):
        update_admin_last_login(body.username)
        token = create_access_token({"sub": admin["username"]})
        response.set_cookie(
            key="admin_access_token", value=token,
            httponly=True, max_age=86400, samesite="lax",
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "username": admin["username"],
            "is_admin": True,
        }

    user = load_user(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")

    update_last_login(body.username)
    token = create_access_token({"sub": user["username"]})

    response.set_cookie(
        key="access_token", value=token,
        httponly=True, max_age=86400, samesite="lax",
    )
    return {
        "access_token":    token,
        "token_type":      "bearer",
        "username":        user["username"],
        "preferences_set": user["profile"].get("preferences_set", False),
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id":             current_user["user_id"],
        "username":            current_user["username"],
        "email":               current_user["email"],
        "name":                current_user["profile"]["name"],
        "created_at":          current_user["profile"]["created_at"],
        "last_login":          current_user["profile"]["last_login"],
        "preferences_set":     current_user["profile"].get("preferences_set", False),
        "liked_categories":    current_user["preferences"]["liked_categories"],
        "disliked_categories": current_user["preferences"]["disliked_categories"],
        "tracked_topics":      current_user["tracked_topics"],
        "bookmarks":           current_user["bookmarks"],
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    user = load_user(current_user["username"])
    # Note: user specifically requested "dont do password hash" in older session,
    # so hash_password currently returns plain text.
    user["password_hash"] = hash_password(body.new_password)
    from login.utils.storage import save_user
    save_user(user)
    return {"message": "Password updated successfully"}
