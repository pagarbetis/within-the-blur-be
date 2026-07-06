from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR: Path = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import os
import logging
import uuid
import bcrypt
import jwt
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta

from database import (
    init_db, get_db, engine,
    User, LoginAttempt, JournalEntry, KuisResult, CekDiriEntry,
)

# JWT
JWT_ALGORITHM = "HS256"
ACCESS_TTL = timedelta(minutes=60 * 24)  # 24 hours (audience remaja, less token expiry frustration)
REFRESH_TTL = timedelta(days=30)

PALETTE_KEYS = Literal[
    "terracotta", "mustard", "sage", "kabut", "senja", "ink"
]


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + ACCESS_TTL,
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + REFRESH_TTL,
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        key="access_token", value=access, httponly=True, secure=False,
        samesite="lax", max_age=int(ACCESS_TTL.total_seconds()), path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=int(REFRESH_TTL.total_seconds()), path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def user_public(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name or "",
        "profileColor": u.profile_color or "terracotta",
        "createdAt": u.created_at.isoformat() if isinstance(u.created_at, datetime) else u.created_at,
    }


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        result = await db.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# =================== Pydantic Models ===================
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileColorRequest(BaseModel):
    color: PALETTE_KEYS


class JournalCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    title: Optional[str] = Field(default=None, max_length=120)
    mood: Optional[str] = Field(default=None, max_length=40)
    # Letter-from-future: ISO date string when this entry unlocks. If null, always visible.
    unlockAt: Optional[str] = Field(default=None, description="ISO datetime string, opsional")


class KuisResultCreate(BaseModel):
    dominant: Literal["chimp", "human", "computer"]
    counts: dict = Field(default_factory=dict)


class CekDiriCreate(BaseModel):
    feeling: str = Field(..., min_length=1, max_length=40)
    note: Optional[str] = Field(default=None, max_length=2000)


# =================== FastAPI ===================
app: FastAPI = FastAPI()
api_router: APIRouter = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger: logging.Logger = logging.getLogger(__name__)


# ---------- Health ----------
@api_router.get("/")
async def root():
    return {"message": "Within the Blur API"}


# ---------- Auth ----------
@api_router.post("/auth/register")
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar. Coba login.")
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        profile_color="terracotta",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    access = create_access_token(user.id, email)
    refresh = create_refresh_token(user.id)
    set_auth_cookies(response, access, refresh)
    return {"user": user_public(user), "access_token": access}


