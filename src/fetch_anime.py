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
ENGINES_KNOWN = ('ani-cli', 'ani-cli-rs', 'ani-tupi', 'goanime')
ENGINE = _CFG.get('AUTODL_ENGINE') if _CFG.get('AUTODL_ENGINE') in ENGINES_KNOWN else ('ani-tupi' if LANGUAGE == 'pt' else 'ani-cli')
# Second engine, used when the first one cannot deliver a valid file (wrong anime, no audio, not found, timeout...).
BACKUP_ENGINE = _CFG.get('AUTODL_BACKUP_ENGINE') if _CFG.get('AUTODL_BACKUP_ENGINE') in ENGINES_KNOWN else ''
if BACKUP_ENGINE == ENGINE:
    BACKUP_ENGINE = ''
ENGINE_CHAIN = [ENGINE] + ([BACKUP_ENGINE] if BACKUP_ENGINE else [])
PREFER_SUBS = _flag('PREFER_SUBS', True)   # ani-cli-rs: a 'sub' file without subtitle tracks makes it try the other catalog first
AUDIO = 'dub' if _CFG.get('AUDIO') == 'dub' else 'sub'     # preferred version
AUDIO_FALLBACK = _flag('AUDIO_FALLBACK', True)              # accept the other version when the preferred one is missing

DOWNLOAD_DIR = _CFG.get('DOWNLOAD_DIR') or '/sdcard/Download/Anime'          # final destination
TMP_DIR = os.path.expanduser('~/.anime_tmp')      # internal storage: download + ffmpeg fixup happen here
HOLD_DIR = os.path.expanduser('~/.anime_hold')    # a usable-but-not-ideal file waits here while other sources are tried
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
AUDIO_MIN_RATIO = 0.5          # the audio track must cover at least this share of the video's length
RS_PROVIDERS = ('anikoto', 'anikoto2')       # ani-cli-rs has two independent catalogs
# GoAnime sources to try, in order (English: anidb; Brazilian Portuguese: animefire, goyabu). Only the ones this GoAnime
# version lists in `goanime -h` are used: AllAnime, for example, was removed in 1.8.7.
GOANIME_SOURCES = [x for x in re.split(r'[\s,]+', _CFG.get('GOANIME_SOURCES', '')) if x] or \
    (['animefire', 'goyabu'] if LANGUAGE == 'pt' else ['anidb'])
GOANIME_KNOWN_SOURCES = ('anidb', 'animefire', 'goyabu', 'superflix', 'allanime', '9anime')
GOANIME_OUT = os.path.expanduser('~/.anime_goanime_output.log')   # what the last goanime run printed
DRY_RUN = False        # `anilist-autodl try`: run the whole pipeline but deliver nothing and record nothing
SUB_EXTS = ('.vtt', '.srt', '.ass', '.ssa', '.sub')

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


LIST_ERRORS = 0   # AniList requests that failed in this run: an incomplete picture must never trigger cleanups


def get_list(username, status):
    global LIST_ERRORS
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
        if data.get('errors') or (data.get('data') or {}).get('MediaListCollection') is None:
            LIST_ERRORS += 1       # e.g. unknown user: looks like an empty list but is not
            log(f"[!] AniList did not return your {status} list: {json.dumps(data.get('errors') or 'no data')[:200]}")
            return []
        collection = (data.get('data') or {}).get('MediaListCollection') or {}
        for lst in collection.get('lists', []):
            entries.extend(lst.get('entries', []))
        return entries
    except urllib.error.HTTPError as e:
        LIST_ERRORS += 1
        log(f"[!] AniList API Error: {e.code} {e.reason}")
    except Exception as e:
        LIST_ERRORS += 1
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
             'by', 'this', 'that', 'your', 'you', 'my', 'i', 'it', 'season', 'episode', 'ep',
             # sequel markers: "2nd Season", "Part 2", "II" tell seasons apart but are not part of the name
             'nd', 'st', 'rd', 'th', 'ii', 'iii', 'iv', 'part', 'cour', 'stage'}
# tags that sources add to file names; they say nothing about WHICH anime it is
FILE_NOISE = {'episodes', 'eps', 'dub', 'dubbed', 'sub', 'subbed', 'dublado', 'legendado', 'hd', 'uncensored'}

MATCH_MIN_COVERAGE = 0.8    # share of the expected title's words that must be in the file name
MATCH_EXTRA_PER = 5         # unrelated extra words allowed in the file name: one per this many words of the title


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


def file_name_tokens(filename):
    """(all words, main words) of a file name. 'main' ignores 'Episode N', (tags), [tags] and dub/sub labels."""
    stem = os.path.splitext(filename)[0] if os.path.splitext(filename)[1].lower() in VIDEO_EXTS + ('.part',) else filename
    stem = re.sub(r'\bepisode\s*\d+.*$', ' ', stem, flags=re.IGNORECASE)
    main = tokenize(re.sub(r'[(\[].*?[)\]]', ' ', stem)) - FILE_NOISE
    return tokenize(stem), main


def title_match(titles, filename):
    """Is this file really one of the anime in `titles`? Strict on purpose: a wrong anime in the library is worse
    than a skipped download ('Magical Explorer' must not accept 'Magical Girl Magical Destroyers')."""
    full, main = file_name_tokens(filename)
    if not main:
        return False
    for t in titles:
        exp = tokenize(t)
        if not exp:
            continue
        covered = len(exp & full) / len(exp)
        extra = len(main - exp)
        if covered >= MATCH_MIN_COVERAGE and extra <= len(exp) // MATCH_EXTRA_PER:
            return True                      # same title; short titles allow NO unrelated words ('... Alicization')
        if len(main) >= 2 and main <= exp:
            return True                      # the source shortened a long title
    return False


# ---------- Cleanup of watched episodes ----------

def episode_files():
    """Yield (folder, filename, episode_number) for every library video named '... Episode N'."""
    for root, files in walk_library():
        for fname in files:
            if not fname.lower().endswith(VIDEO_EXTS):
                continue
            m = re.search(r'Episode\s+(\d+)\s*$', os.path.splitext(fname)[0], re.IGNORECASE)
            if m:
                yield root, fname, int(m.group(1))


