import os
import sys
import yt_dlp


def progress_hook(d):
    if d.get("status") == "downloading":
        percent = (d.get("_percent_str") or "").strip()
        speed = (d.get("_speed_str") or "").strip()
        eta = (d.get("_eta_str") or "").strip()
        print(f"[DOWN] {percent} | {speed} | ETA {eta}", end="\r")
    elif d.get("status") == "finished":
        print("\n[OK] Скачано. Склейка/обработка...")


def is_supported_protocol(fmt: dict) -> bool:
    proto = (fmt.get("protocol") or "").lower()
    return proto.startswith("https") or proto.startswith("m3u8")


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def pick_best_formats(formats: list[dict], max_height: int):
    """
    Возвращает:
      (video_id, audio_id, progressive_id)

    Приоритет:
      1) video-only (mp4/webm, https/m3u8) <= max_height + audio-only (m4a, https/m3u8)
      2) progressive mp4 (https/m3u8) <= max_height
      3) None/None/None
    """
    BANNED_VCODECS = ("av01", "av1")  # не хотим AV1

    video_candidates = []
    audio_candidates = []
    progressive_candidates = []

    for f in formats or []:
        ext = (f.get("ext") or "").lower()
        vcodec = (f.get("vcodec") or "none").lower()
        acodec = (f.get("acodec") or "none").lower()
        height = safe_int(f.get("height"), 0)

        if not is_supported_protocol(f):
            continue

        if any(b in vcodec for b in BANNED_VCODECS):
            continue

        # ✅ video-only: разрешаем mp4 И webm (vp9 4K обычно webm)
        if ext in ("mp4", "webm") and vcodec != "none" and acodec == "none":
            if height == 0 or height <= max_height:
                video_candidates.append((height, safe_int(f.get("tbr"), 0), f.get("format_id")))

        # audio-only m4a
        if ext == "m4a" and acodec != "none" and vcodec == "none":
            abr = safe_int(f.get("abr"), 0)
            tbr = safe_int(f.get("tbr"), 0)
            audio_candidates.append((abr, tbr, f.get("format_id")))

        # progressive mp4 (на YouTube часто максимум 720/1080, но оставим как fallback)
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


# ================== НАСТРОЙКИ ==================
URL = "https://youtu.be/awMmB-dIgNU"

COOKIES_PATH = r"d:\youtube\need things\cookies.txt"   # если не нужно — поставь None
OUT_DIR = r"d:\youtube\СНИ\Kurzhaar and draghaar\materials"

MAX_HEIGHT = 2160   # ✅ 4K
VERBOSE = False
# =================================================


os.makedirs(OUT_DIR, exist_ok=True)

# Protect console output on Windows terminals that are not UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

base_opts = {
    # YouTube JS challenge (n-param) solving via node + remote ejs component.
    "js_runtimes": {"node": {}},
    "remote_components": ["ejs:github"],
    # Prefer clients that often avoid n-challenge failures.
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},

    "outtmpl": os.path.join(OUT_DIR, "%(title)s.%(ext)s"),

    # ✅ для 4K (vp9/webm) надёжнее мерджить в mkv
    "merge_output_format": "mkv",

    "progress_hooks": [progress_hook],

    # стабильность:
    "retries": 20,
    "fragment_retries": 50,
    "concurrent_fragment_downloads": 1,
    "source_address": "0.0.0.0",  # force IPv4, often helps with SSL EOF
    "socket_timeout": 30,
    "noplaylist": True,

    "quiet": not VERBOSE,
    "no_warnings": False,
}

if COOKIES_PATH:
    base_opts["cookiefile"] = COOKIES_PATH


# 1) Получаем форматы
extract_opts = dict(base_opts)
extract_opts["skip_download"] = True

with yt_dlp.YoutubeDL(extract_opts) as ydl:
    try:
        info = ydl.extract_info(URL, download=False, process=False)
    except yt_dlp.utils.DownloadError as e:
        raise SystemExit(
            "[ERROR] Не удалось получить форматы у YouTube. "
            "Проверь cookies и обнови cookies.txt."
        ) from e

formats = info.get("formats") or []
protocols = {(f.get("protocol") or "").lower() for f in formats}
if protocols == {"m3u8_native"}:
    print(
        "[INFO] YouTube отдал только m3u8-потоки. "
        "Обычно это bot-check / n-challenge: часть форматов недоступна."
    )
v_id, a_id, p_id = pick_best_formats(formats, max_height=MAX_HEIGHT)

# 2) Выбираем формат
if v_id and a_id:
    chosen_format = f"{v_id}+{a_id}"
    print(f"[PICK] Выбрано: video={v_id} + audio={a_id} (<= {MAX_HEIGHT}p)")
elif p_id:
    chosen_format = p_id
    print(f"[PICK] Выбрано: progressive mp4={p_id} (<= {MAX_HEIGHT}p)")
else:
    # ✅ умный fallback: лучшее до 2160 без av1
    chosen_format = (
        f"bestvideo[height<={MAX_HEIGHT}][vcodec!*=av01][vcodec!*=av1]"
        f"+bestaudio"
        f"/best[height<={MAX_HEIGHT}]"
    )
    print("[WARN] Не нашёл подходящие форматы по списку - качаю через fallback selector")

# 3) Качаем
dl_opts = dict(base_opts)
dl_opts["format"] = chosen_format

with yt_dlp.YoutubeDL(dl_opts) as ydl:
    try:
        ydl.download([URL])
    except yt_dlp.utils.DownloadError as e:
        # Typical failure in this setup: HLS/SSL EOF -> empty file.
        msg = str(e).lower()
        if "http error 403" in msg or "requested format is not available" in msg:
            raise SystemExit(
                "[ERROR] YouTube отклоняет медиапоток (403). "
                "Обычно это устаревшие cookies или недоступный n/po-token. "
                "Обнови cookies.txt из того же браузера/профиля."
            ) from e
        if "downloaded file is empty" in msg or "unexpected_eof_while_reading" in msg or "ssl" in msg:
            print("[WARN] Сетевая ошибка на основном формате, пробую безопасный fallback...")
            safe_opts = dict(base_opts)
            safe_opts["format"] = (
                f"best[ext=mp4][height<={MAX_HEIGHT}]"
                f"/best[height<={MAX_HEIGHT}]"
                "/best"
            )
            with yt_dlp.YoutubeDL(safe_opts) as retry_ydl:
                retry_ydl.download([URL])
        else:
            raise

print("[DONE] Готово!")
