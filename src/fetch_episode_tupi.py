#!/usr/bin/env python3
"""Download ONE episode with ani-tupi, without menus. Used by fetch_anime.py.

argv[1] = JSON {"queries": [...], "titles": [...], "episode": N, "anilist_id": ID|null,
                "audio": "sub"|"dub", "fallback": true|false}
Prints a final line:  ANI_TUPI_RESULT {"ok": true, "path": "...", "title": "..."}
Progress lines start with "[helper] ".

argv[1] = --selftest   checks that the installed ani-tupi still offers everything this helper uses
                       (exit 0 = compatible). The updater runs it and rolls back when it fails.
"""
import json
import os
import re
import sys

RESULT_PREFIX = 'ANI_TUPI_RESULT '
MIN_SCORE = 0.6

# Words that carry no identity (language/audio tags, season words, filler).
STOP = {'the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'for', 'on', 'with', 'is', 'at', 'by',
        'this', 'that', 'your', 'you', 'my', 'i', 'it', 'season', 'part', 'cour', 'episode', 'ep',
        'temporada', 'parte', 'dublado', 'legendado', 'dub', 'sub', 'todos', 'episodios', 'online',
        'hd', 'nd', 'rd', 'th', 'st'}
ROMAN = {'ii': 2, 'iii': 3, 'iv': 4}


def say(msg):
    print(f"[helper] {msg}", flush=True)


def emit(obj):
    print(RESULT_PREFIX + json.dumps(obj, ensure_ascii=False), flush=True)


def words(s):
    """Identity words of a title: letters only, no stopwords, no numbers."""
    s = re.sub(r'[\d_]+', ' ', s.lower())
    s = re.sub(r'[^\w\s]+', ' ', s)
    return {w for w in s.split() if w not in STOP and w not in ROMAN and len(w) > 1}


def markers(s):
    """Season/sequel numbers in a title ('2nd Season', 'Part 2', 'II', '2a Temporada'). Years are ignored."""
    nums = {int(n) for n in re.findall(r'\d+', s) if int(n) < 1900}
    for w in re.sub(r'[^\w\s]+', ' ', s.lower()).split():
        if w in ROMAN:
            nums.add(ROMAN[w])
    return nums


def score(expected_titles, candidate):
    """0..1 similarity between a scraper title and the known AniList names."""
    cand_w, cand_m = words(candidate), markers(candidate)
    if not cand_w:
        return 0.0
    best = 0.0
    for t in expected_titles:
        exp_w, exp_m = words(t), markers(t)
        if not exp_w:
            continue
        covered = len(exp_w & cand_w) / len(exp_w)          # how much of the expected title is present
        extra = len(cand_w - exp_w) / len(cand_w)           # how much unrelated stuff the candidate adds
        s = covered - 0.3 * extra
        if exp_m != cand_m:                                  # "Dandadan" vs "Dandadan 2nd Season"
            s -= 0.4
        best = max(best, s)
    return best


DUB_RE = re.compile(r'\b(dublado|dublada|dublagem|dub|dubbed)\b', re.IGNORECASE)


def is_dub(title):
    return bool(DUB_RE.search(title))


def pick_title(candidates, expected_titles, audio='sub', fallback=True):
    """Best scraper title for the wanted anime, or None when nothing is convincing.

    Only titles that really match the anime are considered. Among those, the preferred version
    (dub / sub) wins; if there is none, the other version is used when `fallback` is true.
    Ties go to the plainest (shortest) title, e.g. 'X' over 'X Dublado'.
    """
    good = [(score(expected_titles, c), c) for c in candidates]
    good = [(sc, c) for sc, c in good if sc >= MIN_SCORE]
    if not good:
        return None

    def best(pool):
        return sorted((-round(sc, 4), len(c), c) for sc, c in pool)[0][2]

    preferred = [(sc, c) for sc, c in good if is_dub(c) == (audio == 'dub')]
    if preferred:
        return best(preferred)
    return best(good) if fallback else None