def move_to_trash(root, fname, why):
    """Move the video + companion files with the SAME stem (subtitles etc.) to the trash.
    Exact stem match only, so "Episode 1" never matches "Episode 10"."""
    stem = os.path.splitext(fname)[0]
    for other in os.listdir(root):
        if other == fname or other.startswith(stem + '.'):
            try:
                dst = os.path.join(TRASH_DIR, other)
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(os.path.join(root, other), dst)
                os.utime(dst, None)   # trash age counts from now
                log(f"[🗑] {why}, moved to trash: {other}")
            except Exception as e:
                log(f"[!] Could not trash {other}: {e}")


def cleanup_watched_episodes(media, progress):
    if not progress or progress <= 0:
        return
    titles = all_titles(media)
    if not titles:
        return
    for root, fname, ep in episode_files():
        if ep <= progress and title_match(titles, fname):
            move_to_trash(root, fname, f"Watched (Progress: Ep {progress})")


def cleanup_left_lists(history, active_ids):
    """Files THIS TOOL downloaded for anime that are no longer on your Watching/Planning lists (completed, dropped,
    paused or removed) -> trash. Uses our own records ('<AniList id>_<episode>' -> file name), never file names, so
    a sequel (another AniList id) is never confused with its first season and files you added yourself are never touched."""
    active = {str(i) for i in active_ids}
    for key, fname in list(history.items()):
        if not fname or str(key).split('_')[0] in active:
            continue
        if os.path.exists(os.path.join(DOWNLOAD_DIR, fname)):
            move_to_trash(DOWNLOAD_DIR, fname, "No longer on your Watching/Planning list")


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


def build_env(engine):
    """Environment for an engine: de-duplicated PATH-like vars, oversized vars removed, size logged once per run."""
    global _env_logged
    env = dict(os.environ, PYTHONUNBUFFERED='1')
    if engine == 'ani-tupi':
        env.update(
            # ani-tupi downloads into internal storage; this script verifies the file and then moves it to DOWNLOAD_DIR
            ANI_TUPI__ANIME_DOWNLOAD__DOWNLOAD_DIRECTORY=TMP_DIR,
            ANI_TUPI__ANIME_DOWNLOAD__VIDEO_FORMAT='mp4',
            ANI_TUPI__ANIME_DOWNLOAD__MAX_PARALLEL_DOWNLOADS='1',
            ANI_TUPI__ANIME_DOWNLOAD__SKIP_ALREADY_DOWNLOADED='false',   # TMP_DIR is wiped every run
            ANI_TUPI__SEARCH__ENABLE_TITLE_RESOLUTION='false',           # skip the slow Jikan fallback
        )
    elif engine == 'goanime':
        env.update(GOANIME_DOWNLOAD_DIR=TMP_DIR, GOANIME_DEFAULT_QUALITY='best', TERM='dumb', NO_COLOR='1', CI='true')
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
        log(f"[i] {engine} environment: {len(env)} vars, {total} bytes; largest: "
            + ", ".join(f"{k}={len(v)}B" for k, v in top)
            + (f"; dropped oversized: {', '.join(dropped)}" if dropped else ""))
    return env


# ---------- Engine: ani-cli ----------

def downloading_wrong_file(titles):
    """Name of a file ani-cli is writing right now that is NOT this anime (so the download can be aborted early)."""
    for _, _, files in os.walk(TMP_DIR):
        for f in files:
            low = f.lower()
            cuts = [low.find(m) for m in PARTIAL_MARKERS if low.find(m) > 0]
            base = f[:min(cuts)] if cuts else f
            if not base.lower().endswith(VIDEO_EXTS):
                if not cuts:
                    continue                  # logs, thumbnails...
                base += '.mp4'
            if not title_match(titles, base):
                return base
    return None


def run_ani_cli(query, ep, audio, titles):
    """Returns 'ok', 'timeout' or 'wrong' (it started downloading a different anime and was stopped)."""
    env = build_env('ani-cli')
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

    def kill():
        try:
            os.killpg(p.pid, signal.SIGKILL)   # kill ani-cli AND yt-dlp/ffmpeg children
        except Exception:
            pass
        p.wait()

    deadline = time.time() + PROCESS_TIMEOUT_SECONDS
    while True:
        try:
            code = p.wait(timeout=2)
            if code != 0:
                log(f"[!] ani-cli exited with code {code} (checking for a usable file anyway)")
            return 'ok'
        except subprocess.TimeoutExpired:
            pass
        wrong = downloading_wrong_file(titles)
        if wrong:
            log(f"[!] ani-cli is downloading '{wrong}', which is a different anime. Stopping it.")
            kill()
            return 'wrong'
        if time.time() > deadline:
            kill()
            return 'timeout'


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
    env = build_env('ani-tupi')
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


def stage_video(path, title, ep, dest_dir=None):
    """Give a downloaded file the name the rest of this script relies on: '<Title> Episode <ep>.<ext>'.
    Companion files (subtitles...) that share the old name follow along; dest_dir moves them all to another folder."""
    folder, old = os.path.dirname(path), os.path.basename(path)
    old_stem = os.path.splitext(old)[0]
    new_stem = f"{safe_name(title)} Episode {ep}"
    dest = dest_dir or folder
    if old_stem == new_stem and dest == folder:
        return path
    for other in os.listdir(folder):
        if other == old or other.startswith(old_stem + '.'):
            shutil.move(os.path.join(folder, other), os.path.join(dest, new_stem + other[len(old_stem):]))
    return os.path.join(dest, new_stem + old[len(old_stem):])


def hold_video(video):
    """Park a file (and its companions) in HOLD_DIR so clean_tmp() cannot remove it."""
    if os.path.dirname(video) == HOLD_DIR:
        return video
    clean_hold()
    stem = os.path.splitext(os.path.basename(video))[0]
    folder = os.path.dirname(video)
    for other in os.listdir(folder):
        if other == os.path.basename(video) or other.startswith(stem + '.'):
            shutil.move(os.path.join(folder, other), os.path.join(HOLD_DIR, other))
    return os.path.join(HOLD_DIR, os.path.basename(video))


