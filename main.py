"""
Instagram Group Sharing API

FastAPI servisi — instagrapi ile Instagram grup mesajlarına link gönderir.
Web UI ile hesap, grup yönetimi ve gönderim yapılır.
"""

import json
import logging
import os
import re
import secrets
import time
import traceback
import uuid
from pathlib import Path

import bcrypt
from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
    UnknownError,
)
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError

from models import (
    AccountConfig,
    AccountSendResult,
    AddAccountRequest,
    AppConfig,
    AppLoginRequest,
    AppUser,
    GroupResult,
    RegisterRequest,
    ResetPasswordRequest,
    SaveGroupsRequest,
    SendRequest,
    SendResponse,
    UsersConfig,
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
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# instagrapi dahili loglarını da aç (challenge, auth vb. ayrıntılar görünsün)
logging.getLogger("instagrapi").setLevel(logging.DEBUG)
logging.getLogger("public_request").setLevel(logging.DEBUG)
logging.getLogger("private_request").setLevel(logging.DEBUG)

DATA_DIR = Path(os.getenv("DATA_DIR", "."))
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_DIR = DATA_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = CONFIG_DIR / "users.json"

SESSION_COOKIE = "ig_session"

# ---------------------------------------------------------------------------
# Users helpers
# ---------------------------------------------------------------------------


def _load_users() -> UsersConfig:
    if USERS_FILE.exists():
        try:
            data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            return UsersConfig(**data)
        except Exception as exc:
            logger.error("users.json okunamadı: %s", exc)
    return UsersConfig()


def _save_users(users: UsersConfig) -> None:
    tmp = USERS_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(users.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(USERS_FILE)
    except Exception as exc:
        logger.error("users.json kaydedilemedi: %s", exc)
        tmp.unlink(missing_ok=True)


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _get_current_user(ig_session: str | None = Cookie(default=None)) -> AppUser:
    """Cookie'den oturumu doğrula, kullanıcıyı döndür."""
    if not ig_session:
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    users = _load_users()
    for u in users.users:
        if u.session_token and secrets.compare_digest(u.session_token, ig_session):
            return u
    raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş oturum.")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _config_file(owner_id: str) -> Path:
    """Her kullanıcının config dosyası ayrı tutulur."""
    return CONFIG_DIR / f"config_{owner_id}.json"


def _load_config(owner_id: str) -> AppConfig:
    f = _config_file(owner_id)
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return AppConfig(**data)
        except Exception as exc:
            logger.error("Konfigürasyon okunamadı: %s", exc)
    return AppConfig(owner_id=owner_id)


def _save_config(config: AppConfig) -> None:
    assert config.owner_id, "owner_id zorunlu"
    f = _config_file(config.owner_id)
    tmp = f.with_suffix(".tmp")
    try:
        tmp.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(f)
    except Exception as exc:
        logger.error("Konfigürasyon kaydedilemedi: %s", exc)
        tmp.unlink(missing_ok=True)


def _find_account(config: AppConfig, account_id: str) -> AccountConfig:
    for acc in config.accounts:
        if acc.id == account_id:
            return acc
    raise HTTPException(status_code=404, detail="Hesap bulunamadı")


# ---------------------------------------------------------------------------
# Instagram helpers
# ---------------------------------------------------------------------------


def _get_client(username: str, password: str) -> Client:
    """
    instagrapi Client oluştur.

    Strateji (instagrapi best-practices):
      1. Session dosyası varsa yükle → login(username, password) çağır
         (bu aslında session ile devam eder, şifreyle yeniden giriş yapmaz).
      2. get_timeline_feed() ile session'ın geçerliliğini doğrula.
      3. Session geçersizse → aynı device UUID'leri koruyarak temiz login yap.
      4. Session dosyası yoksa → doğrudan login.
    """
    cl = Client()
    cl.delay_range = [2, 5]

    session_file = SESSIONS_DIR / f"{username}.json"
    login_via_session = False
    login_via_pw = False

    # ── 1) Session dosyasından giriş dene ──
    if session_file.exists():
        try:
            cl.load_settings(session_file)
            cl.login(username, password)
            logger.info("[%s] Session dosyasından giriş deneniyor…", username)

            # Session geçerli mi kontrol et
            try:
                cl.get_timeline_feed()
                login_via_session = True
                logger.info("[%s] ✅ Session geçerli.", username)
            except LoginRequired:
                logger.warning(
                    "[%s] Session geçersiz (LoginRequired), temiz login yapılacak…",
                    username,
                )
                old_session = cl.get_settings()

                # Yeni client — ama aynı device UUID'leri koru (Instagram güveni)
                cl.set_settings({})
                cl.set_uuids(old_session["uuids"])

                cl.login(username, password)
                login_via_session = True
                logger.info("[%s] ✅ Temiz login (aynı device) başarılı.", username)

        except BadPassword:
            raise HTTPException(status_code=401, detail=f"Hatalı şifre: {username}")
        except TwoFactorRequired:
            raise HTTPException(
                status_code=403,
                detail=f"2FA doğrulaması gerekli: {username}",
            )
        except ChallengeRequired as exc:
            logger.error(
                "[%s] Instagram challenge istiyor (session ile): %s\n%s",
                username,
                exc,
                traceback.format_exc(),
            )
            # Bozuk session'ı sil ki bir sonraki denemede temiz başlansın
            session_file.unlink(missing_ok=True)
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Instagram güvenlik doğrulaması (Challenge) istiyor: {username}. "
                    "Lütfen Instagram uygulamasını veya web'i açarak 'Bendim' diyerek "
                    "onaylayın, ardından tekrar deneyin."
                ),
            )
        except (RequestsJSONDecodeError, json.JSONDecodeError) as exc:
            logger.error(
                "[%s] Challenge sırasında JSON parse hatası (session bozulmuş olabilir): %s\n%s",
                username,
                exc,
                traceback.format_exc(),
            )
            session_file.unlink(missing_ok=True)
            raise HTTPException(
                status_code=403,
                detail=(
                    "Instagram güvenlik doğrulaması (Challenge) yanıtı okunamadı. "
                    "Eski session silindi. Lütfen Instagram uygulamasını veya web'i "
                    "açarak şüpheli giriş uyarısını ('Bendim' diyerek) onaylayıp "
                    "tekrar Login butonuna basın."
                ),
            )
        except UnknownError as exc:
            err_msg = str(exc)
            logger.error(
                "[%s] Instagram hesap hatası (session ile): %s\n%s",
                username,
                err_msg,
                traceback.format_exc(),
            )
            session_file.unlink(missing_ok=True)
            if "invalid_credentials" in err_msg.lower() or "can't find" in err_msg.lower() or "invalid_user" in err_msg.lower():
                raise HTTPException(
                    status_code=401,
                    detail=f"Instagram hesabı bulunamadı veya bilgiler hatalı: {username}. "
                    "Kullanıcı adını kontrol edin.",
                )
            raise HTTPException(
                status_code=401,
                detail=f"Instagram giriş hatası ({username}): {err_msg}",
            )
        except Exception as exc:
            logger.error(
                "[%s] Session ile giriş başarısız: %s\n%s",
                username,
                exc,
                traceback.format_exc(),
            )
            err_msg = str(exc)
            # Session dosyası bozuk olabilir, bir sonraki denemede temiz başla
            session_file.unlink(missing_ok=True)
            # invalid_credentials hatalarını 500 yerine düzgün döndür
            if "invalid_credentials" in err_msg.lower() or "can't find" in err_msg.lower() or "invalid_user" in err_msg.lower():
                raise HTTPException(
                    status_code=401,
                    detail=f"Instagram hesabı bulunamadı veya bilgiler hatalı: {username}. "
                    "Kullanıcı adını kontrol edin.",
                )

    # ── 2) Session yoksa / başarısızsa → şifre ile login ──
    if not login_via_session:
        try:
            logger.info(
                "[%s] Şifre ile yeni giriş yapılıyor…", username
            )
            cl = Client()
            cl.delay_range = [2, 5]
            cl.login(username, password)
            login_via_pw = True
            logger.info("[%s] ✅ Şifre ile giriş başarılı.", username)

        except BadPassword:
            raise HTTPException(status_code=401, detail=f"Hatalı şifre: {username}")
        except TwoFactorRequired:
            raise HTTPException(
                status_code=403,
                detail=f"2FA doğrulaması gerekli: {username}",
            )
        except ChallengeRequired as exc:
            logger.error(
                "[%s] Instagram challenge istiyor (şifre ile): %s\n%s",
                username,
                exc,
                traceback.format_exc(),
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Instagram güvenlik doğrulaması (Challenge) istiyor: {username}. "
                    "Lütfen Instagram uygulamasını veya web'i açarak 'Bendim' diyerek "
                    "onaylayın, ardından tekrar deneyin."
                ),
            )
        except (RequestsJSONDecodeError, json.JSONDecodeError) as exc:
            logger.error(
                "[%s] Login sırasında JSON parse hatası (challenge sayfası boş yanıt döndü): %s\n%s",
                username,
                exc,
                traceback.format_exc(),
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    "Instagram güvenlik doğrulaması (Challenge) yanıtı okunamadı. "
                    "Lütfen Instagram uygulamasını veya web'i açarak şüpheli giriş "
                    "uyarısını ('Bendim' diyerek) onaylayıp tekrar Login butonuna basın."
                ),
            )
        except UnknownError as exc:
            err_msg = str(exc)
            logger.error(
                "[%s] Instagram hesap hatası: %s\n%s",
                username,
                err_msg,
                traceback.format_exc(),
            )
            # "invalid_credentials" veya "invalid_user" gibi hataları yakala
            if "invalid_credentials" in err_msg.lower() or "can't find" in err_msg.lower() or "invalid_user" in err_msg.lower():
                raise HTTPException(
                    status_code=401,
                    detail=f"Instagram hesabı bulunamadı veya bilgiler hatalı: {username}. "
                    "Kullanıcı adını kontrol edin.",
                )
            raise HTTPException(
                status_code=401,
                detail=f"Instagram giriş hatası ({username}): {err_msg}",
            )
        except Exception as exc:
            logger.error(
                "[%s] Login hatası: %s\n%s",
                username,
                exc,
                traceback.format_exc(),
            )
            err_msg = str(exc)
            # UnknownError olarak yakalanmamış ama invalid_credentials içeren hatalar
            if "invalid_credentials" in err_msg.lower() or "can't find" in err_msg.lower() or "invalid_user" in err_msg.lower():
                raise HTTPException(
                    status_code=401,
                    detail=f"Instagram hesabı bulunamadı veya bilgiler hatalı: {username}. "
                    "Kullanıcı adını kontrol edin.",
                )
            raise HTTPException(
                status_code=500,
                detail=f"Login hatası: {type(exc).__name__}: {exc}",
            )

    if not login_via_session and not login_via_pw:
        raise HTTPException(
            status_code=500,
            detail=f"Hesaba giriş yapılamadı: {username}. Session ve şifre ile denendi.",
        )

    # ── 3) Session'ı kaydet ──
    try:
        cl.dump_settings(session_file)
        logger.debug("[%s] Session dosyası kaydedildi.", username)
    except Exception as exc:
        logger.warning("[%s] Session dosyası kaydedilemedi: %s", username, exc)

    return cl


