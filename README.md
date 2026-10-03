# Anime Downloader for Termux

Auto-downloads your AniList anime episodes on Android with ani-cli.

Checks your AniList lists every hour and downloads new episodes with ani-cli, only on Wi-Fi.

- **Watching:** next unwatched episode of airing anime, plus up to 3 ahead for finished anime.
- **Planning:** Ep 1 of planned anime once it starts airing.
- **Cleanup:** watched episodes (and their subtitles) move to a hidden `.trash` folder inside the download folder and are deleted for good after 3 days. If you lower your progress on AniList, a trashed episode is restored instead of downloaded again.
- **Storage guard:** downloads pause when free space is under 2 GB (the trash is emptied first to make room).
- **Notifications:** download finished, timeout, first failure of an episode, and low storage (at most once a day).

## 1. Install from scratch

1. Install **Termux** and **Termux:API** from F-Droid (or GitHub). Both must come from the same source. Not the Play Store.
2. Open Termux and run `termux-setup-storage`, then allow storage access.
3. Copy `install_anime_downloader.sh` to your phone's Downloads folder, then in Termux:
   ```
   bash ~/storage/downloads/install_anime_downloader.sh
   ```
   (or `bash ~/storage/downloads/install_anime_downloader.sh YOUR_ANILIST_NAME` to skip the question)
4. Allow notifications for Termux:API (Android Settings > Apps > Termux:API > Notifications).
5. Android Settings > Apps > **Termux** and **Termux:API** > Battery > **Unrestricted** (or "Don't optimize"). Without this Android may kill long downloads.

The installer is safe to re-run any time. It updates everything in place and keeps your history.

## 2. Everyday use

| What | Command |
|---|---|
| Watch the script log live | `tail -f ~/.anime_downloader.log` |
| Watch full output (yt-dlp progress, errors) | `tail -f ~/.anime_downloader_output.log` |
| Run a check right now (through Android, like the hourly job) | `termux-job-scheduler --job-id 2 --script ~/run_downloader.sh --network unmetered --battery-not-low true` |
| Run by hand in Termux | `~/run_downloader.sh` |
| See scheduled jobs | `termux-job-scheduler --pending` |
| Retry failed episodes immediately | `rm ~/.anime_downloader_state.json` |

## 3. Settings (top of `~/fetch_anime.py`, edit with `nano ~/fetch_anime.py`)

| Setting | Default | Meaning |
|---|---|---|
| `ANILIST_USERNAME` | set by installer | Your AniList name |
| `DOWNLOAD_DIR` | `/sdcard/Download/Anime` | Final folder |
| `ADVANCE_DOWNLOAD_LIMIT` | 3 | Episodes ahead for finished anime |
| `DOWNLOAD_PLANNING` | True | Grab Ep 1 of planned, airing anime |
| `RETRY_COOLDOWN_HOURS` | 6 | Wait before retrying a failed episode |
| `PROCESS_TIMEOUT_SECONDS` | 3600 | Max time per download attempt |
| `MAX_LOG_SIZE_MB` | 5 | Log is trimmed above this |
| `MIN_FREE_GB` | 2 | Pause downloads below this much free storage |
| `LOW_SPACE_NOTIFY_HOURS` | 24 | Minimum time between low-storage notifications |
| `TRASH_DAYS` | 3 | Days watched episodes stay in `.trash` before final deletion |

To change the schedule (the interval is in milliseconds), re-register with the same job ID:
```
termux-job-scheduler --job-id 1 --script ~/run_downloader.sh --period-ms 7200000 --network unmetered --battery-not-low true --persisted true
```

## 3b. Files it uses

- `~/fetch_anime.py`: the downloader (a backup of the previous version is kept as `.bak`)
- `~/run_downloader.sh`: what the Android scheduler runs (wake lock, ani-cli update, logs)
- `~/.anime_downloader_state.json`: history and failure timestamps
- `~/.anime_tmp/`: temporary download folder (emptied automatically)
- `~/.anime_downloader.lock`: prevents two copies running at once

## 4. Uninstall

```
termux-job-scheduler --cancel-all
rm -f ~/fetch_anime.py* ~/run_downloader.sh ~/.anime_downloader* ~/.anime_download_history.json
rm -rf ~/.anime_tmp
```
Your downloaded episodes in `/sdcard/Download/Anime` are not touched.

## 5. Troubleshooting

- **"printf: Argument list too long"**: ani-cli running under Android's `sh`. The script runs it with Termux's `sh` already. If it returns, run `termux-fix-shebang $PREFIX/bin/ani-cli`.
- **"Overwrite? [y/N]" or "No such file" from ffmpeg:** make sure `~/.config/yt-dlp/config` doesn't contain `--force-overwrite` or `--no-m3u8-fixup`, and only one copy of the job is running.
- **`yt-dlp: not found`:** `pip uninstall yt-dlp -y; pkg reinstall python-yt-dlp -y`
- **Wrongly marked an episode as watched:** it's in `/sdcard/Download/Anime/.trash` for 3 days. Lower your progress on AniList and the next run restores it, or move the files back by hand.
- **"Downloads paused" / low-storage notification:** free up space; the next hourly run continues on its own.
- **Same episode keeps failing:** it's retried after the cooldown. Check `~/.anime_downloader_output.log` for the reason (source down, wrong anime, no source yet).
- **Nothing runs hourly:** `termux-job-scheduler --pending` should list job 1. If it doesn't, re-run the installer. Also check the battery setting from step 1.5.
- **No notifications:** the Termux:API app must be installed and allowed to post notifications.
- **ani-cli broken after a site change:** `ani-cli -U` updates it. The hourly job does this automatically.

## AI disclosure

This project was **100% made with AI**. All code, scripts and documentation were written by AI assistants (Google Gemini for the first versions, then Anthropic's Claude). I directed the work through prompts and ran it on a real phone, but I did not write any of it by hand. It has only been tested on my own setup, so read the code before you run it and use it at your own risk.

## Disclaimer

This tool does not host or provide any content. It automates ani-cli, which searches third-party sources. You are responsible for following the copyright laws and terms of service that apply to you. The software is provided "as is", without warranty of any kind.

## Credits

- [ani-cli](https://github.com/pystardust/ani-cli) (GPL-3.0). It is downloaded at install time, not redistributed here.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org), [Termux](https://termux.dev) and the [AniList API](https://anilist.gitbook.io/anilist-apiv2-docs/).

## License

[MIT](LICENSE)
