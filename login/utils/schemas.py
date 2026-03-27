from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    name: Optional[str] = ""

    @field_validator("username")
    @classmethod
    def username_clean(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, _ and -")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class PreferenceRequest(BaseModel):
    liked_categories: List[str] = []
    disliked_categories: List[str] = []
    description: Optional[str] = ""
    use_ai_extraction: bool = False

class ChangePasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatContextRequest(BaseModel):
    context_text: str  # The article text or timeline details
    messages: List[ChatMessage]
