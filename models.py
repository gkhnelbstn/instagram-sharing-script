"""Pydantic models for the Instagram Group Sharing API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config models (persisted in config.json)
# ---------------------------------------------------------------------------


class Account(BaseModel):
    """Kaydedilmiş bir Instagram hesabı."""

    id: str = Field(..., description="Benzersiz hesap ID'si (UUID)")
    username: str
    password: str
    logged_in: bool = False


class GroupConfig(BaseModel):
    """Bir hesaba ait seçilmiş grup bilgisi."""

    thread_id: str
    thread_title: str
    user_count: int = 0


class AccountConfig(BaseModel):
    """Bir hesabın tam config'i: kimlik bilgileri + seçili gruplar."""

    id: str
    username: str
    password: str
    logged_in: bool = False
    selected_groups: list[GroupConfig] = []


class AppConfig(BaseModel):
    """Tüm uygulama konfigürasyonu (config.json)."""

    accounts: list[AccountConfig] = []
    owner_id: str | None = None  # hangi AppUser'a ait


class AppUser(BaseModel):
    """Uygulamaya giriş yapan kullanıcı hesabı."""

    id: str = Field(..., description="Benzersiz kullanıcı ID'si (UUID)")
    username: str
    hashed_password: str  # bcrypt hash
    session_token: str | None = None  # aktif oturum tokeni
    password_hint: str | None = None  # şifre sıfırlama ipucu


class UsersConfig(BaseModel):
    """Tüm uygulama kullanıcıları (users.json)."""

    users: list[AppUser] = []


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class AddAccountRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class SaveGroupsRequest(BaseModel):
    """Bir hesap için seçili grupları kaydet."""

    groups: list[GroupConfig]


class SendRequest(BaseModel):
    """Link gönderim isteği."""

    link: str = Field(..., description="Paylaşılacak gönderi linki")
    message: str | None = Field(
        default=None, description="Gönderi ile birlikte gönderilecek opsiyonel mesaj"
    )
    account_ids: list[str] = Field(..., description="Gönderim yapılacak hesap ID'leri")
    delay: int = Field(
        default=8, ge=1, le=60, description="Gönderimler arası bekleme (saniye)"
    )


class GroupInfo(BaseModel):
    thread_id: str
    thread_title: str
    user_count: int


class GroupResult(BaseModel):
    thread_id: str
    group: str
    status: str  # "ok" | "error"
    message: str | None = None


class AccountSendResult(BaseModel):
    account_id: str
    username: str
    total_groups: int
    sent: int = 0
    failed: int = 0
    results: list[GroupResult] = []


class SendResponse(BaseModel):
    total_accounts: int
    account_results: list[AccountSendResult] = []


class RegisterRequest(BaseModel):
    username: str
    password: str
    password_hint: str | None = None  # şifre sıfırlama ipucu


class AppLoginRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    username: str
    password_hint: str
    new_password: str


