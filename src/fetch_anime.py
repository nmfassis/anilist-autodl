#!/usr/bin/env python3
"""anilist-autodl: download the next episodes of your AniList lists on Android (Termux).

All settings live in ~/.config/anilist-autodl/config (written by install.sh; run
`anilist-autodl config` to change them). Engines: ani-cli (English sources) or
ani-tupi (Brazilian-Portuguese sources).
"""
import os
import re
import json
import time
import fcntl
import shlex
import shutil
import signal
import subprocess
import sys
import unicodedata
import urllib.request
import urllib.error
from datetime import datetime

# ---------------- CONFIGURATION ----------------
CONFIG_FILE = os.environ.get('AUTODL_CONFIG') or os.path.expanduser('~/.config/anilist-autodl/config')


def load_config(path):
    """Read KEY='value' lines (the same file is sourced by the shell scripts)."""
    cfg = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.match(r'^([A-Z][A-Z0-9_]*)=(.*)$', line.strip())
                if not m:
                    continue
                try:
                    parts = shlex.split(m.group(2))
                except ValueError:
                    continue
                cfg[m.group(1)] = parts[0] if parts else ''
    except OSError:
        pass
    return cfg


_CFG = load_config(CONFIG_FILE)


def _num(key, default, cast=int, minimum=None):
    try:
        v = cast(_CFG.get(key, default))
    except (TypeError, ValueError):
        v = default
    return max(v, minimum) if minimum is not None else v


def _flag(key, default):
    v = _CFG.get(key)
    return default if v is None else v.strip().lower() in ('1', 'true', 'yes', 'y', 'on')


ANILIST_USERNAME = _CFG.get('ANILIST_USERNAME', 'YOUR_ANILIST_USERNAME')
LANGUAGE = _CFG.get('AUTODL_LANG', 'en') if _CFG.get('AUTODL_LANG') in ('en', 'pt') else 'en'   # notification language
ENGINE = _CFG.get('AUTODL_ENGINE') or ('ani-tupi' if LANGUAGE == 'pt' else 'ani-cli')            # 'ani-cli' | 'ani-tupi'
AUDIO = 'dub' if _CFG.get('AUDIO') == 'dub' else 'sub'     # preferred version
AUDIO_FALLBACK = _flag('AUDIO_FALLBACK', True)              # accept the other version when the preferred one is missing

DOWNLOAD_DIR = _CFG.get('DOWNLOAD_DIR') or '/sdcard/Download/Anime'          # final destination
TMP_DIR = os.path.expanduser('~/.anime_tmp')      # internal storage: download + ffmpeg fixup happen here
TRASH_DIR = os.path.join(DOWNLOAD_DIR, '.trash')  # watched episodes wait here before being deleted
STATE_FILE = os.path.expanduser('~/.anime_downloader_state.json')
LEGACY_HISTORY_FILE = os.path.expanduser('~/.anime_download_history.json')
LOG_FILE = os.path.expanduser('~/.anime_downloader.log')
LOCK_FILE = os.path.expanduser('~/.anime_downloader.lock')

AHEAD_FINISHED = _num('AHEAD_FINISHED', 3, minimum=1)   # episodes to download ahead for FINISHED anime
AHEAD_AIRING = _num('AHEAD_AIRING', 1, minimum=1)       # ...and for anime that is still airing (capped at released episodes)
PROCESS_TIMEOUT_SECONDS = _num('TIMEOUT_MINUTES', 60, minimum=5) * 60   # per download attempt
MAX_LOG_SIZE_MB = 5
DOWNLOAD_PLANNING = _flag('DOWNLOAD_PLANNING', True)    # also grab Ep 1 of PLANNING anime once it starts airing
RETRY_COOLDOWN_HOURS = _num('RETRY_COOLDOWN_HOURS', 6, cast=float, minimum=0.25)   # wait before retrying a failed episode
MIN_FREE_GB = _num('MIN_FREE_GB', 2, cast=float, minimum=0)        # pause downloads (and notify) below this
LOW_SPACE_NOTIFY_HOURS = 24       # at most one low-storage notification per this many hours
TRASH_DAYS = _num('TRASH_DAYS', 3, cast=float, minimum=0)   # watched episodes sit in <DOWNLOAD_DIR>/.trash this long
MIN_SIZE_MB = 10
MIN_DURATION_SEC = 60
TITLE_MATCH_RATIO = 0.5

