#!/data/data/com.termux/files/usr/bin/bash
# anilist-autodl engine updater.
#   update.sh            update only if the interval (UPDATE_EVERY_DAYS) has passed
#   update.sh --force    update now
#
# ani-tupi: pip upgrade -> compatibility self-test -> automatic rollback if the new version breaks the bridge.
# ani-cli:  `ani-cli -U` (it updates itself).
# yt-dlp (ani-tupi engine): refreshed at most once a day.
export PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PATH="$PREFIX/bin:$PATH"

DIR="$HOME/.anilist-autodl"
CONF="${AUTODL_CONFIG:-$HOME/.config/anilist-autodl/config}"
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

AUTODL_LANG="${AUTODL_LANG:-en}"
AUTODL_ENGINE="${AUTODL_ENGINE:-ani-cli}"
AUTO_UPDATE="${AUTO_UPDATE:-true}"
UPDATE_EVERY_DAYS="${UPDATE_EVERY_DAYS:-7}"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

STAMP="$DIR/.last_engine_update"
YT_STAMP="$DIR/.last_ytdlp_update"
FAILED="$DIR/.update_failed_version"

log() { printf '[%s] [update] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

notify() {  # notify EN_TITLE EN_TEXT PT_TITLE PT_TEXT
  local t="$1" c="$2"
  [ "$AUTODL_LANG" = "pt" ] && { t="$3"; c="$4"; }
  timeout 15 termux-notification --title "$t" --content "$c" --priority default --icon "${5:-info}" >/dev/null 2>&1 </dev/null || true
}

due() {  # due STAMP_FILE DAYS
  [ "$FORCE" = 1 ] && return 0
  [ -f "$1" ] || return 0
  [ -n "$(find "$1" -mmin "+$(( $2 * 1440 ))" 2>/dev/null)" ]
}

tupi_version() { pip show ani-tupi 2>/dev/null | sed -n 's/^Version: //p'; }

update_ytdlp() {
  due "$YT_STAMP" 1 || return 0
  if timeout 300 pip install -q -U yt-dlp --no-deps; then
    touch "$YT_STAMP"
  else
    log "yt-dlp update skipped/failed"
  fi
}

update_tupi() {
  local old new
  old="$(tupi_version)"
  if [ -z "$old" ]; then log "ani-tupi is not installed (re-run the installer)"; return 1; fi
  due "$STAMP" "$UPDATE_EVERY_DAYS" || return 0

  ANDROID_API_LEVEL="$(getprop ro.build.version.sdk 2>/dev/null)"; export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-24}"
  log "ani-tupi $old: checking for a newer version..."
  timeout 1800 pip install -q -U ani-tupi || log "pip could not finish the upgrade"
  new="$(tupi_version)"

  if [ "$new" = "$old" ] && python3 "$DIR/fetch_episode_tupi.py" --selftest >/dev/null 2>&1; then
    log "ani-tupi $old is up to date."
    touch "$STAMP"
    return 0
  fi

  if python3 "$DIR/fetch_episode_tupi.py" --selftest; then
    log "ani-tupi updated: $old -> $new"
    rm -f "$FAILED"; touch "$STAMP"
    notify "anilist-autodl" "ani-tupi updated to $new" "anilist-autodl" "ani-tupi atualizado para $new"
    return 0
  fi

  log "ani-tupi $new is not compatible with this bridge. Rolling back to $old..."
  if pip install -q "ani-tupi==$old" --no-deps && python3 "$DIR/fetch_episode_tupi.py" --selftest >/dev/null 2>&1; then
    log "Rolled back to ani-tupi $old."
    if [ "$(cat "$FAILED" 2>/dev/null)" != "$new" ]; then      # tell the user once per bad version
      echo "$new" > "$FAILED"
      notify "anilist-autodl" "ani-tupi $new is not compatible yet. Staying on $old." \
             "anilist-autodl" "O ani-tupi $new ainda não é compatível. Continuando na $old." "error"
    fi
    touch "$STAMP"
  else
    log "Rollback failed. Re-run the installer to repair ani-tupi."
    notify "anilist-autodl" "ani-tupi update failed and could not be rolled back. Re-run the installer." \
           "anilist-autodl" "A atualização do ani-tupi falhou e não foi revertida. Rode o instalador de novo." "error"
  fi
  return 1
}

update_ani_cli() {
  if command -v ani-cli >/dev/null 2>&1; then
    timeout 120 ani-cli -U || log "ani-cli update skipped/failed"
    termux-fix-shebang "$PREFIX/bin/ani-cli" 2>/dev/null || true
  fi
}

case "$AUTO_UPDATE:$FORCE" in
  false:0|no:0|0:0) log "automatic updates are off (AUTO_UPDATE=false)"; exit 0 ;;
esac

if [ "$AUTODL_ENGINE" = "ani-tupi" ]; then
  update_ytdlp
  update_tupi
else
  update_ani_cli
fi
