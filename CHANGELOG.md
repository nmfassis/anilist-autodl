# Changelog

## 2.1.0
- **New English engine: [ani-cli-rs](https://github.com/vorlie/ani-cli-rs)**, with **ani-cli as backup**. It is the default for
  English; built from source by the installer (Termux has no prebuilt binary).
- **Backup engine** for any combination (`AUTODL_BACKUP_ENGINE`): used when the main engine yields no valid file (wrong
  anime, no audio, not found, provider down, timeout).
- **Audio check on every download, with every engine:** a video without an audio track, or whose audio stops early, is
  rejected and the next source is tried. It reuses the `ffprobe` call that already measured the duration.
- ani-cli-rs picks the show **by ID** from `search --json` using the strict title check (no more "first result"), tries both
  of its catalogs, skips a catalog that does not answer, and renames the result to `<Title> Episode N`.
- **Subtitles:** ani-cli-rs embeds the provider's subtitle tracks (mov_text) in the MP4. A `sub` file without any makes it try
  the other catalog first (`PREFER_SUBS`); if none has them the file is kept and the log says so (hardsubs cannot be detected).
- Safe ani-cli-rs updater: rebuilds only when the repository changed and swaps the binary only after a self-test, keeping the
  old one. (ani-cli-rs's own `update` is not used: it installs prebuilt releases that do not exist for Android.)
- New commands: `anilist-autodl doctor` (test every engine, show what ani-cli-rs returns) and `anilist-autodl check FILE`.
- Installer: engine/backup questions in Custom mode, ani-cli-rs build step (a failed build falls back to the backup engine),
  an old ani-cli config is offered the new defaults when you re-run it interactively (unattended runs never switch engines).
- Fixed: `--set YES_NO_KEY=maybe` was saved as an empty value instead of being rejected.
- Added `tests/test_streams.py` (real ffmpeg-generated videos; skipped without ffmpeg).

## 2.0.2
- **Fixed: episodes of anime you finished were never trashed.** Only your Watching list was cleaned, and an anime leaves it
  when you complete it (AniList does this by itself when you log the last episode). Now the files this tool downloaded for any
  anime that is no longer on your Watching/Planning lists (Completed, but also Dropped, Paused or removed) move to `.trash`
  and are deleted after `TRASH_DAYS`.
- It works from the tool's own records (`<AniList id>_<episode>` → file name), so it needs **no extra AniList request**, never
  guesses from file names (a sequel is never confused with its first season) and never touches files you added yourself.
- Safety: nothing is trashed when an AniList list failed to load in that run. An answer with an error (for example a mistyped
  username) is now counted as a failure instead of looking like an empty list.
- Added `tests/test_cleanup.py`.

## 2.0.1
- **Fixed: wrong anime downloaded.** A file was accepted when only half of the wanted title's words were in its name, so
  "Magical Explorer" accepted "Magical Girl Magical Destroyers" (they share "magical"). Matching is now strict: at least
  80 % of the title's words must be present and a short title allows no unrelated extra words (so "Sword Art Online"
  no longer accepts "Sword Art Online Alicization"). Tags such as `(Dub)`, `[1080p]`, `(12 episodes)`, season markers and
  Portuguese site wrapper words ("Todos os Episódios", "Assistir ... Online") are ignored.
- ani-cli: if it starts downloading a different anime, the download is **stopped within seconds** and the next search term
  is tried, instead of downloading the whole wrong episode first.
- ani-tupi: stricter candidate choice (no other season, no unrelated extra words).
- The same stricter matching is used when moving watched episodes to the trash and restoring them, so one anime's
  progress can no longer trash another anime's files.
- Added `tests/test_matching.py` (`python3 -m unittest discover -s tests -v`).

## 2.0.0
- **Unified installer** (`install.sh`): one script for both engines. Language choice picks the sources:
  English → ani-cli, Portuguese → ani-tupi.
- Install straight from GitHub with a single `curl ... | bash` line.
- Options during install: engine/language, dub or sub (with fallback), episodes in advance
  (finished / airing), check interval, retry cooldown, timeout, minimum free space, trash days,
  Wi-Fi only, battery guard, automatic engine updates. Quick mode asks only the essentials.
- Settings now live in `~/.config/anilist-autodl/config` (no more editing the Python file).
  `anilist-autodl config` changes them later.
- **Automatic ani-tupi updater** with a compatibility self-test and automatic rollback.
- New `anilist-autodl` command: `run`, `job`, `status`, `logs`, `update`, `retry`, `config`, `uninstall`.
- Notifications in English or Portuguese.
- Heads-up before `pkg upgrade`; answers are saved first so an interrupted install can simply be re-run.
- Scripts moved to `~/.anilist-autodl/`; state, logs and history files keep their old names, so nothing is lost.
  Old files are kept as `*.bak` / `*.old`.

## 1.x
- ani-cli only; settings at the top of `fetch_anime.py`.