# ---------------------------------------------------------------------------
# API — Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# API — Auth (register / login / logout / me)
# ---------------------------------------------------------------------------


@app.post("/api/auth/register")
def register(req: RegisterRequest, response: Response):
    """Yeni kullanıcı kaydı (ilk kullanımda veya ek kullanıcı için)."""
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Kullanıcı adı ve şifre zorunlu.")
    users = _load_users()
    for u in users.users:
        if u.username.lower() == req.username.lower():
            raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten kayıtlı.")
    token = secrets.token_urlsafe(32)
    new_user = AppUser(
        id=str(uuid.uuid4()),
        username=req.username,
        hashed_password=_hash_password(req.password),
        session_token=token,
        password_hint=req.password_hint.strip() if req.password_hint and req.password_hint.strip() else None,
    )
    users.users.append(new_user)
    _save_users(users)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 gün
    )
    return {"ok": True, "username": new_user.username}


@app.post("/api/auth/login")
def app_login(req: AppLoginRequest, response: Response):
    """Kullanıcı girişi — session cookie set eder."""
    users = _load_users()
    user = next((u for u in users.users if u.username.lower() == req.username.lower()), None)
    if not user or not _check_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı.")
    token = secrets.token_urlsafe(32)
    user.session_token = token
    _save_users(users)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True, "username": user.username}


