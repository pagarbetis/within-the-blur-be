"""Tests for streak/chart /api/stats and letter-from-future journal locking."""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta

def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                os.environ.setdefault("REACT_APP_BACKEND_URL", line.split("=", 1)[1].strip())

_load_frontend_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
EMAIL = "test@withintheblur.id"
PASSWORD = "Blur2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# ---------- Stats ----------
def test_stats_shape(sess):
    r = sess.get(f"{BASE}/stats", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "streak" in d and "chart" in d
    s = d["streak"]
    assert set(s.keys()) >= {"current", "longest", "today"}
    assert isinstance(s["current"], int)
    assert isinstance(s["longest"], int)
    assert isinstance(s["today"], bool)
    assert isinstance(d["chart"], list) and len(d["chart"]) == 7
    for item in d["chart"]:
        assert set(item.keys()) >= {"date", "label", "mood", "source"}
        assert item["label"] in ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


def test_stats_today_reflects_cekdiri(sess):
    # Ensure user has at least one cekdiri today
    sess.post(f"{BASE}/cekdiri", json={"feeling": "Tenang", "note": "test today"}, timeout=15)
    r = sess.get(f"{BASE}/stats", timeout=15)
    d = r.json()
    assert d["streak"]["today"] is True
    assert d["streak"]["current"] >= 1
    assert d["streak"]["longest"] >= d["streak"]["current"]
    # last chart entry should be today with mood present from cekdiri
    today_key = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
    last = d["chart"][-1]
    assert last["date"] == today_key
    assert last["mood"] is not None
    assert last["source"] == "cekdiri"


# ---------- Letter from future / journal locking ----------
def test_journal_locked_hides_body(sess):
    unlock = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    r = sess.post(
        f"{BASE}/journal",
        json={"body": "Halo diri masa depan — secret content", "title": "Surat 30", "mood": "tenang", "unlockAt": unlock},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    entry = r.json()["entry"]
    assert entry["locked"] is True
    assert entry["body"] is None
    assert entry["unlockAt"]

    # List: still locked, body None
    r2 = sess.get(f"{BASE}/journal", timeout=15)
    assert r2.status_code == 200
    entries = r2.json()["entries"]
    matched = [e for e in entries if e.get("id") == entry["id"]]
    assert matched and matched[0]["locked"] is True and matched[0]["body"] is None

    # cleanup
    sess.delete(f"{BASE}/journal/{entry['id']}", timeout=15)


def test_journal_unlocked_regular(sess):
    r = sess.post(
        f"{BASE}/journal",
        json={"body": "regular body plain", "title": "reg", "mood": "tenang"},
        timeout=15,
    )
    assert r.status_code == 200
    entry = r.json()["entry"]
    assert entry["locked"] is False
    assert entry["body"] == "regular body plain"
    sess.delete(f"{BASE}/journal/{entry['id']}", timeout=15)


def test_journal_unlockAt_past_rejected(sess):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = sess.post(
        f"{BASE}/journal",
        json={"body": "x", "unlockAt": past},
        timeout=15,
    )
    assert r.status_code == 400


def test_journal_unlockAt_beyond_3_years_rejected(sess):
    far = (datetime.now(timezone.utc) + timedelta(days=365 * 4)).isoformat()
    r = sess.post(f"{BASE}/journal", json={"body": "x", "unlockAt": far}, timeout=15)
    assert r.status_code == 400


def test_journal_unlockAt_invalid_format(sess):
    r = sess.post(f"{BASE}/journal", json={"body": "x", "unlockAt": "not-a-date"}, timeout=15)
    assert r.status_code == 400