VIDEO_EXTS = ('.mp4', '.mkv', '.webm')
PREFIX = os.environ.get('PREFIX', '/data/data/com.termux/files/usr')
TERMUX_SH = os.path.join(PREFIX, 'bin', 'sh')
HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fetch_episode_tupi.py')   # ani-tupi bridge
RESULT_PREFIX = 'ANI_TUPI_RESULT '
PARTIAL_MARKERS = ('.part', '.ytdl', '.tmp', '.aria2', '.temp.')

# Notification texts (logs are always English so they are easy to paste in bug reports).
MESSAGES = {
    'en': {
        'title': 'Anime Downloader',
        'done': 'Downloaded Ep {ep} of {name}',
        'timeout_t': 'Anime Downloader - Timeout',
        'timeout': 'Download timed out for {name} Ep {ep}',
        'failed_t': 'Anime Downloader - Failed',
        'failed': "Couldn't download {name} Ep {ep}. Will retry in {hours:g}h.",
        'space_t': 'Anime Downloader - Low storage',
        'space': 'Only {free:.1f} GB free. Downloads are paused until you free up space.',
    },
    'pt': {
        'title': 'Anime Downloader',
        'done': 'Episódio {ep} de {name} baixado',
        'timeout_t': 'Anime Downloader - Tempo esgotado',
        'timeout': 'O download de {name} ep. {ep} excedeu o tempo limite',
        'failed_t': 'Anime Downloader - Falhou',
        'failed': 'Não foi possível baixar {name} ep. {ep}. Nova tentativa em {hours:g}h.',
        'space_t': 'Anime Downloader - Pouco espaço',
        'space': 'Só {free:.1f} GB livres. Os downloads ficam pausados até você liberar espaço.',
    },
}


def msg(key, **kw):
    return MESSAGES[LANGUAGE][key].format(**kw)
# -----------------------------------------------

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(TRASH_DIR, exist_ok=True)
try:
    open(os.path.join(TRASH_DIR, '.nomedia'), 'a').close()   # keep the trash out of the gallery/media apps
