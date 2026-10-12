# Changelog

## 2.2.2
- **Fixed: an empty or lagging episode listing no longer blocks a download.** A catalog can report "0 episodes" (or not list the
  wanted one) while the stream exists. ani-cli-rs's `episodes` listing is no longer consulted at all: the download is always
  tried, and it answers fast and clearly when an episode is really missing (`ACL-3001`, `ACL-2004`...). One call less per attempt.
- `anilist-autodl trace` still shows the listing, now labelled advisory, and adds a direct stream probe (`ani-cli-rs links`).
- Added `tests/test_rs_flow.py`: runs the real flow against a fake `ani-cli-rs` that lists no episodes but can download.
- ani-tupi is unchanged on purpose: it needs the episode list to get the episode's URL.

## 2.2.1
- **Fixed: a catalog that names a combined stage entry by its first stage was rejected.** AniList's "2nd & 3rd STAGE"
  (stages 2 and 3) is "2nd Stage" in the second ani-cli-rs catalog. Season/stage numbers now match when they are equal, or when the
  catalog's numbers are a subset of the wanted range that starts at the same number. A plain title counts as stage 1
  (so the first stage's entry is still found, and "2nd Stage" is still never taken for it). Same rule for ani-tupi and GoAnime.
- **ani-cli-rs ids carry the AniList entry.** `anikoto:` ids are base64 JSON with `anilistId`, `malId`, `title` and `episodes`; when
  present, the AniList id is used as exact proof (same id = this entry, different id = never this entry), before any name matching.
- Clearer log for failed ani-cli-rs downloads: `ACL-3001 No playable sources found (the provider has no working stream for this
  episode (yet))` instead of the tail of the message. That code is the provider's, not a matching problem: the other catalog and
  then the backup engine are tried.
- `anilist-autodl trace` shows the verdict per result with the AniList-id check.

## 2.2.0
- **New optional engine: [GoAnime](https://github.com/alvarorichard/GoAnime)** (English `anidb`; Portuguese `animefire`,
  `goyabu`). Built with Termux's own Go (`GOTOOLCHAIN=local`). It cannot be searched without downloading, so it is **guarded**:
  the anime, season and episode are read from the path it writes (Jellyfin/Plex style folders are understood) and must match,
  a wrong anime is stopped as soon as its file appears, the sources offered by `goanime -h` decide what is used (AllAnime was
  removed in GoAnime 1.8.7), `--dub` is used only if this version has it, and the audio check applies. When a run produces
  nothing usable, the log shows GoAnime's last output and any video written outside the temporary folder.
- `GOANIME_SOURCES` setting. Updater: asks the Go proxy for the latest version, builds into a temporary folder and replaces
  the binary only after a self-test (the old one is kept).
- **`anilist-autodl try TEXT [EP]`**: runs the real pipeline (every engine in order) for an anime of your lists, delivers nothing
  and records nothing.
- A file GoAnime got right but without audio no longer triggers the remaining search texts (same stream).

## 2.1.2
- **Fixed: ani-cli-rs/ani-tupi searched "JoJos" instead of "JoJo's".** The symbol-free search text made for ani-cli (it does not
  URL-encode) was sent to every engine. ani-cli-rs and ani-tupi now get the original titles first, then the cleaned ones, then
  the parts of "Title: Subtitle"; ani-cli keeps the cleaned text.
- **Fixed: "1st STAGE" and "2nd - 3rd STAGE" looked identical.** Search results must now match in words **and** season/stage
  numbers (`STEEL BALL RUN JoJo's Bizarre Adventure 1st STAGE` can no longer be taken for the 2nd - 3rd STAGE entry, which
  would have downloaded the wrong show's episode). "Stage" counts as a split-cour marker like "Part".
- When nothing matches, the log lists what the catalog returned and why each result was rejected.
- New command `anilist-autodl trace TEXT`: shows, without downloading, the search texts, the catalog results, the verdict
  for each and whether the wanted episode is listed.

## 2.1.1
- **Fixed: the ani-cli-rs build gave up on `Text file busy (os error 26)`.** That is a race between parallel Rust build jobs
  on Android (a build script is executed while another job still has it open). The installer and the updater now retry the
  build with fewer parallel jobs (up to 4, then 2, then 1; finished crates are cached, so retries are cheap).
- When the build still fails, the installer remembers it: the next interactive run explains and offers ani-cli-rs again
  (restoring it as main or as backup, as it was). Unattended runs never retry on their own.

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
