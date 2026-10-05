# anilist-autodl — Anime Downloader for Termux

**English** · [Português](README.pt-BR.md)

Auto-downloads the episodes on your AniList lists to your Android phone, so they are ready to watch offline.
Choose the sources when you install:

| You pick | Engine | Sources |
| --- | --- | --- |
| English | [ani-cli](https://github.com/pystardust/ani-cli) | English sub/dub |
| Português | [ani-tupi](https://github.com/levyvix/ani-tupi) | Brazilian Portuguese (dublado/legendado) |

> The ani-tupi engine is new in 2.0. It was built against ani-tupi's source and tested with simulated sources;
> please open an issue if a source misbehaves on your phone (attach the `[helper]` lines from `anilist-autodl logs`).

## What it does

Checks your AniList lists on a schedule (default: every hour, Wi-Fi only):

- **Watching:** the next unwatched episodes of airing anime (default 1 ahead), plus up to 3 ahead for finished anime.
- **Planning:** Ep 1 of planned anime once it starts airing.
- **Dub or sub:** your preferred version, with an optional fallback to the other one.
- **Cleanup:** watched episodes move to a hidden `.trash` folder and are deleted for good after 3 days. If you lower your
  progress on AniList, a trashed episode is restored instead of downloaded again.
- **Storage guard:** pauses below 2 GB free (the trash is emptied first).
- **Safety checks:** every file is verified (size, duration, matching title) before it reaches your download folder.
- **Notifications:** download finished, timeout, first failure of an episode, low storage. English or Portuguese.
- **Auto-update:** keeps the engine fresh. ani-tupi updates are self-tested and **rolled back** automatically if a new
  version stops working with this tool.

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
| Language / engine | English → ani-cli, Português → ani-tupi |
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
anilist-autodl update     # update the engine now
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
| `AUTODL_ENGINE` | by language | `ani-cli` or `ani-tupi` |
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

- `~/.anilist-autodl/` — the scripts (`fetch_anime.py`, `fetch_episode_tupi.py`, `run.sh`, `update.sh`, `install.sh`)
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
- **Wrongly marked an episode as watched:** it sits in `<download folder>/.trash` for 3 days. Lower your progress on AniList
  and the next run restores it, or move the files back by hand.
- **Nothing runs automatically:** `termux-job-scheduler --pending` should list job 1. If not, run `anilist-autodl config`.
  Also check the battery setting from step 1.5.
- **No notifications:** Termux:API must be installed (same source as Termux) and allowed to post notifications.

## AI disclosure

This project was **100% made with AI**. All code, scripts and documentation were written by AI assistants (Google Gemini for
the first versions, then Anthropic's Claude). I directed the work through prompts and ran it on a real phone, but I did not
write any of it by hand. Read the code before you run it and use it at your own risk.

## Disclaimer

This tool does not host or provide any content. It automates ani-cli / ani-tupi, which search third-party sources. You are
responsible for following the copyright laws and terms of service that apply to you. The software is provided "as is",
without warranty of any kind. Not affiliated with AniList, ani-cli or ani-tupi.

## Credits

- [ani-cli](https://github.com/pystardust/ani-cli) (GPL-3.0) and [ani-tupi](https://github.com/levyvix/ani-tupi), downloaded
  at install time, not redistributed here.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org), [Termux](https://termux.dev) and the
  [AniList API](https://anilist.gitbook.io/anilist-apiv2-docs/).

## License

[MIT](LICENSE)