def selftest():
    """Exit code 0 when the installed ani-tupi still has the internals this helper calls."""
    import inspect
    try:
        from scrapers import loader
        from services.repository import rep
        from services.anime.download_service import AnimeDownloadService
        from services.anime.download_catalog import stable_anime_directory   # noqa: F401
        from models.config import settings
    except Exception as e:
        print(f"selftest: import failed: {e!r}")
        return 1
    problems = []
    for name in ('register', 'clear_search_results', 'search_anime', 'search_episodes',
                 'get_episode_list', 'search_player', 'anime_to_urls'):
        if not hasattr(rep, name):
            problems.append(f"repository.{name} is missing")
    if not callable(getattr(loader, 'load_plugins', None)):
        problems.append("scrapers.loader.load_plugins is missing")
    try:
        params = set(inspect.signature(AnimeDownloadService.download_episodes).parameters)
        for p in ('anime_title', 'range_input', 'total_episodes', 'get_episode_url',
                  'anilist_id', 'season', 'silent', 'max_attempts'):
            if p not in params:
                problems.append(f"download_episodes() has no '{p}' parameter")
        settings.anime_download.download_directory   # noqa: B018
        settings.anime_download.video_format         # noqa: B018
    except Exception as e:
        problems.append(f"download API changed: {e!r}")
    if problems:
        print("selftest: incompatible ani-tupi: " + "; ".join(problems))
        return 1
    print("selftest: ok")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--selftest':
        sys.exit(selftest())
    args = json.loads(sys.argv[1])
    queries, titles = args['queries'], args['titles']
    episode, anilist_id = int(args['episode']), args.get('anilist_id')
    audio, fallback = args.get('audio', 'sub'), bool(args.get('fallback', True))

    try:
        from scrapers import loader
        from services.repository import rep
        from services.anime.download_service import AnimeDownloadService
        from services.anime.download_catalog import stable_anime_directory
        from models.config import settings
    except Exception as e:  # ani-tupi missing or its internals changed
        emit({'ok': False, 'reason': 'import', 'detail': repr(e)})
        return

    loader.load_plugins(rep.register)
    reason = 'not_found'

    for query in queries:
        say(f"searching '{query}'")
        try:
            rep.clear_search_results()
            rep.search_anime(query, verbose=False)
        except Exception as e:
            say(f"search failed: {e!r}")
            reason = 'search_error'
            continue

        found = list(rep.anime_to_urls.keys())
        title = pick_title(found, titles, audio, fallback)
        if not title:
            say(f"{len(found)} result(s), none matches the expected title ({audio} preferred"
                f"{', other version allowed' if fallback else ', no fallback'})")
            continue

        say(f"matched '{title}'")
        try:
            rep.search_episodes(title)
            episodes = rep.get_episode_list(title)
        except Exception as e:
            say(f"episode listing failed: {e!r}")
            reason = 'episodes_error'
            continue
        if episode not in episodes:
            say(f"episode {episode} not available yet (sources have {len(episodes)} episode(s))")
            reason = 'episode_missing'
            continue

        try:
            player_url = rep.search_player(title, episode)
        except Exception as e:
            say(f"could not resolve a stream: {e!r}")
            reason = 'stream_error'
            continue
        if not player_url:
            say('no playable stream found')
            reason = 'no_stream'
            continue

        dl_title = re.sub(r'[\\/]+', ' ', title).strip()   # the download service rejects path separators
        service = AnimeDownloadService()
        try:
            result = service.download_episodes(
                anime_title=dl_title,
                range_input=str(episode),
                total_episodes=max(episodes),
                get_episode_url=lambda _n, u=player_url: (u, 'unknown'),
                anilist_id=anilist_id,
                season=1,
                silent=True,
                max_attempts=2,
            )
        except Exception as e:
            say(f"download failed: {e!r}")
            reason = 'download_error'
            continue

        path = stable_anime_directory(service.download_dir, dl_title, anilist_id) / \
            f"{episode}.{settings.anime_download.video_format}"
        if (result.successful or result.skipped) and path.exists():
            emit({'ok': True, 'path': str(path), 'title': title})
            return
        say(f"download did not produce a file ({result.summary})")
        reason = 'download_failed'

    emit({'ok': False, 'reason': reason})


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        emit({'ok': False, 'reason': 'crash', 'detail': repr(exc)})
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)   # leave no browser/worker threads behind
