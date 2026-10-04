#!/data/data/com.termux/files/usr/bin/bash
# What the Android scheduler runs (and `anilist-autodl run`): wake lock, engine update, downloader, logs.
#   run.sh               quiet, output goes to ~/.anime_downloader_output.log
#   run.sh --foreground  also prints to the terminal
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:$PATH"
cd "$HOME" || exit 1

DIR="$HOME/.anilist-autodl"
OUT="$HOME/.anime_downloader_output.log"

# keep the output log small
if [ -f "$OUT" ] && [ "$(wc -c < "$OUT")" -gt 2000000 ]; then
  tail -n 2000 "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
fi

# keep the phone awake for the whole run, always release on exit
termux-wake-lock
trap 'termux-wake-unlock' EXIT

job() {
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') job start ==="
  bash "$DIR/update.sh"
  python3 "$DIR/fetch_anime.py"
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') job end ==="
}

if [ "${1:-}" = "--foreground" ]; then
  job 2>&1 | tee -a "$OUT"
else
  job >> "$OUT" 2>&1
fi
