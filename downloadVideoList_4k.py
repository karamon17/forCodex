import os
import re
import yt_dlp


def progress_hook(d):
    if d.get("status") == "downloading":
        percent = (d.get("_percent_str") or "").strip()
        speed = (d.get("_speed_str") or "").strip()
        eta = (d.get("_eta_str") or "").strip()
        print(f"🔄 {percent} | 🚀 {speed} | ⏳ {eta}", end="\r")
    elif d.get("status") == "finished":
        print("\n✅ Скачано. Склейка/обработка...")


def is_https(fmt: dict) -> bool:
    proto = (fmt.get("protocol") or "").lower()
    return proto.startswith("https")


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


# --- нормализация ссылок (должна быть ДО использования) ---
MD_LINK_RE = re.compile(
    r'^\s*\[(?P<text>.*?)\]\((?P<url>https?://[^)\s]+)\)\s*$',
    re.IGNORECASE
)

def normalize_url(s: str) -> str:
    s = (s or "").strip().strip('"').strip("'")

    # markdown: [text](url)
    m = MD_LINK_RE.match(s)
    if m:
        return m.group("url")

    # если кто-то вставил просто "(url)" или "<url>"
    s = s.strip("<>").strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()

    # иногда копируют с лишним хвостом типа ")"
    s = s.rstrip(").,;")

    # добавить схему, если вставили "youtube.com/shorts/..." или "youtu.be/..."
    if s.startswith(("youtube.com", "www.youtube.com", "youtu.be")):
        s = "https://" + s

    return s
# --- конец нормализации ---


def pick_best_formats(formats: list[dict], max_height: int):
    """
    Возвращает (video_id, audio_id, progressive_id)

    Приоритет:
      1) video-only (mp4/webm, https) <= max_height + audio-only (m4a, https)
      2) progressive (mp4, https) <= max_height
      3) None/None/None
    """
    BANNED_VCODECS = ("av01", "av1")

    video_candidates = []
    audio_candidates = []
    progressive_candidates = []

    for f in formats or []:
        ext = (f.get("ext") or "").lower()
        vcodec = (f.get("vcodec") or "none").lower()
        acodec = (f.get("acodec") or "none").lower()
        height = safe_int(f.get("height"), 0)

        if not is_https(f):
            continue

        if any(b in vcodec for b in BANNED_VCODECS):
            continue

        # video-only: mp4 или webm (vp9 для 4K часто webm)
        if ext in ("mp4", "webm") and vcodec != "none" and acodec == "none":
            if height == 0 or height <= max_height:
                video_candidates.append((height, safe_int(f.get("tbr"), 0), f.get("format_id")))

        # audio-only m4a
        if ext == "m4a" and acodec != "none" and vcodec == "none":
            abr = safe_int(f.get("abr"), 0)
            tbr = safe_int(f.get("tbr"), 0)
            audio_candidates.append((abr, tbr, f.get("format_id")))

        # progressive mp4
        if ext == "mp4" and vcodec != "none" and acodec != "none":
            if height == 0 or height <= max_height:
                progressive_candidates.append((height, safe_int(f.get("tbr"), 0), f.get("format_id")))

    video_id = audio_id = progressive_id = None

    if video_candidates:
        video_candidates.sort(reverse=True)
        video_id = video_candidates[0][2]

    if audio_candidates:
        audio_candidates.sort(reverse=True)
        audio_id = audio_candidates[0][2]

    if progressive_candidates:
        progressive_candidates.sort(reverse=True)
        progressive_id = progressive_candidates[0][2]

    return video_id, audio_id, progressive_id


def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip().strip(".")