def clean_hold():
    shutil.rmtree(HOLD_DIR, ignore_errors=True)
    os.makedirs(HOLD_DIR, exist_ok=True)


def probe_streams(video):
    """ONE ffprobe call: duration, audio tracks (their durations) and subtitle tracks. None if unreadable."""
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_entries", "format=duration:stream=codec_type,duration", "-i", video],
            capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return None
        data = json.loads(res.stdout or '{}')
    except Exception:
        return None

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    duration = num((data.get('format') or {}).get('duration'))
    if duration is None:
        return None
    streams = data.get('streams') or []
    return {
        'duration': duration,
        'audio': [num(st.get('duration')) for st in streams if st.get('codec_type') == 'audio'],
        'subs': sum(1 for st in streams if st.get('codec_type') == 'subtitle'),
    }


def audio_problem(info):
    """Why this file's sound is unusable, or None when it is fine. A video without sound is never acceptable."""
    if not info['audio']:
        return "no audio track"
    known = [d for d in info['audio'] if d]
    if known and info['duration'] > 0 and max(known) < AUDIO_MIN_RATIO * info['duration']:
        return f"audio track is only {max(known):.0f}s of a {info['duration']:.0f}s video"
    return None


def has_sidecar_subs(video):
    stem = os.path.splitext(os.path.basename(video))[0]
    try:
        return any(f.startswith(stem + '.') and f.lower().endswith(SUB_EXTS) for f in os.listdir(os.path.dirname(video)))
    except OSError:
        return False


def verify(video, titles, need_subs=False, flags=None):
    """Hard checks: size, right anime, readable, long enough, has audio. Soft check (need_subs): subtitle tracks;
    a file without them is still accepted but reported through flags ({'no_subs'}), because it may have hardsubs."""
    name = os.path.basename(video)
    size_mb = os.path.getsize(video) / (1024 * 1024)
    if size_mb < MIN_SIZE_MB:
        log(f"[!] {name} is only {size_mb:.1f} MB - too small, rejecting.")
        return False
    if not title_match(titles, name):
        log(f"[!] '{name}' does not match any known title ({' | '.join(titles[:3])}) - wrong anime, rejecting.")
        return False
    if not shutil.which("ffprobe"):
        log(f"[✓] Verified: {name} ({size_mb:.1f} MB; ffprobe missing, audio not checked)")
        return True
    info = probe_streams(video)
    if info is None:
        log(f"[!] ffprobe could not read {name}, rejecting.")
        return False
    if info['duration'] < MIN_DURATION_SEC:
        log(f"[!] {name} is only {info['duration']:.0f}s long, rejecting.")
        return False
    problem = audio_problem(info)
    if problem:
        log(f"[!] {name}: {problem}, rejecting.")
        return False
    subs = ''
    if need_subs:
        if info['subs'] or has_sidecar_subs(video):
            subs = ", subtitles ✓"
        else:
            subs = ", NO subtitle tracks"
            if flags is not None:
                flags.add('no_subs')
    d = info['duration']
    log(f"[✓] Verified: {name} ({size_mb:.1f} MB, {int(d // 60)}m{int(d % 60)}s, audio ✓{subs})")
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


# ---------- Engine: ani-cli-rs ----------

def run_capture(cmd, timeout, env):
    """Run a command in its own session and capture its output. (None, '', '') when it had to be killed."""
    p = subprocess.Popen(cmd, cwd=TMP_DIR, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, errors='replace', start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)   # also kills yt-dlp/ffmpeg/aria2 children
        except Exception:
            pass
        p.communicate()
        return None, '', ''
    return p.returncode, out or '', err or ''


def rs_cmd(env, *args, provider=None):
    exe = shutil.which('ani-cli-rs', path=env['PATH']) or os.path.join(PREFIX, 'bin', 'ani-cli-rs')
    return [exe] + (['--provider', provider] if provider else []) + [str(a) for a in args]


_RS_ID_KEYS = ('id', 'show_id', 'showId', 'slug')
_RS_LIST_KEYS = ('results', 'shows', 'items', 'data', 'anime', 'list', 'episodes')


def _json_or_none(text):
    text = (text or '').strip()
    if text[:1] not in ('[', '{'):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _rs_items(data):
    if isinstance(data, dict):
        for k in _RS_LIST_KEYS:
            if isinstance(data.get(k), list):
                return data[k]
        return [data]
    return data if isinstance(data, list) else []


def _item_titles(item):
    """Every name an item carries: 'title', 'name', 'english_name'... (also nested {'english': ..., 'romaji': ...})."""
    out = []
    for k, v in item.items():
        if 'title' in k.lower() or 'name' in k.lower():
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
            elif isinstance(v, dict):
                out += [x.strip() for x in v.values() if isinstance(x, str) and x.strip()]
    return list(dict.fromkeys(out))


def parse_rs_results(text):
    """'ani-cli-rs search --json' (or its tab-separated text) -> [(show_id, [names])].
    Written against the documented behaviour, so it is deliberately tolerant about field names."""
    data = _json_or_none(text)
    results = []
    if data is not None:
        for it in _rs_items(data):
            if not isinstance(it, dict):
                continue
            sid = next((str(it[k]) for k in _RS_ID_KEYS if it.get(k) not in (None, '')), None)
            names = _item_titles(it)
            if sid and names:
                results.append((sid, names))
        return results
    for line in (text or '').splitlines():       # text format: the show ID comes first
        cols = [c.strip() for c in line.split('\t') if c.strip()]
        names = [c for c in cols[1:] if not re.fullmatch(r'[\d.,/ ]+', c)]
        if len(cols) >= 2 and names:
            results.append((cols[0], names))
    return results


ROMAN_SEASONS = {'ii': 2, 'iii': 3, 'iv': 4}