except OSError:
    pass


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE_MB * 1024 * 1024:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines[len(lines) // 2:])
                f.write(f"[{timestamp}] [INFO] Log exceeded {MAX_LOG_SIZE_MB}MB and was trimmed.\n")
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def load_state():
    """state = {"history": {key: filename|None}, "failures": {key: epoch_seconds}}"""
    state = {"history": {}, "failures": {}, "low_space_notice": 0}
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
        state["history"] = data.get("history", {})
        state["failures"] = data.get("failures", {})
        state["low_space_notice"] = data.get("low_space_notice", 0)
        return state
    except Exception:
        pass
    try:  # migrate the old history file (a plain list of keys)
        with open(LEGACY_HISTORY_FILE, 'r') as f:
            for k in json.load(f):
                state["history"][k] = None
    except Exception:
        pass
    return state


def save_state(state):
    try:
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        log(f"[!] Could not save state: {e}")


def walk_library():
    """Yield (folder, files) for DOWNLOAD_DIR, skipping the trash folder."""
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        dirs[:] = [d for d in dirs if d != '.trash']
        yield root, files


def episode_on_disk(media, ep, filename=None):
    """True if the episode file still exists in DOWNLOAD_DIR."""
    if filename:
        return os.path.exists(os.path.join(DOWNLOAD_DIR, filename))
    titles = all_titles(media)  # legacy entry / unknown filename: look for a matching file
    for _, files in walk_library():
        for f in files:
            if f.lower().endswith(VIDEO_EXTS):
                m = re.search(r'Episode\s+(\d+)\s*$', os.path.splitext(f)[0], re.IGNORECASE)
                if m and int(m.group(1)) == ep and title_match(titles, f):
                    return True
    return False


ANILIST_API_URL = 'https://graphql.anilist.co'
QUERY = """
query ($username: String, $status: MediaListStatus) {
  MediaListCollection(userName: $username, type: ANIME, status: $status) {
    lists {
      entries {
        progress
        media {
          id
          status
          episodes
          seasonYear
          startDate { year }
          title { english romaji }
          synonyms
          nextAiringEpisode { episode }
        }
      }
    }
  }
}
"""


def get_list(username, status):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    }
    req = urllib.request.Request(
        ANILIST_API_URL,
        data=json.dumps({'query': QUERY, 'variables': {'username': username, 'status': status}}).encode('utf-8'),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        entries = []
        collection = (data.get('data') or {}).get('MediaListCollection') or {}
        for lst in collection.get('lists', []):
            entries.extend(lst.get('entries', []))
        return entries
    except urllib.error.HTTPError as e:
        log(f"[!] AniList API Error: {e.code} {e.reason}")
    except Exception as e:
        log(f"[!] Network error connecting to AniList: {e}")
    return []


def notify(title, content, icon):
    try:
        subprocess.run(["termux-notification", "--title", title, "--content", content,
                        "--priority", "high", "--icon", icon],
                       stdin=subprocess.DEVNULL, timeout=15)
    except Exception:
        pass


# ---------- Title matching (against ALL known names, not just one) ----------

STOPWORDS = {'the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'for', 'on', 'with', 'is', 'at',
             'by', 'this', 'that', 'your', 'you', 'my', 'i', 'it', 'season', 'episode', 'ep'}


def tokenize(s):
    s = re.sub(r'[\d\W_]+', ' ', s.lower())
    return set(s.split()) - STOPWORDS


def all_titles(media):
    t = media.get('title') or {}
    names = [t.get('english'), t.get('romaji')] + list(media.get('synonyms') or [])[:5]
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def title_match(titles, filename):
    file_tokens = tokenize(os.path.splitext(filename)[0])
    best = 0.0
    for t in titles:
        exp = tokenize(t)
        if not exp:
            continue
        best = max(best, len(exp & file_tokens) / len(exp))
    return best >= TITLE_MATCH_RATIO


# ---------- Cleanup of watched episodes ----------

def cleanup_watched_episodes(media, progress):
    if not progress or progress <= 0:
        return
    titles = all_titles(media)
    if not titles:
        return
    for root, files in walk_library():
        for fname in files:
            if not fname.lower().endswith(VIDEO_EXTS):
                continue
            stem = os.path.splitext(fname)[0]
            m = re.search(r'Episode\s+(\d+)\s*$', stem, re.IGNORECASE)
            if not m or not title_match(titles, fname):
                continue
            if int(m.group(1)) > progress:
                continue
            # Move the video + companion files with the SAME stem (subtitles etc.) to the trash.
            # Exact stem match only, so "Episode 1" never matches "Episode 10".
            for other in os.listdir(root):
                if other == fname or other.startswith(stem + '.'):
                    try:
                        dst = os.path.join(TRASH_DIR, other)
                        if os.path.exists(dst):
                            os.remove(dst)
                        shutil.move(os.path.join(root, other), dst)
                        os.utime(dst, None)   # trash age counts from now
                        log(f"[🗑] Watched, moved to trash: {other} (Progress: Ep {progress})")
                    except Exception as e:
                        log(f"[!] Could not trash {other}: {e}")


def purge_trash(force=False):
    """Delete trashed files older than TRASH_DAYS (or everything when force=True)."""
    cutoff = time.time() - TRASH_DAYS * 86400
    try:
        names = os.listdir(TRASH_DIR)
    except OSError:
        return
    for f in names:
        if f == '.nomedia':
            continue
        path = os.path.join(TRASH_DIR, f)
        try:
            if force or os.path.getmtime(path) < cutoff:
                os.remove(path)
                log(f"[🗑] Trash emptied: {f}")
        except OSError:
            pass


def restore_from_trash(media, ep):
    """If this episode is in the trash (e.g. watched count was lowered), move it back instead of downloading."""
    titles = all_titles(media)
    try:
        names = os.listdir(TRASH_DIR)
    except OSError:
        return False
    for f in names:
        if not f.lower().endswith(VIDEO_EXTS):
            continue
        stem = os.path.splitext(f)[0]
        m = re.search(r'Episode\s+(\d+)\s*$', stem, re.IGNORECASE)
        if m and int(m.group(1)) == ep and title_match(titles, f):
            for other in names:
                if other == f or other.startswith(stem + '.'):
                    try:
                        dst = os.path.join(DOWNLOAD_DIR, other)
                        if os.path.exists(dst):
                            os.remove(dst)
                        shutil.move(os.path.join(TRASH_DIR, other), dst)
                    except OSError as e:
                        log(f"[!] Could not restore {other}: {e}")
                        return False
            return True
    return False


def free_gb():
    return min(shutil.disk_usage(p).free for p in (DOWNLOAD_DIR, TMP_DIR)) / (1024 ** 3)


def storage_ok(state):
    """False (and a throttled notification) when free space is below MIN_FREE_GB, even after emptying the trash."""
    free = free_gb()
    if free < MIN_FREE_GB:
        purge_trash(force=True)
        free = free_gb()
    if free >= MIN_FREE_GB:
        if state.get("low_space_notice"):
            state["low_space_notice"] = 0
            save_state(state)
        return True
    log(f"[!] Only {free:.1f} GB free (minimum {MIN_FREE_GB} GB) - downloads paused.")
    if time.time() - state.get("low_space_notice", 0) > LOW_SPACE_NOTIFY_HOURS * 3600:
        notify(msg('space_t'), msg('space', free=free), "error")
        state["low_space_notice"] = time.time()
        save_state(state)
    return False


# ---------- Download / verify / deliver ----------

def clean_tmp():
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.makedirs(TMP_DIR, exist_ok=True)


_env_logged = False


def build_env():
    """Environment for the engine: de-duplicated PATH-like vars, oversized vars removed, size logged once per run."""
    global _env_logged
    env = dict(os.environ, PYTHONUNBUFFERED='1')
    if ENGINE == 'ani-tupi':
        env.update(
            # ani-tupi downloads into internal storage; this script verifies the file and then moves it to DOWNLOAD_DIR
            ANI_TUPI__ANIME_DOWNLOAD__DOWNLOAD_DIRECTORY=TMP_DIR,
            ANI_TUPI__ANIME_DOWNLOAD__VIDEO_FORMAT='mp4',
            ANI_TUPI__ANIME_DOWNLOAD__MAX_PARALLEL_DOWNLOADS='1',
            ANI_TUPI__ANIME_DOWNLOAD__SKIP_ALREADY_DOWNLOADED='false',   # TMP_DIR is wiped every run
            ANI_TUPI__SEARCH__ENABLE_TITLE_RESOLUTION='false',           # skip the slow Jikan fallback
        )
    else:
        env['ANI_CLI_DOWNLOAD_DIR'] = TMP_DIR
    for k, v in list(env.items()):
        if k.endswith('PATH') and ':' in v:
            env[k] = ':'.join(dict.fromkeys(v.split(':')))
    # Termux binaries first, so child processes find Termux's own tools even in a bare scheduler environment
    env['PATH'] = ':'.join(dict.fromkeys([os.path.join(PREFIX, 'bin')] + env.get('PATH', '').split(':')))
    dropped = [k for k, v in env.items() if len(v) > 16384 and not k.endswith('PATH')]
    for k in dropped:
        env.pop(k)
    if not _env_logged:
        _env_logged = True
        total = sum(len(k) + len(v) + 2 for k, v in env.items())
        top = sorted(env.items(), key=lambda kv: -len(kv[1]))[:3]
        log(f"[i] {ENGINE} environment: {len(env)} vars, {total} bytes; largest: "
            + ", ".join(f"{k}={len(v)}B" for k, v in top)
            + (f"; dropped oversized: {', '.join(dropped)}" if dropped else ""))
    return env


# ---------- Engine: ani-cli ----------

def run_ani_cli(query, ep, audio):
    env = build_env()
    # Run ani-cli with Termux's own sh. Under the job scheduler its "#!/bin/sh" can resolve to Android's
    # /system/bin/sh, which has no builtin printf, so large search results fail with "Argument list too long".
    ani = shutil.which("ani-cli", path=env["PATH"]) or os.path.join(PREFIX, "bin", "ani-cli")
    cmd = ([TERMUX_SH, ani] if os.path.exists(TERMUX_SH) else [ani]) + ["-d", "-e", str(ep), "-S", "1"]
    if audio == 'dub':
        cmd.append("--dub")
    cmd.append(query)
    p = subprocess.Popen(cmd,
                         cwd=TMP_DIR, env=env, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    try:
        code = p.wait(timeout=PROCESS_TIMEOUT_SECONDS)
        if code != 0:
            log(f"[!] ani-cli exited with code {code} (checking for a usable file anyway)")
        return True
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)   # kill ani-cli AND yt-dlp/ffmpeg children
        except Exception:
            pass
        p.wait()
        return False


def find_finished_video():
    best = None
    for root, _, files in os.walk(TMP_DIR):
        for f in files:
            low = f.lower()
            if low.endswith(VIDEO_EXTS) and not any(m in low for m in PARTIAL_MARKERS):
                path = os.path.join(root, f)
                if best is None or os.path.getsize(path) > os.path.getsize(best):
                    best = path
    return best


# ---------- Engine: ani-tupi ----------

def run_ani_tupi(queries, titles, ep, anilist_id):
    """Run the ani-tupi helper in its own session. Returns its result dict, or None on timeout."""
    env = build_env()
    payload = json.dumps({"queries": queries, "titles": titles, "episode": ep, "anilist_id": anilist_id,
                          "audio": AUDIO, "fallback": AUDIO_FALLBACK})
    p = subprocess.Popen([sys.executable, HELPER, payload],
                         cwd=TMP_DIR, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors='replace', start_new_session=True)
    try:
        out, _ = p.communicate(timeout=PROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)   # kill the helper AND yt-dlp/ffmpeg/browser children
        except Exception:
            pass
        p.communicate()
        return None

    result, other = None, []
    for line in (out or '').splitlines():
        if line.startswith(RESULT_PREFIX):
            try:
                result = json.loads(line[len(RESULT_PREFIX):])
            except ValueError:
                pass
        elif line.startswith('[helper] '):
            log(line)
        elif line.strip():
            other.append(line)
    if result is None:
        log(f"[!] ani-tupi helper exited with code {p.returncode} without a result. Last output:")
        for line in other[-15:]:
            log(f"    {line}")
        return {"ok": False, "reason": "no-result"}
    if not result.get("ok") and other:
        for line in other[-5:]:
            log(f"    {line}")
    return result


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()[:120] or 'Anime'


def stage_video(path, title, ep):
    """Rename ani-tupi's '<ep>.mp4' to '<Title> Episode <ep>.mp4' (the naming the rest of this script relies on)."""
    ext = os.path.splitext(path)[1] or '.mp4'
    dst = os.path.join(TMP_DIR, f"{safe_name(title)} Episode {ep}{ext}")
    shutil.move(path, dst)
    return dst


def verify(video, titles):
    name = os.path.basename(video)
    size_mb = os.path.getsize(video) / (1024 * 1024)
    if size_mb < MIN_SIZE_MB:
        log(f"[!] {name} is only {size_mb:.1f} MB - too small, rejecting.")
        return False
    if not title_match(titles, name):
        log(f"[!] '{name}' does not match any known title - wrong anime, rejecting.")
        return False
    if shutil.which("ffprobe"):
        try:
            res = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video],
                capture_output=True, text=True, timeout=60)
            if res.returncode != 0 or not res.stdout.strip():
                log(f"[!] ffprobe could not read {name}, rejecting.")
                return False
            duration = float(res.stdout.strip())
            if duration < MIN_DURATION_SEC:
                log(f"[!] {name} is only {duration:.0f}s long, rejecting.")
                return False
            log(f"[✓] Verified: {name} ({size_mb:.1f} MB, {int(duration // 60)}m{int(duration % 60)}s)")
            return True
        except Exception as e:
            log(f"[!] ffprobe check failed: {e}")
            return False
    log(f"[✓] Verified: {name} ({size_mb:.1f} MB)")
    return True


