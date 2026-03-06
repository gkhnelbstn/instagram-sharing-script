"""
Instagram Group Sharing API

FastAPI servisi — instagrapi ile Instagram grup mesajlarına link gönderir.
Web UI ile hesap, grup yönetimi ve gönderim yapılır.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
)

from models import (
    AccountConfig,
    AccountSendResult,
    AddAccountRequest,
    AppConfig,
    GroupConfig,
    GroupInfo,
    GroupResult,
    SaveGroupsRequest,
    SendRequest,
    SendResponse,
)

# ---------------------------------------------------------------------------
# App & Logger
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Instagram Group Sharing API",
    description="Instagram grup sohbetlerine gönderi linklerini paylaşan API servisi",
    version="2.0.0",
)

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

CONFIG_FILE = Path("config.json")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _load_config() -> AppConfig:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig(**data)
    return AppConfig()


def _save_config(config: AppConfig) -> None:
    CONFIG_FILE.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _find_account(config: AppConfig, account_id: str) -> AccountConfig:
    for acc in config.accounts:
        if acc.id == account_id:
            return acc
    raise HTTPException(status_code=404, detail="Hesap bulunamadı")


# ---------------------------------------------------------------------------
# Instagram helpers
# ---------------------------------------------------------------------------


def _get_client(username: str, password: str) -> Client:
    """instagrapi Client oluştur, session varsa yükle, yoksa login ol."""
    cl = Client()
    cl.delay_range = [1, 3]

    session_file = SESSIONS_DIR / f"{username}.json"

    try:
        if session_file.exists():
            cl.load_settings(session_file)
            cl.login(username, password)
            logger.info("Session dosyasından giriş yapıldı: %s", username)
        else:
            cl.login(username, password)
            logger.info("Yeni giriş yapıldı: %s", username)

        cl.dump_settings(session_file)
        return cl

    except BadPassword:
        raise HTTPException(status_code=401, detail=f"Hatalı şifre: {username}")
    except TwoFactorRequired:
        raise HTTPException(
            status_code=403,
            detail=f"2FA doğrulaması gerekli: {username}",
        )
    except ChallengeRequired:
        raise HTTPException(
            status_code=403,
            detail=f"Instagram challenge istiyor: {username}. Uygulamadan onaylayın.",
        )
    except LoginRequired:
        if session_file.exists():
            session_file.unlink()
            logger.warning("Geçersiz session silindi: %s", username)
            cl = Client()
            cl.delay_range = [1, 3]
            cl.login(username, password)
            cl.dump_settings(session_file)
            return cl
        raise HTTPException(status_code=401, detail=f"Giriş yapılamadı: {username}")
    except Exception as exc:
        logger.exception("Login hatası: %s", username)
        raise HTTPException(status_code=500, detail=f"Login hatası: {str(exc)}")


# ---------------------------------------------------------------------------
# API — Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# API — Account CRUD
# ---------------------------------------------------------------------------


@app.get("/api/accounts")
def get_accounts():
    """Tüm hesapları listele (şifreler maskelenir)."""
    config = _load_config()
    return [
        {
            "id": acc.id,
            "username": acc.username,
            "logged_in": acc.logged_in,
            "selected_groups_count": len(acc.selected_groups),
        }
        for acc in config.accounts
    ]


@app.post("/api/accounts")
def add_account(req: AddAccountRequest):
    """Yeni hesap ekle."""
    config = _load_config()

    # Aynı username varsa hata
    for acc in config.accounts:
        if acc.username == req.username:
            raise HTTPException(status_code=409, detail="Bu hesap zaten ekli.")

    new_acc = AccountConfig(
        id=str(uuid.uuid4()),
        username=req.username,
        password=req.password,
    )
    config.accounts.append(new_acc)
    _save_config(config)
    return {"id": new_acc.id, "username": new_acc.username}


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    """Hesabı sil."""
    config = _load_config()
    config.accounts = [a for a in config.accounts if a.id != account_id]
    _save_config(config)

    # Session dosyasını da sil
    for f in SESSIONS_DIR.glob("*.json"):
        # Dosya adının username olup olmadığını kontrol et
        pass

    return {"ok": True}


# ---------------------------------------------------------------------------
# API — Login & Groups
# ---------------------------------------------------------------------------


@app.post("/api/accounts/{account_id}/login")
def login_account(account_id: str):
    """Hesaba giriş yap ve durumunu güncelle."""
    config = _load_config()
    acc = _find_account(config, account_id)

    _get_client(acc.username, acc.password)
    acc.logged_in = True
    _save_config(config)

    return {"ok": True, "username": acc.username}


@app.get("/api/accounts/{account_id}/groups")
def list_groups(account_id: str):
    """Hesaptaki tüm grup thread'lerini listele."""
    config = _load_config()
    acc = _find_account(config, account_id)

    cl = _get_client(acc.username, acc.password)
    acc.logged_in = True
    _save_config(config)

    try:
        threads = cl.direct_threads(amount=100)
    except Exception as exc:
        logger.error("Grup listeleme hatası (%s): %s", acc.username, str(exc))
        # Eğer 403 Forbidden alırsak (session patlamış olabilir), session'ı temizle ki kullanıcı tekrar giriş yapabilsin
        if "403 Client Error" in str(exc) or "Forbidden" in str(exc):
            acc.logged_in = False
            _save_config(config)
            session_file = SESSIONS_DIR / f"{acc.username}.json"
            if session_file.exists():
                session_file.unlink()
            raise HTTPException(
                status_code=401,
                detail="Oturum süresi dolmuş veya geçersiz. Lütfen hesaba tekrar giriş yapın (Login).",
            )
        raise HTTPException(status_code=500, detail=f"Gruplar alınamadı: {str(exc)}")

    group_threads = [t for t in threads if len(t.users) > 1]

    # Önceden seçilmiş grupların ID'lerini topla
    selected_ids = {g.thread_id for g in acc.selected_groups}

    return [
        {
            "thread_id": str(t.id),
            "thread_title": t.thread_title or "İsimsiz Grup",
            "user_count": len(t.users),
            "selected": str(t.id) in selected_ids,
        }
        for t in group_threads
    ]


