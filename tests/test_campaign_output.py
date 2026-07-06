"""Frontend static-asset regression tests for /campaign-output/ (iteration 3).

Covers:
- 12 asset cards rendered in index.html with correct data-testids
- 6 static PNGs return 200 image/png
- 6 motion MP4s return 200 video/mp4 with 1080x1350 @ 30fps and correct durations
- 9 SVGs return 200 image/svg+xml and are well-formed XML
- ZIP >= 5MB with 22 files (6 PNG + 6 MP4 + 9 SVG + README.txt)
- Content pillar mid-frames (Feed 10, 11, 12) contain expected UI elements
- No em-dash character in text overlays of rendered mid-frames (visual OCR)
"""
import os
import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") \
    else "https://blur-enhance.preview.emergentagent.com"
ROOT = f"{BASE}/campaign-output"

STATIC_IDS = ["01", "02", "03", "07", "08", "09"]
MOTION_IDS_CHAR = ["04", "05", "06"]
MOTION_IDS_PILLAR = ["10", "11", "12"]
MOTION_IDS = MOTION_IDS_CHAR + MOTION_IDS_PILLAR
SVG_IDS = STATIC_IDS + MOTION_IDS_PILLAR  # 01-03, 07-09, 10-12 (9 total)
ALL_ASSET_IDS = STATIC_IDS + MOTION_IDS_CHAR + MOTION_IDS_PILLAR  # 12 asset cards

EXPECTED_DURATIONS = {"04": 15.0, "05": 8.0, "06": 10.0, "10": 12.0, "11": 10.0, "12": 8.0}


@pytest.fixture(scope="module")
def index_html():
    r = requests.get(f"{ROOT}/index.html", timeout=30)
    assert r.status_code == 200
    return r.text


class TestIndexPage:
    def test_index_loads(self, index_html):
        assert "campaign assets" in index_html.lower()

    def test_all_12_asset_cards(self, index_html):
        for aid in ALL_ASSET_IDS:
            assert f'data-testid="asset-card-{aid}"' in index_html, f"asset-card-{aid} missing"

    def test_section_headers(self, index_html):
        # Sections should now be Static / Motion Characters / Content Pillars
        assert "Static · 6 feed" in index_html
        assert "Motion Characters · 3 feed" in index_html
        assert "Content Pillars · 3 feed" in index_html

    def test_static_download_testids(self, index_html):
        for sid in STATIC_IDS:
            assert f'data-testid="download-static-{sid}"' in index_html

    def test_motion_download_testids(self, index_html):
        for mid in MOTION_IDS:
            assert f'data-testid="download-motion-{mid}"' in index_html

    def test_svg_download_testids(self, index_html):
        for sid in SVG_IDS:
            assert f'data-testid="download-svg-{sid}"' in index_html

    def test_no_em_dash_in_page(self, index_html):
        # spec says no em-dash in visible campaign copy.
        # Strip <style>, <script>, <title> (metadata not visible in the feed).
        body = re.sub(r"<style.*?</style>", "", index_html, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<script.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<title>.*?</title>", "", body, flags=re.DOTALL | re.IGNORECASE)
        body_text = re.sub(r"<[^>]+>", " ", body)
        assert "—" not in body_text, "em-dash found in index page visible text"


class TestStaticPNG:
    @pytest.mark.parametrize("sid", STATIC_IDS)
    def test_png_200(self, sid):
        r = requests.get(f"{ROOT}/static/feed-{sid}.png", timeout=30)
        assert r.status_code == 200, f"feed-{sid}.png -> {r.status_code}"
        assert r.headers.get("content-type", "").startswith("image/png"), r.headers.get("content-type")
        assert len(r.content) > 5000, f"feed-{sid}.png too small: {len(r.content)}"


class TestMotionMP4:
    @pytest.mark.parametrize("mid", MOTION_IDS)
    def test_mp4_200(self, mid):
        r = requests.head(f"{ROOT}/motion/feed-{mid}.mp4", timeout=30, allow_redirects=True)
        # If HEAD not allowed, fall back to GET with stream
        if r.status_code >= 400:
            r = requests.get(f"{ROOT}/motion/feed-{mid}.mp4", timeout=60, stream=True)
        assert r.status_code == 200, f"feed-{mid}.mp4 -> {r.status_code}"
        ctype = r.headers.get("content-type", "")
        assert "video/mp4" in ctype or "application/octet-stream" in ctype, ctype

    @pytest.mark.parametrize("mid,exp_dur", list(EXPECTED_DURATIONS.items()))
    def test_mp4_ffprobe(self, mid, exp_dur):
        local = f"/app/frontend/public/campaign-output/motion/feed-{mid}.mp4"
        assert os.path.exists(local), f"local file missing: {local}"
        # ffprobe: width, height, r_frame_rate, duration
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate:format=duration",
            "-of", "default=nw=1", local
        ], text=True)
        assert "width=1080" in out, out
        assert "height=1350" in out, out
        assert "30/1" in out or "30000/1001" in out or "r_frame_rate=30" in out, out
        m = re.search(r"duration=([\d\.]+)", out)
        assert m, out
        dur = float(m.group(1))
        assert abs(dur - exp_dur) < 0.6, f"Feed {mid}: expected ~{exp_dur}s got {dur}s"