def deliver(video):
    stem = os.path.splitext(os.path.basename(video))[0]
    for f in os.listdir(os.path.dirname(video)):
        low = f.lower()
        if (f.startswith(stem + '.')) and not any(m in low for m in PARTIAL_MARKERS):
            src = os.path.join(os.path.dirname(video), f)
            dst = os.path.join(DOWNLOAD_DIR, f)
            try:
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
                log(f"[→] Moved to {DOWNLOAD_DIR}: {f}")
            except Exception as e:
                log(f"[!] Could not move {f}: {e}")
                return False
    return True


def clean_query(q):
    """Search backends don't URL-encode reliably: strip accents, dashes, quotes and symbols that cause HTTP 400 / bad searches."""
    q = re.sub(r'[\u2010-\u2015]', ' ', q).replace("'", "").replace("\u2019", "")
    q = unicodedata.normalize('NFKD', q).encode('ascii', 'ignore').decode()
    q = re.sub(r'[^A-Za-z0-9\s\-]', ' ', q)
    return re.sub(r'\s+', ' ', q).strip()


def try_ani_cli(candidates, titles, primary, anilist_id, target_ep):
    """Returns (verified video path | None, timed_out)."""
    other = 'sub' if AUDIO == 'dub' else 'dub'
    for mode in [AUDIO] + ([other] if AUDIO_FALLBACK else []):
        for query in candidates:
            log(f"[+] ani-cli query: '{query}' ({mode}) for Ep {target_ep}...")
            clean_tmp()  # always start from an empty temp dir: no stale files, no overwrite prompts
            if not run_ani_cli(query, target_ep, mode):
                return None, True
            video = find_finished_video()
            if video and verify(video, titles):
                return video, False
            log(f"[!] Query '{query}' ({mode}) gave no usable file. Trying next candidate...")
    return None, False