@api_router.post("/auth/login")
async def login(payload: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    identifier = f"{request.client.host}:{email}"
    now = datetime.now(timezone.utc)

    lock = (await db.execute(select(LoginAttempt).where(LoginAttempt.identifier == identifier))).scalar_one_or_none()
    if lock and lock.locked_until and lock.locked_until > now:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan. Coba lagi dalam 15 menit.")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        attempts = (lock.attempts if lock else 0) + 1
        if lock is None:
            lock = LoginAttempt(id=str(uuid.uuid4()), identifier=identifier, attempts=0)
            db.add(lock)
        lock.attempts = attempts
        lock.last_attempt = now
        if attempts >= 5:
            lock.locked_until = now + timedelta(minutes=15)
            lock.attempts = 0
        await db.commit()
        raise HTTPException(status_code=401, detail="Email atau password salah.")

    # success — clear attempts, issue tokens
    if lock is not None:
        await db.execute(delete(LoginAttempt).where(LoginAttempt.identifier == identifier))
        await db.commit()

    access = create_access_token(user.id, email)
    refresh = create_refresh_token(user.id)
    set_auth_cookies(response, access, refresh)
    return {"user": user_public(user), "access_token": access}


@api_router.post("/auth/logout")
async def logout(response: Response, user: User = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": user_public(user)}


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        result = await db.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(user.id, user.email)
        response.set_cookie(
            key="access_token", value=access, httponly=True, secure=False,
            samesite="lax", max_age=int(ACCESS_TTL.total_seconds()), path="/",
        )
        return {"user": user_public(user), "access_token": access}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# ---------- Profile ----------
@api_router.patch("/profile/color")
async def update_profile_color(
    payload: ProfileColorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.profile_color = payload.color
    await db.commit()
    return {"user": user_public(user)}


# ---------- Journal (auth required) ----------
def _validate_unlock_at(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Tanggal buka surat harus di masa depan.")
        if dt > datetime.now(timezone.utc) + timedelta(days=365 * 3):
            raise HTTPException(status_code=400, detail="Maksimal 3 tahun dari sekarang.")
        return dt
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid.")


def _entry_to_dict(e: JournalEntry) -> dict:
    return {
        "id": e.id,
        "user_id": e.user_id,
        "title": e.title,
        "body": e.body,
        "mood": e.mood,
        "unlockAt": e.unlock_at.isoformat() if e.unlock_at else None,
        "createdAt": e.created_at.isoformat() if e.created_at else None,
    }


def _is_locked(entry: dict) -> bool:
    ua = entry.get("unlockAt")
    if not ua:
        return False
    try:
        dt = datetime.fromisoformat(ua.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


def _mask_locked_entry(entry: dict) -> dict:
    """Return entry, hiding body if still locked."""
    if _is_locked(entry):
        return {
            **{k: v for k, v in entry.items() if k not in ("body",)},
            "body": None,
            "locked": True,
        }
    return {**entry, "locked": False}


@api_router.post("/journal")
async def create_journal(
    payload: JournalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    unlock_dt = _validate_unlock_at(payload.unlockAt)
    entry = JournalEntry(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=(payload.title or "").strip() or "Tanpa Judul",
        body=payload.body.strip(),
        mood=(payload.mood or "tenang").strip(),
        unlock_at=unlock_dt,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    return {"entry": _mask_locked_entry(_entry_to_dict(entry))}


@api_router.get("/journal")
async def list_journal(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == user.id).order_by(JournalEntry.created_at.desc()).limit(500)
    )
    entries = [_mask_locked_entry(_entry_to_dict(e)) for e in result.scalars().all()]
    return {"entries": entries, "count": len(entries)}


@api_router.delete("/journal/{entry_id}")
async def delete_journal(entry_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        delete(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Entry tidak ditemukan")
    return {"ok": True}


# ---------- Kuis history ----------
@api_router.post("/kuis/result")
async def save_kuis(payload: KuisResultCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = KuisResult(
        id=str(uuid.uuid4()),
        user_id=user.id,
        dominant=payload.dominant,
        counts=payload.counts,
        created_at=datetime.now(timezone.utc),
    )
    db.add(result)
    await db.commit()
    return {
        "result": {
            "id": result.id,
            "user_id": result.user_id,
            "dominant": result.dominant,
            "counts": result.counts,
            "createdAt": result.created_at.isoformat(),
        }
    }


@api_router.get("/kuis/latest")
async def get_kuis_latest(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KuisResult).where(KuisResult.user_id == user.id).order_by(KuisResult.created_at.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"result": None}
    return {
        "result": {
            "id": row.id,
            "user_id": row.user_id,
            "dominant": row.dominant,
            "counts": row.counts,
            "createdAt": row.created_at.isoformat(),
        }
    }


# ---------- Cek Diri history ----------
@api_router.post("/cekdiri")
async def save_cekdiri(payload: CekDiriCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    entry = CekDiriEntry(
        id=str(uuid.uuid4()),
        user_id=user.id,
        feeling=payload.feeling,
        note=payload.note or "",
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    return {
        "entry": {
            "id": entry.id,
            "user_id": entry.user_id,
            "feeling": entry.feeling,
            "note": entry.note,
            "createdAt": entry.created_at.isoformat(),
        }
    }


@api_router.get("/cekdiri")
async def list_cekdiri(days: int = 7, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(CekDiriEntry)
        .where(CekDiriEntry.user_id == user.id, CekDiriEntry.created_at >= since)
        .order_by(CekDiriEntry.created_at.desc())
        .limit(500)
    )
    entries = [
        {
            "id": e.id,
            "user_id": e.user_id,
            "feeling": e.feeling,
            "note": e.note,
            "createdAt": e.created_at.isoformat(),
        }
        for e in result.scalars().all()
    ]
    return {"entries": entries, "count": len(entries)}


# ---------- Aggregated Stats (Streak + Mood Chart) ----------
DAY_LABELS_ID = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


def _day_key(dt: datetime) -> Optional[str]:
    try:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def _index_by_day(rows: list, field: str) -> tuple:
    """Return (set_of_day_keys, dict_of_day_key -> field_value_of_latest_entry)."""
    days = set()
    by_day: dict = {}
    for r in rows:
        k = _day_key(r.created_at)
        if not k:
            continue
        days.add(k)
        if k not in by_day:
            by_day[k] = getattr(r, field)
    return days, by_day


def _compute_streak(cek_days: set, today) -> tuple:
    current = 0
    d = today
    if today.strftime("%Y-%m-%d") not in cek_days:
        d = today - timedelta(days=1)
    while d.strftime("%Y-%m-%d") in cek_days:
        current += 1
        d = d - timedelta(days=1)

    longest = 0
    run = 0
    prev = None
    for k in sorted(cek_days):
        cur = datetime.strptime(k, "%Y-%m-%d").date()
        if prev is not None and (cur - prev).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        prev = cur
    return current, longest


def _build_chart(today, cek_by_day: dict, jur_by_day: dict) -> list:
    chart = []
    for i in range(6, -1, -1):
        d0 = today - timedelta(days=i)
        k = d0.strftime("%Y-%m-%d")
        mood = cek_by_day.get(k) or jur_by_day.get(k)
        if k in cek_by_day:
            source = "cekdiri"
        elif k in jur_by_day:
            source = "journal"
        else:
            source = None
        chart.append({"date": k, "label": DAY_LABELS_ID[d0.weekday()], "mood": mood, "source": source})
    return chart


@api_router.get("/stats")
async def user_stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return { streak: {current, longest, today}, chart: [7 days] }."""
    since_60 = datetime.now(timezone.utc) - timedelta(days=60)

    cek_rows = (await db.execute(
        select(CekDiriEntry).where(CekDiriEntry.user_id == user.id, CekDiriEntry.created_at >= since_60)
        .order_by(CekDiriEntry.created_at.desc()).limit(1000)
    )).scalars().all()
    jur_rows = (await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == user.id, JournalEntry.created_at >= since_60)
        .order_by(JournalEntry.created_at.desc()).limit(1000)
    )).scalars().all()

    cek_days, cek_by_day = _index_by_day(cek_rows, "feeling")
    _, jur_by_day = _index_by_day(jur_rows, "mood")

    today = datetime.now(timezone.utc).date()
    current, longest = _compute_streak(cek_days, today)
    chart = _build_chart(today, cek_by_day, jur_by_day)

    return {
        "streak": {
            "current": current,
            "longest": longest,
            "today": today.strftime("%Y-%m-%d") in cek_days,
        },
        "chart": chart,
    }


# ---------- Startup / Shutdown ----------
@app.on_event("startup")
async def startup_db():
    try:
        await init_db()
        logger.info("MySQL tables ensured.")
    except Exception as e:
        logger.error(f"Database init failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    await engine.dispose()


# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)