def sequel_markers(text):
    """Season/stage numbers named in a title: '2nd Season', 'Season 2', 'Part 2', '2nd - 3rd STAGE', 'II' -> {2} / {2, 3}.
    Resolutions, '(12 episodes)', years and numbers above 99 ('Mob Psycho 100') are not season numbers."""
    text = re.sub(r'\bepisode\s*\d+.*$', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\(\s*\d+\s*(episodes?|eps?)\s*\)|\b\d{3,4}p\b', ' ', text, flags=re.IGNORECASE)
    nums = {int(n) for n in re.findall(r'\d+', text) if 1 <= int(n) <= 99}
    nums |= {ROMAN_SEASONS[w] for w in re.findall(r'[a-z]+', text.lower()) if w in ROMAN_SEASONS}
    return nums


def result_match(name, titles):
    """Is this catalog entry the anime we want? -> (True, '') or (False, why).
    Same words AND the same season/stage numbers: 'X 1st STAGE' and 'X 2nd - 3rd STAGE' are different entries (each with
    its own episode numbering) even though their words are identical."""
    fname = f"{name} Episode 1.mp4"
    same_words = [t for t in titles if title_match([t], fname)]
    if not same_words:
        return False, 'different title'
    mine = sequel_markers(name)
    if not any(sequel_markers(t) == mine for t in same_words):
        wanted = sorted({tuple(sorted(sequel_markers(t))) for t in same_words})
        return False, f"season/stage numbers differ (entry {sorted(mine) or '-'}, wanted {[list(w) or '-' for w in wanted]})"
    return True, ''


def pick_result(results, titles):
    """The search result that really is this anime: right words and right season, exact name first, then the shortest."""
    best = None
    for sid, names in results:
        ok = [n for n in names if result_match(n, titles)[0]]
        if not ok:
            continue
        exact = any(tokenize(n) == tokenize(t) for n in ok for t in titles)
        key = (0 if exact else 1, min(len(n) for n in ok), sid)
        if best is None or key < best[0]:
            best = (key, sid, ok[0])
    return (best[1], best[2]) if best else None


def _norm_episode(x):
    s = str(x).strip()
    s = re.sub(r'^(episode|ep)\s*', '', s, flags=re.IGNORECASE)
    if re.fullmatch(r'\d+(\.\d+)?', s):
        return re.sub(r'\.0+$', '', s)
    return None


def parse_rs_episodes(text):
    """Episode labels offered by 'ani-cli-rs episodes' -> {'1', '2', '10.5'}.
    An empty set means "the catalog lists none"; None means the output was not understood (then just try)."""
    text = (text or '').strip()
    if not text:
        return set()
    data = _json_or_none(text)
    if data is not None:
        items = _rs_items(data)
        if not items:
            return set()
        labels = []
        for it in items:
            if isinstance(it, dict):
                for k in ('episode', 'number', 'label', 'name', 'id'):
                    if k in it:
                        labels.append(it[k])
                        break
            else:
                labels.append(it)
    else:
        labels = re.split(r'[\s,]+', text)
    eps = {_norm_episode(x) for x in labels}
    eps.discard(None)
    return eps if eps else None


def try_ani_cli_rs(candidates, titles, primary, anilist_id, target_ep):
    """Search with ani-cli-rs, pick the show BY ID (strict name match), download that exact episode.
    Both catalogs are tried, then the other version (dub/sub) when allowed. Returns (video | None, timed_out)."""
    env = build_env('ani-cli-rs')
    title = safe_name(primary)
    other = 'sub' if AUDIO == 'dub' else 'dub'
    held = None
    down = set()          # catalogs that errored out: not asked again for this episode
    clean_hold()
    for mode in [AUDIO] + ([other] if AUDIO_FALLBACK else []):
        for provider in RS_PROVIDERS:
            if provider in down:
                continue
            clean_tmp()
            show, errors, seen = None, 0, []
            for query in candidates:
                rc, out, err = run_capture(rs_cmd(env, 'search', '--mode', mode, '--json', query, provider=provider), 90, env)
                if rc is None:
                    errors += 1
                    log(f"[!] ani-cli-rs search timed out ({provider}, '{query}')")
                    if errors >= 2:
                        break          # a hanging catalog: do not wait for every remaining query
                    continue
                if rc != 0:
                    errors += 1
                    log(f"[!] ani-cli-rs search failed ({provider}, '{query}', code {rc}): {(err or out).strip()[-160:]}")
                    continue
                parsed = parse_rs_results(out)
                show = pick_result(parsed, titles)
                log(f"[i] ani-cli-rs {provider}/{mode}: '{query}' -> {len(parsed)} result(s)" + (" (match)" if show else ""))
                if show:
                    break
                seen += [r for r in parsed if r not in seen]
            if not show and errors and errors >= min(len(candidates), 2):
                down.add(provider)
                log(f"[!] ani-cli-rs {provider} is not answering: skipping it for this episode.")
                continue
            if not show:
                log(f"[!] ani-cli-rs ({provider}, {mode}): nothing matches '{primary}' ({len(seen)} result(s) seen).")
                for sid, names in seen[:4]:                  # say WHY, so a mismatch can be diagnosed from the log alone
                    log(f"      - {names[0]}: {result_match(names[0], titles)[1] or 'ok'}")
                continue
            sid, found = show
            log(f"[+] ani-cli-rs {provider}/{mode}: '{found}' [{sid}] for Ep {target_ep}...")

            rc, out, err = run_capture(rs_cmd(env, 'episodes', sid, '--mode', mode, '--json'), 90, env)
            eps = parse_rs_episodes(out) if rc == 0 else None
            if eps is not None and str(target_ep) not in eps:
                log(f"[!] Ep {target_ep} is not in the {provider} catalog yet ({len(eps)} episode(s) listed).")
                continue

            rc, out, err = run_capture(rs_cmd(env, 'download', sid, target_ep, '--mode', mode, '-q', 'best',
                                              '--title', title, '--output', TMP_DIR), PROCESS_TIMEOUT_SECONDS, env)
            if rc is None:
                return None, True
            if rc != 0:
                log(f"[!] ani-cli-rs download exited with code {rc}: {(err or out).strip()[-200:]}")
            video = find_finished_video()
            if not video:
                continue
            video = stage_video(video, primary, target_ep)
            flags = set()
            if not verify(video, titles, need_subs=(mode == 'sub' and PREFER_SUBS), flags=flags):
                continue
            if not flags:
                return video, False
            log(f"[!] The {provider} file has no subtitle tracks: trying the other catalog before accepting it.")
            if held is None:
                held = hold_video(video)
        if held:
            break          # a usable file in the preferred version exists: do not switch to the other version
    if held:
        log("[!] No catalog offered subtitle tracks for this episode: using the file without them (it may be hardsubbed).")
        return held, False
    return None, False


# ---------- Engine: GoAnime ----------
# GoAnime has no machine-readable search, so (unlike ani-cli-rs) the show cannot be chosen by ID. It is guarded instead:
# the anime, season and episode are read from the path it writes and must match, a wrong anime is stopped as soon as
# its file appears, and the usual audio checks apply. It writes Jellyfin/Plex-style folders ("Show (2026)/Season 01/...").

_GO_GENERIC = re.compile(r'^(?:(?:season|temporada|s)\s*0*\d+|specials?|extras?|anime|animes|downloads?|goanime|tv shows?|series)$', re.I)
_GO_EP = (r'[sS]\d+\s*[eE](\d+)', r'\b[Ee]pisode\s*0*(\d+)', r'\b[Ee]p\.?\s*0*(\d+)', r'\b[Ee]0*(\d+)\b',
          r'[\s_.-]0*(\d{1,3})\s*$')
_goanime_caps = {}


def _strip_tags(text):
    text = re.sub(r'\(\s*(?:19|20)\d\d\s*\)|\[[^\]]*\]|\{[^}]*\}', ' ', text)    # (2026) [anidb-123] {...}
    return re.sub(r'\s+', ' ', text).strip(' -_.')


def goanime_identity(relpath):
    """(anime title, season, episode) read from a path GoAnime wrote; any part may be None."""
    parts = [p for p in relpath.replace('\\', '/').split('/') if p]
    if not parts:
        return None, None, None
    name, folders = parts[-1], parts[:-1]
    low = name.lower()
    cuts = [low.find(m) for m in PARTIAL_MARKERS if low.find(m) > 0]
    stem = name[:min(cuts)] if cuts else name
    if os.path.splitext(stem)[1].lower() in VIDEO_EXTS:
        stem = os.path.splitext(stem)[0]
    ep = None
    for pat in _GO_EP:
        m = re.search(pat, stem)
        if m:
            ep = int(m.group(1))
            break
    season = None
    m = re.search(r'[sS](\d+)\s*[eE]\d+', stem)
    if m:
        season = int(m.group(1))
    for f in folders:
        m = re.match(r'^(?:season|temporada|s)\s*0*(\d+)$', f, re.IGNORECASE)
        if m:
            season = int(m.group(1))
    source = next((f for f in folders if not _GO_GENERIC.match(f)), None)
    if source is None:                              # no folder: the title is what comes before the episode marker
        m = re.search(r'[sS]\d+\s*[eE]\d+|\b[Ee]pisode\b|\b[Ee]p\b', stem)
        source = stem[:m.start()] if m else re.sub(r'[\s_.-]0*\d{1,3}\s*$', '', stem)
    return (_strip_tags(source) or None), season, ep


def goanime_check(relpath, titles, target_ep):
    """Is this file the wanted anime AND episode? -> (True, '') / (False, why). Season 2+ counts as 'Season N'."""
    title, season, ep = goanime_identity(relpath)
    if not title:
        return False, 'the anime name cannot be read from the path'
    named = title + (f" Season {season}" if season and season > 1 else '')
    ok, why = result_match(named, titles)
    if not ok:
        return False, f"'{named}' is not the wanted anime ({why})"
    if ep is not None and ep != target_ep:
        return False, f"it is Ep {ep}, not Ep {target_ep}"
    return True, ''


def goanime_capabilities(help_text):
    """What this GoAnime version says it can do (from `goanime -h`)."""
    h = (help_text or '').lower()
    return {'known': bool(h.strip()), 'source_flag': '--source' in h, 'dub_flag': '--dub' in h,
            'sources': [x for x in GOANIME_KNOWN_SOURCES if re.search(r'(?<![\w-])' + re.escape(x) + r'(?![\w-])', h)]}


def goanime_pick_sources(caps, wanted):
    """Sources to try ([None] = let GoAnime search all of them)."""
    if not caps['source_flag']:
        return [None]
    if not caps['sources']:
        return list(wanted)
    return [x for x in wanted if x in caps['sources']]


def goanime_exe(env):
    return shutil.which('goanime', path=env['PATH'])


def goanime_caps(env):
    if 'caps' not in _goanime_caps:
        exe = goanime_exe(env)
        caps = None
        if exe:
            rc, out, err = run_capture([exe, '-h'], 30, env)
            if rc is not None:
                caps = goanime_capabilities(out + '\n' + err)
        _goanime_caps['caps'] = caps
    return _goanime_caps['caps']


def _tail(path, n=8):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = [re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', ln).rstrip() for ln in f.readlines()]
        return [ln for ln in lines if ln.strip()][-n:]
    except OSError:
        return []


def goanime_wrong_in_progress(titles, target_ep):
    """(path, why) of a file GoAnime is writing that is clearly NOT the wanted anime/episode, else None."""
    for root, _, files in os.walk(TMP_DIR):
        for f in files:
            low = f.lower()
            if not (low.endswith(VIDEO_EXTS) or any(m in low for m in PARTIAL_MARKERS)):
                continue
            rel = os.path.relpath(os.path.join(root, f), TMP_DIR)
            ok, why = goanime_check(rel, titles, target_ep)
            if not ok and 'cannot be read' not in why:
                return rel, why
    return None


def run_goanime(cmd, env, titles, target_ep):
    """Run goanime in its own session, output to GOANIME_OUT. Returns (status, detail): ok | wrong | timeout."""
    with open(GOANIME_OUT, 'w', encoding='utf-8') as out:
        p = subprocess.Popen(cmd, cwd=TMP_DIR, env=env, stdin=subprocess.DEVNULL, stdout=out,
                             stderr=subprocess.STDOUT, start_new_session=True)

        def kill():
            try:
                os.killpg(p.pid, signal.SIGKILL)       # also yt-dlp/ffmpeg children
            except Exception:
                pass
            p.wait()

        deadline = time.time() + PROCESS_TIMEOUT_SECONDS
        while True:
            try:
                return 'ok', str(p.wait(timeout=2))
            except subprocess.TimeoutExpired:
                pass
            wrong = goanime_wrong_in_progress(titles, target_ep)
            if wrong:
                kill()
                return 'wrong', f"{wrong[0]}: {wrong[1]}"
            if time.time() > deadline:
                kill()
                return 'timeout', ''


def finished_videos(folder):
    out = []
    for root, _, files in os.walk(folder):
        for f in files:
            low = f.lower()
            if low.endswith(VIDEO_EXTS) and not any(m in low for m in PARTIAL_MARKERS):
                out.append(os.path.join(root, f))
    return out


def recent_outside_tmp(since, limit=6):
    """Videos written during this run somewhere other than TMP_DIR (to find where a GoAnime version writes)."""
    found = []
    skip = {os.path.normpath(p) for p in (TMP_DIR, HOLD_DIR, DOWNLOAD_DIR, os.path.expanduser('~/storage'))}
    for base, depth in ((os.path.expanduser('~'), 5), (os.path.expanduser('~/storage/downloads'), 2)):
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(root, d)) not in skip and not d.startswith('.cache')]
            if root[len(base):].count(os.sep) >= depth:
                dirs[:] = []
            for f in files:
                path = os.path.join(root, f)
                try:
                    if f.lower().endswith(VIDEO_EXTS) and os.path.getmtime(path) >= since - 2:
                        found.append(path)
                except OSError:
                    pass
    return found[:limit]