@app.get("/api/auth/hint")
def get_password_hint(username: str):
    """Kullanıcının şifre sıfırlama ipucu var mı kontrol et."""
    users = _load_users()
    user = next((u for u in users.users if u.username.lower() == username.lower()), None)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    if not user.password_hint:
        raise HTTPException(
            status_code=404,
            detail="Bu kullanıcı için şifre ipucu tanımlanmamış.",
        )
    return {"has_hint": True, "username": user.username}


@app.post("/api/auth/reset-password")
def reset_password(req: ResetPasswordRequest, response: Response):
    """Şifre ipucuyla şifre sıfırlama."""
    if not req.username or not req.password_hint or not req.new_password:
        raise HTTPException(status_code=400, detail="Tüm alanlar zorunlu.")
    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 4 karakter olmalı.")
    users = _load_users()
    user = next((u for u in users.users if u.username.lower() == req.username.lower()), None)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    if not user.password_hint:
        raise HTTPException(
            status_code=400,
            detail="Bu kullanıcı için şifre ipucu tanımlanmamış. Sıfırlama yapılamaz.",
        )
    if user.password_hint.strip().lower() != req.password_hint.strip().lower():
        raise HTTPException(status_code=401, detail="Şifre ipucu yanlış.")
    user.hashed_password = _hash_password(req.new_password)
    token = secrets.token_urlsafe(32)
    user.session_token = token
    _save_users(users)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True, "username": user.username}


