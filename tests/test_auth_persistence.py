"""E2E backend tests for auth + journal + kuis + cekdiri + profile color."""
import os
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://blur-enhance.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def existing_user_session():
    """Log in with pre-seeded test user."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "test@withintheblur.id", "password": "Blur2026!"})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    data = r.json()
    assert "user" in data and "access_token" in data
    assert data["user"]["email"] == "test@withintheblur.id"
    return s, data


@pytest.fixture(scope="module")
def fresh_session():
    """Register a brand-new user for this run."""
    s = requests.Session()
    email = f"test2+{int(time.time())}@withintheblur.id"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Blur2026!", "name": "Fresh"})
    assert r.status_code == 200, f"register failed {r.status_code} {r.text}"
    data = r.json()
    assert data["user"]["email"] == email
    assert data["user"]["profileColor"] == "terracotta"
    return s, data


# ---------- health ----------
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert "Within the Blur" in r.json().get("message", "")


# ---------- auth ----------
def test_register_duplicate_email(existing_user_session):
    r = requests.post(f"{API}/auth/register", json={"email": "test@withintheblur.id", "password": "Blur2026!", "name": "X"})
    assert r.status_code == 400


def test_login_wrong_password():
    r = requests.post(f"{API}/auth/login", json={"email": "test@withintheblur.id", "password": "WRONG_pw_zzz"})
    assert r.status_code == 401


def test_me_requires_auth():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_me_with_session(existing_user_session):
    s, _ = existing_user_session
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "test@withintheblur.id"


def test_bearer_token_works(existing_user_session):
    _, data = existing_user_session
    token = data["access_token"]
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# ---------- profile color ----------
def test_update_profile_color_persist(existing_user_session):
    s, _ = existing_user_session
    r = s.patch(f"{API}/profile/color", json={"color": "sage"})
    assert r.status_code == 200
    assert r.json()["user"]["profileColor"] == "sage"
    # verify persisted
    r2 = s.get(f"{API}/auth/me")
    assert r2.json()["user"]["profileColor"] == "sage"
    # restore
    s.patch(f"{API}/profile/color", json={"color": "terracotta"})


def test_update_profile_color_invalid(existing_user_session):
    s, _ = existing_user_session
    r = s.patch(f"{API}/profile/color", json={"color": "neon"})
    assert r.status_code in (400, 422)


# ---------- journal ----------
def test_journal_crud(fresh_session):
    s, _ = fresh_session
    # create
    r = s.post(f"{API}/journal", json={"title": "TEST_title", "body": "hello world", "mood": "tenang"})
    assert r.status_code == 200
    entry = r.json()["entry"]
    assert entry["title"] == "TEST_title" and entry["body"] == "hello world"
    entry_id = entry["id"]
    # list
    r2 = s.get(f"{API}/journal")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1
    assert any(e["id"] == entry_id for e in r2.json()["entries"])
    # delete
    r3 = s.delete(f"{API}/journal/{entry_id}")
    assert r3.status_code == 200
    # verify gone
    r4 = s.get(f"{API}/journal")
    assert not any(e["id"] == entry_id for e in r4.json()["entries"])


def test_journal_requires_auth():
    r = requests.post(f"{API}/journal", json={"body": "no auth"})
    assert r.status_code == 401


# ---------- kuis ----------
def test_kuis_save_and_latest(fresh_session):
    s, _ = fresh_session
    r = s.post(f"{API}/kuis/result", json={"dominant": "human", "counts": {"human": 3, "chimp": 1, "computer": 1}})
    assert r.status_code == 200
    assert r.json()["result"]["dominant"] == "human"
    r2 = s.get(f"{API}/kuis/latest")
    assert r2.status_code == 200
    assert r2.json()["result"]["dominant"] == "human"


def test_kuis_invalid_dominant(fresh_session):
    s, _ = fresh_session
    r = s.post(f"{API}/kuis/result", json={"dominant": "alien", "counts": {}})
    assert r.status_code == 422


# ---------- cek diri ----------
def test_cekdiri_save_and_list(fresh_session):
    s, _ = fresh_session
    r = s.post(f"{API}/cekdiri", json={"feeling": "Tenang", "note": "test note"})
    assert r.status_code == 200
    assert r.json()["entry"]["feeling"] == "Tenang"
    r2 = s.get(f"{API}/cekdiri")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1


# ---------- logout ----------
def test_logout_clears_cookie(fresh_session):
    s, _ = fresh_session
    # verify authed
    assert s.get(f"{API}/auth/me").status_code == 200
    r = s.post(f"{API}/auth/logout")
    assert r.status_code == 200
    # after logout, cookie should be cleared
    s.cookies.clear()
    assert s.get(f"{API}/auth/me").status_code == 401