# ================== НАСТРОЙКИ ==================
urls = [
"[https://youtu.be/gY6TfBx_Itc](https://youtu.be/gY6TfBx_Itc)", "[https://youtu.be/YivjioY8b7M](https://youtu.be/YivjioY8b7M)", "[https://youtu.be/A1SI3dXeMCk](https://youtu.be/A1SI3dXeMCk)", "[https://www.youtube.com/shorts/aQqJcMEyYOE](https://www.youtube.com/shorts/aQqJcMEyYOE)", "[https://youtu.be/blIaGmKXIz8](https://youtu.be/blIaGmKXIz8)", "[https://www.youtube.com/shorts/HcG7M0Tk2b8](https://www.youtube.com/shorts/HcG7M0Tk2b8)", "[https://www.youtube.com/shorts/ZWFUCjsSTPU](https://www.youtube.com/shorts/ZWFUCjsSTPU)", "[https://youtu.be/79uIiW0qTWo](https://youtu.be/79uIiW0qTWo)", "[https://youtu.be/r5YsdH3MyPw](https://youtu.be/r5YsdH3MyPw)", "[https://www.youtube.com/shorts/At98S0UvzW4](https://www.youtube.com/shorts/At98S0UvzW4)", "[https://www.youtube.com/shorts/JlR2dDzVGMY](https://www.youtube.com/shorts/JlR2dDzVGMY)", "[https://youtu.be/ob159ts1oQA](https://youtu.be/ob159ts1oQA)", "[https://youtu.be/vBIKaa6_rTA](https://youtu.be/vBIKaa6_rTA)", "[https://youtu.be/SZ2eL-JmmpE](https://youtu.be/SZ2eL-JmmpE)", "[https://youtu.be/rKtOw4JazDw](https://youtu.be/rKtOw4JazDw)", "[https://youtu.be/d8cVrwv8wf0](https://youtu.be/d8cVrwv8wf0)", "[https://youtu.be/PkcCcdaeEBY](https://youtu.be/PkcCcdaeEBY)", "[https://youtu.be/YUbqPUNBx0Q](https://youtu.be/YUbqPUNBx0Q)", "[https://youtu.be/S6h9RyYgr2s](https://youtu.be/S6h9RyYgr2s)", "[https://youtu.be/wSUZoHjWFgo](https://youtu.be/wSUZoHjWFgo)", "[https://www.youtube.com/shorts/1cEcEQUnmgM](https://www.youtube.com/shorts/1cEcEQUnmgM)", "[https://youtu.be/TjDUqlBILy8](https://youtu.be/TjDUqlBILy8)", "[https://youtu.be/XQPbs77mIgI](https://youtu.be/XQPbs77mIgI)", "[https://youtu.be/nVk4neH9_3Q](https://youtu.be/nVk4neH9_3Q)", "[https://youtu.be/bFzP39j7QR0](https://youtu.be/bFzP39j7QR0)", "[https://youtu.be/pa-7FLK4Npw](https://youtu.be/pa-7FLK4Npw)", "[https://youtu.be/ry5-UJw8Qn8](https://youtu.be/ry5-UJw8Qn8)", "[https://youtu.be/gg-TRwWq0rs](https://youtu.be/gg-TRwWq0rs)", "[https://youtu.be/zj56m49REP0](https://youtu.be/zj56m49REP0)", "[https://youtu.be/m0u8e14vIpU](https://youtu.be/m0u8e14vIpU)", "[https://www.youtube.com/shorts/44sBAJD9xTE](https://www.youtube.com/shorts/44sBAJD9xTE)", "[https://youtu.be/Wc2q6xF3JTg](https://youtu.be/Wc2q6xF3JTg)", "[https://youtu.be/sH2DE7VdFlE](https://youtu.be/sH2DE7VdFlE)", "[https://youtu.be/KWvnNxw_alA](https://youtu.be/KWvnNxw_alA)", "[https://youtu.be/WD6lroSm5To](https://youtu.be/WD6lroSm5To)", "[https://youtu.be/dsczgz61ib0](https://youtu.be/dsczgz61ib0)", "[https://youtu.be/H1ZkVG4Ocus](https://youtu.be/H1ZkVG4Ocus)", "[https://youtu.be/9JkPxJnwpEw](https://youtu.be/9JkPxJnwpEw)", "[https://youtu.be/aWF7jq8wR2w](https://youtu.be/aWF7jq8wR2w)", "[https://youtu.be/c4IuahDiLTs](https://youtu.be/c4IuahDiLTs)", "[https://youtu.be/DS-79TrNCoE](https://youtu.be/DS-79TrNCoE)", "[https://youtu.be/Xaz8eCzqtIE](https://youtu.be/Xaz8eCzqtIE)"
]

# ✅ нормализуем список ссылок (без двойного вызова)
norm_urls = []
for u in urls:
    nu = normalize_url(u)
    if nu:
        norm_urls.append(nu)
urls = norm_urls

COOKIES_PATH = r"d:\youtube\need things\cookies.txt"
OUT_DIR = r"d:\youtube\СНИ\Kurzhaar and draghaar\materials"
MAX_HEIGHT = 2160
VERBOSE = False
# =================================================


os.makedirs(OUT_DIR, exist_ok=True)

base_opts = {
    # YouTube JS challenge (n-param) solving via node + remote ejs component.
    "js_runtimes": {"node": {}},
    "remote_components": ["ejs:github"],

    "merge_output_format": "mkv",
    "progress_hooks": [progress_hook],

    "retries": 20,
    "fragment_retries": 50,
    "concurrent_fragment_downloads": 1,

    "quiet": not VERBOSE,
    "no_warnings": False,
}

if COOKIES_PATH:
    base_opts["cookiefile"] = COOKIES_PATH


def download_url(url: str, index: int, total: int):
    print(f"\n\n===== ({index}/{total}) {url} =====")

    extract_opts = dict(base_opts)
    extract_opts["skip_download"] = True

    with yt_dlp.YoutubeDL(extract_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = sanitize_filename(info.get("title") or f"video_{index}")
    formats = info.get("formats") or []
    v_id, a_id, p_id = pick_best_formats(formats, max_height=MAX_HEIGHT)

    if v_id and a_id:
        chosen_format = f"{v_id}+{a_id}"
        print(f"🎯 Выбрано: video={v_id} + audio={a_id} (<= {MAX_HEIGHT}p)")
    elif p_id:
        chosen_format = p_id
        print(f"🎯 Выбрано: progressive mp4={p_id} (<= {MAX_HEIGHT}p)")
    else:
        chosen_format = f"bestvideo[height<={MAX_HEIGHT}][vcodec!*=av01][vcodec!*=av1]+bestaudio[ext=m4a]/best[height<={MAX_HEIGHT}]"
        print("⚠️ Не нашёл подходящие форматы по списку — качаю через fallback selector")

    dl_opts = dict(base_opts)
    dl_opts["format"] = chosen_format
    dl_opts["outtmpl"] = os.path.join(OUT_DIR, f"{title}.%(ext)s")

    with yt_dlp.YoutubeDL(dl_opts) as ydl:
        ydl.download([url])

    print("✅ Готово:", title)


total = len(urls)
ok = 0
fail = 0

for i, u in enumerate(urls, start=1):
    try:
        download_url(u, i, total)
        ok += 1
    except Exception as e:
        fail += 1
        print(f"\n❌ Ошибка на {u}\n{repr(e)}")

print(f"\n\nИтог: ✅ {ok} | ❌ {fail} | всего {total}")