@app.post("/api/auth/logout")
def app_logout(response: Response, ig_session: str | None = Cookie(default=None)):
    """Oturumu sonlandır — cookie sil ve tokeni geçersiz kıl."""
    if ig_session:
        users = _load_users()
        for u in users.users:
            if u.session_token and secrets.compare_digest(u.session_token, ig_session):
                u.session_token = None
                _save_users(users)
                break
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(ig_session: str | None = Cookie(default=None)):
    """Mevcut oturumu kontrol et."""
    if not ig_session:
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    users = _load_users()
    for u in users.users:
        if u.session_token and secrets.compare_digest(u.session_token, ig_session):
            return {"username": u.username, "id": u.id}
    raise HTTPException(status_code=401, detail="Geçersiz oturum.")


@app.get("/api/auth/setup")
def auth_setup():
    """İlk kurulum gerekiyor mu? (hiç kullanıcı yoksa True döner)"""
    users = _load_users()
    return {"needs_setup": len(users.users) == 0}


# ---------------------------------------------------------------------------
# API — Account CRUD
# ---------------------------------------------------------------------------


@app.get("/api/accounts")
def get_accounts(ig_session: str | None = Cookie(default=None)):
    """Tüm hesapları listele (şifreler maskelenir)."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)
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
def add_account(req: AddAccountRequest, ig_session: str | None = Cookie(default=None)):
    """Yeni hesap ekle."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)

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
def delete_account(account_id: str, ig_session: str | None = Cookie(default=None)):
    """Hesabı sil."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)

    # Silinecek hesabın username'ini bul (session dosyasını da silmek için)
    acc_to_del = next((a for a in config.accounts if a.id == account_id), None)
    config.accounts = [a for a in config.accounts if a.id != account_id]
    _save_config(config)

    if acc_to_del:
        sf = SESSIONS_DIR / f"{acc_to_del.username}.json"
        sf.unlink(missing_ok=True)

    return {"ok": True}


# ---------------------------------------------------------------------------
# API — Login & Groups
# ---------------------------------------------------------------------------


@app.post("/api/accounts/{account_id}/login")
def login_account(account_id: str, ig_session: str | None = Cookie(default=None)):
    """Hesaba giriş yap ve durumunu güncelle."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)
    acc = _find_account(config, account_id)

    _get_client(acc.username, acc.password)
    acc.logged_in = True
    _save_config(config)

    return {"ok": True, "username": acc.username}


@app.get("/api/accounts/{account_id}/groups")
def list_groups(account_id: str, ig_session: str | None = Cookie(default=None)):
    """Hesaptaki tüm grup thread'lerini listele."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)
    acc = _find_account(config, account_id)

    cl = _get_client(acc.username, acc.password)
    acc.logged_in = True
    _save_config(config)

    try:
        threads = cl.direct_threads(amount=100)
    except Exception as exc:
        logger.error("Grup listeleme hatası (%s): %s", acc.username, str(exc))
        if "403 Client Error" in str(exc) or "Forbidden" in str(exc):
            acc.logged_in = False
            _save_config(config)
            raise HTTPException(
                status_code=401,
                detail="Instagram isteği reddetti (403 Forbidden) veya oturum geçersiz. "
                "Hesabınıza web/mobil'den girip uyarı varsa onaylayın ve tekrar Login yapın.",
            )
        raise HTTPException(status_code=500, detail=f"Gruplar alınamadı: {str(exc)}")

    group_threads = [t for t in threads if len(t.users) > 1]
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
def save_selected_groups(account_id: str, req: SaveGroupsRequest, ig_session: str | None = Cookie(default=None)):
    """Hesap için seçili grupları kaydet."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)
    acc = _find_account(config, account_id)
    acc.selected_groups = req.groups
    _save_config(config)
    return {"ok": True, "count": len(req.groups)}