def try_goanime(candidates, titles, primary, anilist_id, target_ep):
    """Returns (video | None, timed_out)."""
    env = build_env('goanime')
    exe = goanime_exe(env)
    caps = goanime_caps(env)
    if not exe or caps is None:
        log("[!] goanime is not installed or does not start (run: anilist-autodl doctor).")
        return None, False
    sources = goanime_pick_sources(caps, GOANIME_SOURCES)
    if not sources:
        log(f"[!] None of the configured GoAnime sources ({', '.join(GOANIME_SOURCES)}) is offered by this GoAnime "
            f"(it lists: {', '.join(caps['sources']) or '?'}). Set GOANIME_SOURCES.")
        return None, False
    extra = []
    if AUDIO == 'dub':
        if caps['dub_flag']:
            extra.append('--dub')
        else:
            log("[i] This GoAnime has no --dub flag: the preferred version cannot be requested from it.")
    for source in sources:
        identified = False                              # the right anime was found but its file was unusable
        for query in candidates[:3]:                    # every attempt may download an episode: keep it short
            if identified:
                break                                   # other search texts would fetch the very same stream
            clean_tmp()
            started = time.time()
            cmd = [exe, '-d'] + (['--source', source] if source else []) + ['--quality', 'best'] + extra + [query, str(target_ep)]
            log(f"[+] goanime {source or '(all sources)'}: '{query}' Ep {target_ep}...")
            status, detail = run_goanime(cmd, env, titles, target_ep)
            if status == 'timeout':
                return None, True
            if status == 'wrong':
                log(f"[!] goanime started the wrong file and was stopped: {detail}")
                continue
            videos = finished_videos(TMP_DIR)
            if not videos:
                log(f"[!] goanime finished (exit {detail}) without a video in {TMP_DIR}. Its output ends with:")
                for ln in _tail(GOANIME_OUT):
                    log(f"      | {ln}")
                for path in recent_outside_tmp(started):
                    log(f"      [i] a video was written elsewhere during this run: {path}")
                continue
            verdicts = []
            for path in sorted(videos, key=os.path.getsize, reverse=True):
                rel = os.path.relpath(path, TMP_DIR)
                ok, why = goanime_check(rel, titles, target_ep)
                verdicts.append((rel, ok, why))
                _, _, ep = goanime_identity(rel)
                if ok and (ep == target_ep or (ep is None and len(videos) == 1)):
                    video = stage_video(path, primary, target_ep, dest_dir=TMP_DIR)
                    if verify(video, titles):
                        return video, False
                    identified = True
                    break
            else:
                for rel, ok, why in verdicts[:3]:
                    log(f"[!] goanime wrote '{rel}': {why or 'the episode number cannot be read'}")
    return None, False


