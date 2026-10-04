#!/usr/bin/env bash
# Kept so old links and instructions keep working. The installer is now install.sh.
# Old usage still works:  bash install_anime_downloader.sh [anilist_username]
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
args=("$@")
if [ $# -ge 1 ] && [ "${1#-}" = "$1" ]; then args=(--username "$1" "${@:2}"); fi   # old positional username
if [ -n "$here" ] && [ -f "$here/install.sh" ]; then exec bash "$here/install.sh" "${args[@]}"; fi
exec bash -c 'curl -fsSL https://raw.githubusercontent.com/nmfassis/anilist-autodl/main/install.sh | bash -s -- "$@"' _ "${args[@]}"