# ---------------------------------------------------------------------------
# API — Send
# ---------------------------------------------------------------------------


def _is_instagram_url(url: str) -> bool:
    """Verilen URL bir Instagram gönderisi mi?"""
    return bool(re.search(r"instagram\.com/(p|reel|tv)/", url))


def _send_to_thread(
    cl: "Client",
    thread_id: str,
    link: str,
    message: str | None,
    media_pk: int | None,
) -> tuple[int | None, str]:
    """
    Bir thread'e link + opsiyonel mesaj gönder.

    Instagram gönderisi ise media_share dener; başarısız olursa veya
    Instagram dışı bir link ise düz metin olarak gönderir.

    Returns:
        (güncellenmiş media_pk, method_used)
    """
    method_used = "text"

    # ── Instagram gönderisi ise media_share dene ──
    if _is_instagram_url(link):
        if media_pk is None:
            try:
                media_pk = cl.media_pk_from_url(link)
                logger.debug("Media PK çözümlendi: %s → %s", link, media_pk)
            except Exception as exc:
                logger.warning(
                    "media_pk_from_url başarısız, düz link gönderiliyor: %s", exc
                )
                media_pk = None

        if media_pk is not None:
            try:
                # direct_media_share thread_ids desteklemiyor, user_ids istiyor.
                # Bu yüzden thread üyelerini alıp user_ids ile gönderiyoruz.
                # NOT: Bu yeni bir thread oluşturabilir; sorun olursa fallback'e düşer.
                thread = cl.direct_thread(int(thread_id), amount=1)
                user_ids = [int(u.pk) for u in thread.users]
                if not user_ids:
                    raise ValueError("Thread'de kullanıcı bulunamadı")

                cl.direct_media_share(
                    media_id=str(media_pk),
                    user_ids=user_ids,
                )
                method_used = "media_share"
                logger.debug(
                    "Media share gönderildi (thread_id=%s, media_pk=%s)",
                    thread_id,
                    media_pk,
                )
            except Exception as exc:
                logger.warning(
                    "direct_media_share başarısız (%s), düz link gönderiliyor: %s",
                    type(exc).__name__,
                    exc,
                )
                # Fallback: düz link olarak thread'e gönder
                cl.direct_send(text=link, thread_ids=[int(thread_id)])
                method_used = "text_fallback"
        else:
            # media_pk alınamadı, düz link gönder
            cl.direct_send(text=link, thread_ids=[int(thread_id)])
            method_used = "text"
    else:
        # Instagram dışı link (YouTube, Twitter vb.) — düz metin olarak gönder
        cl.direct_send(text=link, thread_ids=[int(thread_id)])
        method_used = "text"

    # ── Opsiyonel mesaj ──
    if message and message.strip():
        time.sleep(1)
        cl.direct_send(text=message.strip(), thread_ids=[int(thread_id)])

    return media_pk, method_used


@app.post("/api/send", response_model=SendResponse)
def send_link(req: SendRequest, ig_session: str | None = Cookie(default=None)):
    """Seçili hesap(lar)ın seçili gruplarına link gönder."""
    current_user = _get_current_user(ig_session)
    config = _load_config(current_user.id)

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

        # media_pk hesap başına tek sefer çözümlenir (her grup için tekrar istek atmaz)
        media_pk: int | None = None
        results: list[GroupResult] = []

        for idx, group in enumerate(acc.selected_groups):
            try:
                media_pk, method = _send_to_thread(
                    cl=cl,
                    thread_id=group.thread_id,
                    link=req.link,
                    message=req.message,
                    media_pk=media_pk,
                )
                logger.info(
                    "✅ [%s] → %s (%s)", acc.username, group.thread_title, method
                )
                results.append(
                    GroupResult(
                        thread_id=group.thread_id,
                        group=group.thread_title,
                        status="ok",
                        message=f"method={method}",
                    )
                )
            except Exception as exc:
                logger.error(
                    "❌ [%s] → %s: %s\n%s",
                    acc.username,
                    group.thread_title,
                    exc,
                    traceback.format_exc(),
                )
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