def try_ani_tupi(candidates, titles, primary, anilist_id, target_ep):
    """Returns (verified video path | None, timed_out)."""
    log(f"[+] ani-tupi search for '{primary}' Ep {target_ep} "
        f"(prefer {AUDIO}; queries: {', '.join(candidates) or '-'})...")
    clean_tmp()  # always start from an empty temp dir: no stale files
    res = run_ani_tupi(candidates, titles, target_ep, anilist_id)
    if res is None:
        return None, True
    if res.get('ok') and res.get('path') and os.path.exists(res['path']):
        video = stage_video(res['path'], primary, target_ep)
        if verify(video, titles):
            return video, False
        log("[!] The downloaded file was rejected.")
    else:
        log(f"[!] ani-tupi could not download '{primary}' Ep {target_ep} (reason: {res.get('reason', 'unknown')}).")
    return None, False


def download_anime_entry(media, target_ep):
    t = media.get('title') or {}
    eng, rom = t.get('english'), t.get('romaji')
    year = media.get('seasonYear') or (media.get('startDate') or {}).get('year')
    primary = eng or rom
    titles = all_titles(media)

    candidates = []
    if eng:
        candidates.append(eng)
    if rom and rom != eng:
        candidates.append(rom)
    if eng and year:
        candidates.append(f"{eng} {year}")
    if rom and rom != eng and year:
        candidates.append(f"{rom} {year}")
    for syn in (media.get('synonyms') or [])[:2]:
        if syn and syn not in candidates:
            candidates.append(syn)

    cleaned = []
    for c in candidates:
        c = clean_query(c)
        if c and c not in cleaned:
            cleaned.append(c)
    candidates = cleaned

    video, timed_out = (try_ani_tupi if ENGINE == 'ani-tupi' else try_ani_cli)(
        candidates, titles, primary, media.get('id'), target_ep)
    if timed_out:
        log(f"[!] TIMEOUT ({PROCESS_TIMEOUT_SECONDS // 60} min) for '{primary}' Ep {target_ep}.")
        notify(msg('timeout_t'), msg('timeout', name=primary, ep=target_ep), "error")
        clean_tmp()
        return None, 'timeout'

    if video and deliver(video):
        filename = os.path.basename(video)
        log(f"[✓] Ep {target_ep} of '{primary}' downloaded and verified.")
        notify(msg('title'), msg('done', name=primary, ep=target_ep), "download_done")
        clean_tmp()
        return filename, None

    clean_tmp()
    log(f"[!] All search terms failed for '{primary}' Ep {target_ep}.")
    return None, 'failed'