def try_ani_cli(candidates, titles, primary, anilist_id, target_ep):
    """Returns (verified video path | None, timed_out)."""
    other = 'sub' if AUDIO == 'dub' else 'dub'
    for mode in [AUDIO] + ([other] if AUDIO_FALLBACK else []):
        for query in candidates:
            log(f"[+] ani-cli query: '{query}' ({mode}) for Ep {target_ep}...")
            clean_tmp()  # always start from an empty temp dir: no stale files, no overwrite prompts
            outcome = run_ani_cli(query, target_ep, mode, titles)
            if outcome == 'timeout':
                return None, True
            video = find_finished_video() if outcome == 'ok' else None
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


def build_candidates(media):
    """Search texts per engine. ani-cli does not URL-encode, so it gets symbol-free text. ani-cli-rs and ani-tupi encode
    properly and catalogs contain the real punctuation ("JoJo's"): they get the original titles FIRST, then the cleaned
    ones, then the parts of 'Title: Subtitle'."""
    t = media.get('title') or {}
    eng, rom = t.get('english'), t.get('romaji')
    year = media.get('seasonYear') or (media.get('startDate') or {}).get('year')
    raw = []
    for q in (eng, rom, f"{eng} {year}" if eng and year else None, f"{rom} {year}" if rom and year else None):
        if q and q not in raw:
            raw.append(q)
    for syn in (media.get('synonyms') or [])[:2]:
        if syn and syn not in raw:
            raw.append(syn)
    cleaned = []
    for q in raw:
        q = clean_query(q)
        if q and q not in cleaned:
            cleaned.append(q)
    parts = []
    for q in (eng, rom):
        for piece in re.split(r'\s*[:\uff1a]\s+', q or ''):
            if len(piece.split()) >= 2 and piece != q and piece not in parts:
                parts.append(piece)
    rich = list(dict.fromkeys(raw + cleaned + parts))
    plain = list(dict.fromkeys(raw + cleaned))
    return {'ani-cli': cleaned, 'ani-cli-rs': rich, 'ani-tupi': plain, 'goanime': plain}