@app.put("/api/accounts/{account_id}/groups")
def save_selected_groups(account_id: str, req: SaveGroupsRequest):
    """Hesap için seçili grupları kaydet."""
    config = _load_config()
    acc = _find_account(config, account_id)
    acc.selected_groups = req.groups
    _save_config(config)
    return {"ok": True, "count": len(req.groups)}


# ---------------------------------------------------------------------------
# API — Send
# ---------------------------------------------------------------------------


@app.post("/api/send", response_model=SendResponse)
def send_link(req: SendRequest):
    """Seçili hesap(lar)ın seçili gruplarına link gönder."""
    config = _load_config()

    account_results: list[AccountSendResult] = []

    for acc_id in req.account_ids:
        acc = _find_account(config, acc_id)

        if not acc.selected_groups:
            account_results.append(
                AccountSendResult(
                    account_id=acc.id,
                    username=acc.username,
                    total_groups=0,
                )
            )
            continue

        try:
            cl = _get_client(acc.username, acc.password)
        except HTTPException as exc:
            account_results.append(
                AccountSendResult(
                    account_id=acc.id,
                    username=acc.username,
                    total_groups=len(acc.selected_groups),
                    failed=len(acc.selected_groups),
                    results=[
                        GroupResult(
                            thread_id=g.thread_id,
                            group=g.thread_title,
                            status="error",
                            message=exc.detail,
                        )
                        for g in acc.selected_groups
                    ],
                )
            )
            continue

        # 1. URL'den Media ID'sini çıkarmayı dene
        try:
            # We use the first client we successfully log in to fetch the media_pk
            # If we haven't logged in yet, we'll do it in the loop below. But we need it once.
            media_pk = None
        except Exception as e:
            pass  # We will handle this in the loop more robustly

        results: list[GroupResult] = []
        for idx, group in enumerate(acc.selected_groups):
            try:
                # Get media pk if we don't have it yet
                if "media_pk" not in locals() or media_pk is None:
                    try:
                        media_pk = cl.media_pk_from_url(req.link)
                    except Exception as e:
                        logger.error("Media ID çıkarılamadı: %s", req.link)
                        raise ValueError(
                            f"Geçersiz Instagram linki veya gönderi gizli: {str(e)}"
                        )

                # 1. Gönderiyi paylaş
                cl.direct_media_share(
                    media_id=media_pk, thread_ids=[int(group.thread_id)]
                )

                # 2. Varsa opsiyonel mesajı gönder (üzerine biraz gecikme ekleyerek)
                if req.message and req.message.strip():
                    time.sleep(1)  # Mesajlar arası minik bir es
                    cl.direct_send(
                        text=req.message.strip(), thread_ids=[int(group.thread_id)]
                    )

                logger.info("✅ [%s] → %s", acc.username, group.thread_title)
                results.append(
                    GroupResult(
                        thread_id=group.thread_id,
                        group=group.thread_title,
                        status="ok",
                    )
                )
            except Exception as exc:
                logger.error("❌ [%s] → %s: %s", acc.username, group.thread_title, exc)
                results.append(
                    GroupResult(
                        thread_id=group.thread_id,
                        group=group.thread_title,
                        status="error",
                        message=str(exc),
                    )
                )

            if idx < len(acc.selected_groups) - 1:
                time.sleep(req.delay)

        sent = sum(1 for r in results if r.status == "ok")
        failed = sum(1 for r in results if r.status == "error")
        account_results.append(
            AccountSendResult(
                account_id=acc.id,
                username=acc.username,
                total_groups=len(acc.selected_groups),
                sent=sent,
                failed=failed,
                results=results,
            )
        )

    return SendResponse(
        total_accounts=len(req.account_ids),
        account_results=account_results,
    )


# ---------------------------------------------------------------------------
# Serve static UI
# ---------------------------------------------------------------------------

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_ui():
    return FileResponse("static/index.html")