def main():
    if ANILIST_USERNAME == 'YOUR_ANILIST_USERNAME':
        log(f"No AniList username found in {CONFIG_FILE}. Run: anilist-autodl config")
        return

    # Only one instance at a time (cron + manual run were likely stepping on each other).
    lock = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("[-] Another instance is already running. Exiting.")
        return

    purge_trash()
    state = load_state()
    history, failures = state["history"], state["failures"]
    log(f"Checking AniList for user: {ANILIST_USERNAME}...")
    entries = [(e, False) for e in get_list(ANILIST_USERNAME, 'CURRENT')]
    if DOWNLOAD_PLANNING:
        watching_ids = {(e.get('media') or {}).get('id') for e, _ in entries}
        seen = set()
        for e in get_list(ANILIST_USERNAME, 'PLANNING'):
            mid = (e.get('media') or {}).get('id')
            if mid not in watching_ids and mid not in seen:
                seen.add(mid)
                entries.append((e, True))

    # Pass 1: move watched episodes to the trash first, so the space check below sees the real picture.
    for entry, planning in entries:
        if not planning:
            cleanup_watched_episodes(entry.get('media') or {}, entry.get('progress') or 0)

    for entry, planning in entries:
        progress = entry.get('progress') or 0
        media = entry.get('media') or {}
        media_id = media.get('id')
        t = media.get('title') or {}
        raw_title = t.get('english') or t.get('romaji')
        status = media.get('status')
        episodes = media.get('episodes')
        next_airing = media.get('nextAiringEpisode')

        if planning:
            # Planned anime: only once it is airing, and only Ep 1 (not-yet-released and finished ones are skipped)
            if status != 'RELEASING':
                continue
        elif status not in ('RELEASING', 'FINISHED'):
            continue

        if next_airing:
            latest_released = next_airing['episode'] - 1
        elif episodes:
            latest_released = episodes
        else:
            latest_released = progress + 1

        if planning:
            max_target_ep = min(latest_released, progress + 1)          # planned anime: Ep 1 only
        elif status == 'FINISHED':
            max_target_ep = min(latest_released, progress + AHEAD_FINISHED)
        else:
            max_target_ep = min(latest_released, progress + AHEAD_AIRING)

        if max_target_ep < progress + 1:
            if not planning:
                log(f"[-] '{raw_title}' is up to date (Progress: Ep {progress})")
            continue

        for target_ep in range(progress + 1, max_target_ep + 1):
            key = f"{media_id}_{target_ep}"
            if episode_on_disk(media, target_ep, history.get(key)):
                if not planning:
                    log(f"[-] '{raw_title}' Ep {target_ep} already on disk.")
                continue
            if restore_from_trash(media, target_ep):
                log(f"[↩] '{raw_title}' Ep {target_ep} restored from trash.")
                continue
            if key in history:
                log(f"[*] '{raw_title}' Ep {target_ep} was downloaded before but the file is gone - downloading again.")
            last_fail = failures.get(key)
            if last_fail and time.time() - last_fail < RETRY_COOLDOWN_HOURS * 3600:
                left = RETRY_COOLDOWN_HOURS - (time.time() - last_fail) / 3600
                log(f"[-] '{raw_title}' Ep {target_ep} failed recently - retrying in ~{left:.1f}h.")
                break
            if not storage_ok(state):
                return
            log(f"Targeting{' (planned)' if planning else ''} '{raw_title}' Ep {target_ep} "
                f"(Progress: Ep {progress} | Max Available: Ep {latest_released})")
            filename, reason = download_anime_entry(media, target_ep)
            if filename:
                history[key] = filename
                failures.pop(key, None)
                save_state(state)
            else:
                first_failure = key not in failures
                failures[key] = time.time()
                save_state(state)
                if reason == 'failed' and first_failure:   # timeouts already send their own notification
                    notify(msg('failed_t'),
                           msg('failed', name=raw_title, ep=target_ep, hours=RETRY_COOLDOWN_HOURS),
                           "error")
                break


if __name__ == '__main__':
    main()