def download_anime_entry(media, target_ep):
    t = media.get('title') or {}
    eng, rom = t.get('english'), t.get('romaji')
    year = media.get('seasonYear') or (media.get('startDate') or {}).get('year')
    primary = eng or rom
    titles = all_titles(media)

    per_engine = build_candidates(media)

    runners = {'ani-cli': try_ani_cli, 'ani-cli-rs': try_ani_cli_rs, 'ani-tupi': try_ani_tupi, 'goanime': try_goanime}
    timed_out_any = False
    for n, engine in enumerate(ENGINE_CHAIN):
        if n:
            log(f"[→] Trying the backup engine: {engine}")
        candidates = per_engine[engine]
        video, timed_out = runners[engine](candidates, titles, primary, media.get('id'), target_ep)
        if timed_out:
            timed_out_any = True
            log(f"[!] TIMEOUT ({PROCESS_TIMEOUT_SECONDS // 60} min) with {engine} for '{primary}' Ep {target_ep}.")
            clean_tmp()
            continue
        if video and DRY_RUN:
            log(f"[dry-run] {engine} would deliver '{os.path.basename(video)}' (nothing was delivered or recorded).")
            clean_tmp()
            clean_hold()
            return os.path.basename(video), None
        if video and deliver(video):
            filename = os.path.basename(video)
            log(f"[✓] Ep {target_ep} of '{primary}' downloaded with {engine} and verified.")
            notify(msg('title'), msg('done', name=primary, ep=target_ep), "download_done")
            clean_tmp()
            clean_hold()
            return filename, None
        clean_tmp()
        clean_hold()
        log(f"[!] {engine} could not provide '{primary}' Ep {target_ep}.")

    if timed_out_any:
        notify(msg('timeout_t'), msg('timeout', name=primary, ep=target_ep), "error")
        return None, 'timeout'
    log(f"[!] All engines and search terms failed for '{primary}' Ep {target_ep}.")
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

    shutil.rmtree(HOLD_DIR, ignore_errors=True)    # leftovers of an interrupted run
    purge_trash()
    state = load_state()
    history, failures = state["history"], state["failures"]
    log(f"Checking AniList for user: {ANILIST_USERNAME}...")
    errors_before = LIST_ERRORS
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
    if LIST_ERRORS == errors_before:
        cleanup_left_lists(history, [(e.get('media') or {}).get('id') for e, _ in entries])
    else:
        log("[!] AniList lists are incomplete this run: skipping the cleanup of anime that left your lists.")

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


def inspect_file(path):
    """`anilist-autodl check FILE`: what is inside a video, and would it pass verification?"""
    if not shutil.which('ffprobe'):
        print("ffprobe is not installed (pkg install ffmpeg)")
        return 1
    info = probe_streams(path)
    if info is None:
        print("ffprobe could not read this file")
        return 1
    d = info['duration']
    print(f"{os.path.basename(path)}: {int(d // 60)}m{int(d % 60)}s, {os.path.getsize(path) / 1048576:.0f} MB")
    print(f"  audio tracks   : {len(info['audio'])}")
    print(f"  subtitle tracks: {info['subs']}" + ("   (+ sidecar subtitle file)" if has_sidecar_subs(path) else ""))
    problem = audio_problem(info)
    print("  verdict        : " + (f"REJECTED, {problem}" if problem else "audio OK"))
    return 0 if not problem else 2


def trace(needle):
    """`anilist-autodl trace TEXT`: take the matching entry from your Watching/Planning lists and show, without downloading
    anything, the search texts each engine would use, what ani-cli-rs's catalogs return and why each result is accepted
    or rejected, and whether the wanted episode is listed."""
    os.makedirs(TMP_DIR, exist_ok=True)
    entries = get_list(ANILIST_USERNAME, 'CURRENT') + get_list(ANILIST_USERNAME, 'PLANNING')
    low = needle.lower()
    found = [e for e in entries if any(low in t.lower() for t in all_titles(e.get('media') or {}))]
    if not found:
        print(f"Nothing on your Watching/Planning lists contains '{needle}'. Your entries:")
        for e in entries[:15]:
            print("  -", (all_titles(e.get('media') or {}) or ['?'])[0])
        return 1
    for entry in found:
        media, progress = entry.get('media') or {}, entry.get('progress') or 0
        titles, ep = all_titles(media), progress + 1
        print(f"\n=== {titles[0] if titles else '?'}   (AniList id {media.get('id')}, status {media.get('status')}, "
              f"{media.get('episodes') or '?'} episodes, your progress {progress} -> wanted Ep {ep})")
        print("  names AniList knows:")
        for t in titles:
            print(f"    {t}   [season/stage numbers: {sorted(sequel_markers(t)) or '-'}]")
        per_engine = build_candidates(media)
        for engine in ENGINE_CHAIN:
            print(f"\n  -- {engine}: search texts, in order")
            for q in per_engine[engine]:
                print(f"       {q}")
            if engine == 'goanime':
                print("       (GoAnime cannot be searched without downloading; use: anilist-autodl try \"" + needle + "\")")
            if engine != 'ani-cli-rs':
                continue
            env = build_env(engine)
            for mode in [AUDIO] + ([('sub' if AUDIO == 'dub' else 'dub')] if AUDIO_FALLBACK else []):
                for provider in RS_PROVIDERS:
                    print(f"\n  [{provider} / {mode}]")
                    shown = False
                    for q in per_engine[engine]:
                        rc, out, err = run_capture(rs_cmd(env, 'search', '--mode', mode, '--json', q, provider=provider), 90, env)
                        if rc is None or rc != 0:
                            print(f"    '{q}': {'timed out' if rc is None else 'failed: ' + (err or out).strip()[-120:]}")
                            continue
                        parsed = parse_rs_results(out)
                        pick = pick_result(parsed, titles)
                        print(f"    '{q}' -> {len(parsed)} result(s)")
                        for sid, names in parsed[:8]:
                            ok, why = result_match(names[0], titles)
                            print(f"       {'OK ' if ok else '-- '} {names[0]}   [{sid}]" + ("" if ok else f"  ({why})"))
                        if pick:
                            sid, name = pick
                            rc2, out2, _ = run_capture(rs_cmd(env, 'episodes', sid, '--mode', mode, '--json'), 90, env)
                            eps = parse_rs_episodes(out2) if rc2 == 0 else None
                            have = "unknown (could not read the list)" if eps is None else (
                                f"yes ({len(eps)} listed)" if str(ep) in eps else f"NO ({len(eps)} listed: {sorted(eps, key=float)[:12]})")
                            print(f"     => would download '{name}' [{sid}]; Ep {ep} available: {have}")
                            shown = True
                            break
                    if not shown:
                        print("     => no usable result in this catalog")
    return 0