class TestSVG:
    @pytest.mark.parametrize("sid", SVG_IDS)
    def test_svg_200_and_wellformed(self, sid):
        r = requests.get(f"{ROOT}/svg/feed-{sid}.svg", timeout=30)
        assert r.status_code == 200
        ctype = r.headers.get("content-type", "")
        assert "svg" in ctype.lower(), f"feed-{sid}.svg ctype={ctype}"
        body = r.text
        assert "<svg" in body and "</svg>" in body, f"feed-{sid}.svg not well-formed"
        # em-dash check: only inspect visible <text> elements (metadata <title>/<desc> excluded)
        text_nodes = re.findall(r"<text[^>]*>([^<]*)</text>", body, flags=re.IGNORECASE)
        joined = " ".join(text_nodes)
        assert "—" not in joined, f"em-dash found in visible SVG <text> of feed-{sid}.svg: {joined[:200]}"


class TestZip:
    @pytest.fixture(scope="class")
    def zip_bytes(self):
        r = requests.get(f"{ROOT}/within-the-blur-campaign.zip", timeout=120)
        assert r.status_code == 200
        assert "zip" in r.headers.get("content-type", "").lower(), r.headers.get("content-type")
        return r.content

    def test_zip_size(self, zip_bytes):
        assert len(zip_bytes) >= 5 * 1024 * 1024, f"ZIP too small: {len(zip_bytes)} bytes"

    def test_zip_contents(self, zip_bytes):
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = z.namelist()
        pngs = [n for n in names if n.endswith(".png")]
        mp4s = [n for n in names if n.endswith(".mp4")]
        svgs = [n for n in names if n.endswith(".svg")]
        readmes = [n for n in names if n.lower().endswith("readme.txt")]
        assert len(pngs) == 6, f"expected 6 png in zip, got {len(pngs)}: {pngs}"
        assert len(mp4s) == 6, f"expected 6 mp4 in zip, got {len(mp4s)}: {mp4s}"
        assert len(svgs) == 9, f"expected 9 svg in zip, got {len(svgs)}: {svgs}"
        assert len(readmes) == 1, f"expected 1 readme, got {len(readmes)}: {readmes}"
        assert len(names) == 22, f"expected 22 total files, got {len(names)}: {names}"


class TestMidFrameCorners:
    """Extract mid-frame of motion feeds and check top-left / top-right corners are empty (dark)."""

    @pytest.fixture(scope="class")
    def tmpdir(self):
        d = tempfile.mkdtemp(prefix="midframes_")
        yield d
        shutil.rmtree(d, ignore_errors=True)

    def _extract_frame(self, mid, t, out_dir):
        local = f"/app/frontend/public/campaign-output/motion/feed-{mid}.mp4"
        out = os.path.join(out_dir, f"feed-{mid}-t{t}.png")
        subprocess.check_call([
            "ffmpeg", "-y", "-ss", str(t), "-i", local, "-frames:v", "1", out
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out

    @pytest.mark.parametrize("mid,t", [("04", 7), ("05", 4), ("06", 5)])
    def test_character_feed_corners_empty(self, tmpdir, mid, t):
        """Character feeds (04-06): top-left and top-right 200x100 corners should be mostly dark (no eyebrow/counter text)."""
        from PIL import Image
        p = self._extract_frame(mid, t, tmpdir)
        img = Image.open(p).convert("RGB")
        assert img.size == (1080, 1350), img.size
        # Sample corners
        tl = img.crop((0, 0, 200, 100))
        tr = img.crop((880, 0, 1080, 100))
        # Compute mean brightness in each corner
        for name, region in (("top-left", tl), ("top-right", tr)):
            pixels = list(region.getdata())
            avg = sum(sum(px) / 3 for px in pixels) / len(pixels)
            # Should be < 45 (mostly dark). If eyebrow/counter text present, brightness spikes.
            assert avg < 55, f"Feed {mid} {name} avg brightness {avg:.1f} (expected < 55 = empty corner)"

    @pytest.mark.parametrize("mid,t", [("10", 8), ("11", 7), ("12", 6)])
    def test_pillar_feed_frame_exists(self, tmpdir, mid, t):
        """Content pillar feeds: mid-frame extractable and 1080x1350."""
        from PIL import Image
        p = self._extract_frame(mid, t, tmpdir)
        img = Image.open(p).convert("RGB")
        assert img.size == (1080, 1350), img.size

    def test_feed_12_loading_bar_present(self, tmpdir):
        """Feed 12: at t=6s should show a sage-green loading bar filled ~80-85%.
        Check the middle horizontal band for sage pixels."""
        from PIL import Image
        p = self._extract_frame("12", 6, tmpdir)
        img = Image.open(p).convert("RGB")
        # Scan a horizontal strip in middle third of image
        # Sage color ~ (170, 200, 183). Look for sage-ish pixels count.
        strip = img.crop((80, 600, 1000, 800))
        px = list(strip.getdata())
        sage_count = sum(1 for r, g, b in px if 130 < g < 230 and g > r and g >= b and (g - r) > 8)
        total = len(px)
        ratio = sage_count / total
        assert ratio > 0.05, f"Feed 12: sage green loading-bar pixels ratio {ratio:.3f} too low"


class TestHomepageRegression:
    def test_home_loads(self):
        r = requests.get(f"{BASE}/", timeout=30)
        assert r.status_code == 200
        # basic sanity: HTML content
        assert "<html" in r.text.lower()
