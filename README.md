# anilist-autodl — Anime Downloader for Termux

**English** · [Português](README.pt-BR.md)

Auto-downloads the episodes on your AniList lists to your Android phone, so they are ready to watch offline.
Choose the sources when you install:

| You pick | Main engine | Backup | Sources |
| --- | --- | --- | --- |
| English | [ani-cli-rs](https://github.com/vorlie/ani-cli-rs) | [ani-cli](https://github.com/pystardust/ani-cli) | English sub/dub; ani-cli-rs embeds subtitles in the file |
| Português | [ani-tupi](https://github.com/levyvix/ani-tupi) | none | Brazilian Portuguese (dublado/legendado) |

You can change the main and backup engine in *Custom* mode (any of the three, in any order). The backup is used whenever the
main engine cannot deliver a valid file: wrong anime, no audio, not found, provider down, timeout.

> ani-cli-rs and ani-tupi are new here. They were built against their documentation / source and tested with simulated
> sources, not with the live sites. If something misbehaves, run `anilist-autodl doctor` and attach its output and the
> `[helper]` / `ani-cli-rs` lines from `anilist-autodl logs` to an issue.

## What it does

Checks your AniList lists on a schedule (default: every hour, Wi-Fi only):

- **Watching:** the next unwatched episodes of airing anime (default 1 ahead), plus up to 3 ahead for finished anime.
- **Planning:** Ep 1 of planned anime once it starts airing.
- **Dub or sub:** your preferred version, with an optional fallback to the other one.
- **Cleanup:** watched episodes move to a hidden `.trash` folder and are deleted for good after 3 days. Anime that leave your Watching/Planning lists
  (**Completed**, Dropped, Paused) are cleaned too: every file this tool downloaded for them is trashed. If you lower your progress on AniList, a trashed episode is restored
  instead of downloaded again.
- **Storage guard:** pauses below 2 GB free (the trash is emptied first).
- **Safety checks:** every file is verified before it reaches your download folder: size, readable, duration, matching
  title and **an audio track** (a video without sound, or with audio that stops early, is rejected and the next source is
  tried). This reuses the one `ffprobe` call that already measured the duration, so it costs nothing extra.
- **Subtitles (ani-cli-rs):** it downloads the provider's subtitle tracks and, with ffmpeg, embeds them in the MP4. If a
  subtitled file comes without any, the other ani-cli-rs catalog is tried first; if none has subtitles the file is still kept
  (it may have hardsubs) and the log says so. Hardsubs cannot be detected, only subtitle tracks.
- **Exact anime:** ani-cli-rs is asked for the show by its ID, chosen with the same strict title check, instead of "the first
  search result".
- **Notifications:** download finished, timeout, first failure of an episode, low storage. English or Portuguese.
- **Auto-update:** keeps the engines fresh. ani-tupi updates are self-tested and **rolled back** automatically if a new
  version stops working with this tool. ani-cli-rs is rebuilt from source only when its repository changed, and the new build
  replaces the installed one only after it passes a self-test (the old binary is kept as a backup).

## 1. Install

1. Install **Termux** and **Termux:API** from [F-Droid](https://f-droid.org/packages/com.termux/) (or GitHub). Both from
   the same source, **not** the Play Store.
2. Open Termux and run the installer straight from GitHub:

```
curl -fsSL https://raw.githubusercontent.com/nmfassis/anilist-autodl/main/install.sh | bash
```

3. Answer the questions. *Quick* mode only asks language (which also picks the sources), your AniList username and dub/sub.
   *Custom* asks everything, including the sources separately from the language:

| Question | Default |
| --- | --- |
| Language (also picks the engines) | English → ani-cli-rs + ani-cli backup, Português → ani-tupi |
| *Custom:* main engine, backup engine | by language |
| *Custom:* retry the other ani-cli-rs catalog when a subtitled file has no subtitle tracks | yes |
| AniList username | – |
| Dub or sub (+ fallback to the other) | sub, fallback on |
| Download folder | `/sdcard/Download/Anime` |
| Episodes in advance: finished / airing | 3 / 1 |
| Download Ep 1 of planned anime | yes |
| Check every | 1h (minimum 15m, an Android limit) |
| Retry a failed episode after | 6 h |
| Give up on one download after | 60 min |
| Pause below this free space | 2 GB |
| Days in the trash | 3 |
| Wi-Fi only / skip when battery is low | yes / yes |
| Automatic engine updates / check every | yes / 7 days |

4. Allow notifications for Termux:API (Android Settings > Apps > Termux:API > Notifications).
5. Android Settings > Apps > **Termux** and **Termux:API** > Battery > **Unrestricted**. Without this Android may kill long downloads.

**Good to know**

- The installer starts with `pkg update && pkg upgrade`. It can take several minutes and may update Termux's own tools.
  If it stops or Termux restarts during that step, **run the same command again**: your answers are saved first and it continues.
- With ani-tupi the first install compiles `pydantic-core` (5–15 min). Keep Termux open; the installer holds a wake lock.
- ani-cli-rs has **no Android binary**, so the installer builds it from source with Rust (5–15 min, up to 4 build jobs so a
  phone does not run out of memory). If the build fails, the installer keeps going with the backup engine as the main one
  and tells you; run it again to retry.
- ani-tupi needs Python 3.12 or newer (current Termux has it).
- Prefer a file? `bash install.sh` from a checkout works too, and so does the old `install_anime_downloader.sh`.

### Unattended install

```
curl -fsSL https://raw.githubusercontent.com/nmfassis/anilist-autodl/main/install.sh | bash -s -- \
  --yes --lang pt --username YOUR_NAME --set AUDIO=dub --set AHEAD_FINISHED=5 --set INTERVAL_MINUTES=2h
```

`--lang en|pt`, `--engine ani-cli|ani-tupi`, `--username`, `--mode quick|custom`, `--set KEY=VALUE` (any key from the
table below), `--yes`, `--no-run`, `--reconfigure`, `--uninstall`.

## 2. Everyday use

```
anilist-autodl run        # check AniList and download now, with live output
anilist-autodl status     # settings, scheduled job, engine version, last log lines
anilist-autodl logs       # follow the log (add "full" for yt-dlp/ffmpeg output)
anilist-autodl update     # update the engines now
anilist-autodl doctor     # test every engine and show what ani-cli-rs really returns
anilist-autodl check FILE # audio/subtitle tracks of a video and whether it would be accepted
anilist-autodl retry      # forget failed episodes so they are retried on the next run
anilist-autodl config     # change any setting (re-runs the questions)
anilist-autodl job        # run once through Android's scheduler, like the automatic runs
```

## 3. Settings

Stored in `~/.config/anilist-autodl/config` (`KEY='value'` lines). Change them with `anilist-autodl config`, or edit the
file; the next run picks them up. After changing `INTERVAL_MINUTES`, `WIFI_ONLY` or `BATTERY_NOT_LOW` use
`anilist-autodl config` so the schedule is re-registered.

| Key | Default | Meaning |
| --- | --- | --- |
| `AUTODL_LANG` | `en` | `en` or `pt` (notification language) |
| `AUTODL_ENGINE` | by language | main engine: `ani-cli-rs`, `ani-cli` or `ani-tupi` |
| `AUTODL_BACKUP_ENGINE` | `ani-cli` (English) / empty | used when the main engine fails; empty = none |
| `PREFER_SUBS` | `true` | ani-cli-rs: a `sub` file without subtitle tracks makes it try the other catalog before accepting it |
| `ANILIST_USERNAME` | – | your AniList name |
| `AUDIO` / `AUDIO_FALLBACK` | `sub` / `true` | preferred version; accept the other one if missing |
| `DOWNLOAD_DIR` | `/sdcard/Download/Anime` | final folder |
| `AHEAD_FINISHED` / `AHEAD_AIRING` | `3` / `1` | episodes ahead (airing is capped at released episodes) |
| `DOWNLOAD_PLANNING` | `true` | Ep 1 of planned anime once airing |
| `INTERVAL_MINUTES` | `60` | schedule (minimum 15) |
| `RETRY_COOLDOWN_HOURS` | `6` | wait before retrying a failed episode |
| `TIMEOUT_MINUTES` | `60` | max time per download attempt |
| `MIN_FREE_GB` | `2` | pause below this free space |
| `TRASH_DAYS` | `3` | days watched episodes stay in `.trash` |
| `WIFI_ONLY` / `BATTERY_NOT_LOW` | `true` / `true` | scheduler constraints |
| `AUTO_UPDATE` / `UPDATE_EVERY_DAYS` | `true` / `7` | engine updates |

**Dub/sub with ani-tupi** depends on the source: the title must say *Dublado*/*Dub* for it to be recognised. With ani-cli
the `--dub` flag is used.

## 4. Files

- `~/.anilist-autodl/` — the scripts (`fetch_anime.py`, `fetch_episode_tupi.py`, `run.sh`, `update.sh`, `install.sh`) and the
  ani-cli-rs sources (`ani-cli-rs-src/`, built by the installer)
- `~/.config/anilist-autodl/config` — your settings
- `~/.anime_downloader.log` / `~/.anime_downloader_output.log` — script log / full output
- `~/.anime_downloader_state.json` — history and failure timestamps
- `~/.anime_tmp/` — temporary download folder (emptied automatically)

## 5. Upgrading from 1.x

Run the installer again. It reads your old username and folder, moves the old `~/fetch_anime.py` and
`~/run_downloader.sh` to `*.bak` / `*.old`, keeps your history and re-registers the job.

## 6. Uninstall

```
anilist-autodl uninstall
```

Your downloaded episodes are not touched.

## 7. Troubleshooting

- **The installer stopped during `pkg upgrade`:** run the same command again; your answers were saved.
- **`ani-tupi` search is slow / `Jikan API timeout`:** not an issue for this tool; the downloader turns that lookup off.
- **An episode keeps failing:** it is retried after the cooldown. `anilist-autodl logs full` shows why. With ani-tupi the
  `[helper]` lines say whether the title was not found, the episode is not out yet, or no stream was found.
- **A new ani-tupi version broke things:** the updater self-tests it and rolls back, notifying you once. Check
  `anilist-autodl status`.
- **ani-cli: "printf: Argument list too long":** the script already runs ani-cli with Termux's `sh`; if it returns, run
  `termux-fix-shebang $PREFIX/bin/ani-cli`.
- **"Overwrite? [y/N]" or "No such file" from ffmpeg:** make sure `~/.config/yt-dlp/config` has no `--force-overwrite` or
  `--no-m3u8-fixup` (the installer removes them) and only one copy of the job runs.
- **A video has no sound / the audio stops early:** since 2.1 such files are rejected automatically and the next source is
  tried (see the log line `no audio track`). To inspect any file yourself: `anilist-autodl check "/sdcard/Download/Anime/Show Episode 3.mp4"`.
- **ani-cli-rs finds nothing or `could not parse this output`:** run `anilist-autodl doctor`. It shows what each catalog
  returns. The parser was written from the documentation and accepts several field names; if yours differs, attach the
  first lines `doctor` prints to an issue.
- **A file has no subtitles:** the log line says `NO subtitle tracks` when ani-cli-rs delivered one without tracks. Such a
  file may be hardsubbed (subtitles burned into the picture), which cannot be detected. Files from ani-cli or ani-tupi are
  never checked for subtitles.
- **The ani-cli-rs build fails (out of memory):** close other apps and run the installer again, or pick ani-cli as the main
  engine in *Custom* mode.
- **A wrong anime was downloaded (fixed in 2.0.1):** delete that file from your download folder. The episode it was
  recorded for is then downloaded again, now with the strict title check. If you watched/progressed an anime and files of
  another one were moved to `.trash`, restore them from `<download folder>/.trash`.
- **An episode is "failing" although the anime exists:** the log line `does not match any known title (...)` shows which
  names were compared. If the source uses a very different name, add it as a synonym on the anime's AniList page.
- **A completed anime still has files:** only files this tool downloaded (it keeps a record of each one) are trashed, never
  files you added yourself, and files from very old versions have no record. Nothing is trashed in a run where an AniList
  list failed to load (see `anilist-autodl logs`). Delete such files by hand.
- **A paused/dropped anime was trashed:** by design, anime that leave Watching/Planning lose their downloaded files after
  `TRASH_DAYS`. Put it back on Watching within that time and the episodes are restored from `.trash`.
- **Wrongly marked an episode as watched:** it sits in `<download folder>/.trash` for 3 days. Lower your progress on AniList
  and the next run restores it, or move the files back by hand.
- **Nothing runs automatically:** `termux-job-scheduler --pending` should list job 1. If not, run `anilist-autodl config`.
  Also check the battery setting from step 1.5.
- **No notifications:** Termux:API must be installed (same source as Termux) and allowed to post notifications.

## Tests

`python3 -m unittest discover -s tests -v` (no network or Termux needed) covers the title matching.

## AI disclosure

This project was **100% made with AI**. All code, scripts and documentation were written by AI assistants (Google Gemini for
the first versions, then Anthropic's Claude). I directed the work through prompts and ran it on a real phone, but I did not
write any of it by hand. Read the code before you run it and use it at your own risk.

## Disclaimer

This tool does not host or provide any content. It automates ani-cli / ani-tupi, which search third-party sources. You are
responsible for following the copyright laws and terms of service that apply to you. The software is provided "as is",
without warranty of any kind. Not affiliated with AniList, ani-cli or ani-tupi.

## Credits

- [ani-cli-rs](https://github.com/vorlie/ani-cli-rs), [ani-cli](https://github.com/pystardust/ani-cli) (GPL-3.0) and
  [ani-tupi](https://github.com/levyvix/ani-tupi), downloaded or built at install time, not redistributed here.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org), [Termux](https://termux.dev) and the
  [AniList API](https://anilist.gitbook.io/anilist-apiv2-docs/).

## License

[MIT](LICENSE)