def try_entry(args):
    """`anilist-autodl try TEXT [EP]`: run the REAL pipeline (all engines in order) for an entry of your lists, but deliver
    nothing and record nothing. Default episode: your progress + 1."""
    global DRY_RUN
    ep = int(args[-1]) if len(args) > 1 and args[-1].isdigit() else None
    needle = ' '.join(args[:-1] if ep is not None else args)
    entries = get_list(ANILIST_USERNAME, 'CURRENT') + get_list(ANILIST_USERNAME, 'PLANNING')
    found = [e for e in entries if any(needle.lower() in t.lower() for t in all_titles(e.get('media') or {}))]
    if not found:
        print(f"Nothing on your Watching/Planning lists contains '{needle}'.")
        return 1
    DRY_RUN = True
    os.makedirs(TMP_DIR, exist_ok=True)
    for entry in found:
        media = entry.get('media') or {}
        wanted = ep or (entry.get('progress') or 0) + 1
        print(f"\n=== dry run: {all_titles(media)[0] if all_titles(media) else '?'}  Ep {wanted}  (engines: {' -> '.join(ENGINE_CHAIN)})")
        name, reason = download_anime_entry(media, wanted)
        print(f"=== result: {'WOULD DELIVER ' + name if name else 'failed (' + str(reason) + ')'}")
    return 0


def doctor():
    """`anilist-autodl doctor`: check every engine in use and show what ani-cli-rs really returns."""
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"Engines: {' -> '.join(ENGINE_CHAIN)}   audio={AUDIO} (fallback={AUDIO_FALLBACK})   prefer-subs={PREFER_SUBS}")
    print(f"ffprobe: {'ok' if shutil.which('ffprobe') else 'MISSING (pkg install ffmpeg): audio is not checked'}")
    for engine in ENGINE_CHAIN:
        env = build_env(engine)
        print(f"\n== {engine}")
        if engine == 'ani-tupi':
            rc, out, err = run_capture([sys.executable, HELPER, '--selftest'], 60, env)
            print(f"  selftest: {(out or err).strip() or rc}")
        elif engine == 'ani-cli':
            exe = shutil.which('ani-cli', path=env['PATH'])
            print(f"  binary: {exe or 'MISSING'}")
        elif engine == 'goanime':
            exe = goanime_exe(env)
            print(f"  binary: {exe or 'MISSING'}")
            if exe:
                rc, out, err = run_capture([exe, '-h'], 30, env)
                caps = goanime_capabilities(out + '\n' + err)
                print(f"  --source flag: {caps['source_flag']}   --dub flag: {caps['dub_flag']}   sources it lists: {', '.join(caps['sources']) or '(none found)'}")
                print(f"  sources this tool will use: {', '.join(x or '(all)' for x in goanime_pick_sources(caps, GOANIME_SOURCES)) or 'NONE (set GOANIME_SOURCES)'}")
                first = [ln for ln in (out + err).splitlines() if ln.strip()][:3]
                print("  help starts with: " + ' | '.join(first)[:200])
        else:
            rc, out, err = run_capture(rs_cmd(env, '--version'), 30, env)
            if rc != 0:
                print(f"  binary: MISSING or broken ({(err or out).strip()[:120]})")
                continue
            print(f"  version: {out.strip()}")
            for provider in RS_PROVIDERS:
                rc, out, err = run_capture(rs_cmd(env, 'search', '--mode', 'sub', '--json', 'frieren', provider=provider), 90, env)
                if rc is None:
                    print(f"  {provider}: search timed out")
                    continue
                parsed = parse_rs_results(out)
                print(f"  {provider}: exit {rc}, {len(parsed)} result(s) understood")
                for sid, names in parsed[:3]:
                    print(f"     {sid}  {names[0]}")
                if rc == 0 and not parsed:
                    print("     could not parse this output, please report its first lines:")
                    print("     " + (out or err).strip()[:300].replace('\n', '\n     '))
    return 0


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--inspect':
        sys.exit(inspect_file(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == '--doctor':
        sys.exit(doctor())
    elif len(sys.argv) > 2 and sys.argv[1] == '--trace':
        sys.exit(trace(' '.join(sys.argv[2:])))
    elif len(sys.argv) > 2 and sys.argv[1] == '--try':
        sys.exit(try_entry(sys.argv[2:]))
    else:
        main()
