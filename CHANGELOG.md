# Changelog

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
