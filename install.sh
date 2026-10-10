#!/usr/bin/env bash
# anilist-autodl installer for Termux (Android)
#
#   Install straight from GitHub (no download step):
#     curl -fsSL https://raw.githubusercontent.com/nmfassis/anilist-autodl/main/install.sh | bash
#
#   Or from a checkout:           bash install.sh
#   Change settings later:        anilist-autodl config
#   Remove it:                    anilist-autodl uninstall
#
# Options:  --lang en|pt   --engine ani-cli|ani-tupi   --username NAME   --mode quick|custom
#           --set KEY=VALUE (repeatable, e.g. --set AHEAD_FINISHED=5)   --yes   --reconfigure
#           --uninstall   --no-run   -h/--help
#
# Safe to re-run: answers are saved before anything heavy happens, so if Termux interrupts the
# package upgrade you can run the same command again and it continues with the same settings.
set -u

REPO="${AUTODL_REPO:-nmfassis/anilist-autodl}"
REF="${AUTODL_REF:-main}"
TARBALL_URL="${AUTODL_TARBALL_URL:-https://github.com/$REPO/archive/refs/heads/$REF.tar.gz}"

INSTALL_DIR="$HOME/.anilist-autodl"
CONF_DIR="$HOME/.config/anilist-autodl"
CONF="${AUTODL_CONFIG:-$CONF_DIR/config}"
JOB_ID=1

# ------------------------------------------------------------------ messages (en / pt)
_m_en() {
  case "$1" in
    boot) echo "Downloading anilist-autodl from GitHub...";;
    boot_fail) echo "Could not download the installer (check your connection). URL: %s";;
    need_termux) echo "This installer must be run inside Termux.";;
    no_tty) echo "No terminal available for questions: using flags/defaults (--yes mode).";;
    lang_pick) echo "Main download engine:";;
    eng_rs) echo "ani-cli-rs  (English; Rust port: embeds subtitles, picks the exact anime) - recommended";;
    eng_cli) echo "ani-cli  (English; the original, simple)";;
    eng_tupi) echo "ani-tupi  (Portuguese; Brazilian sources)";;
    eng_none) echo "None";;
    q_backup) echo "Backup engine (used when the main one cannot deliver a valid file):";;
    q_prefer_subs) echo "ani-cli-rs: when a subtitled file has no subtitle tracks, try its other catalog before accepting it?";;
    st_rs) echo "Building ani-cli-rs from source (Rust compile: 5-15 min, keep Termux open)";;
    rs_fail_swap) echo "ani-cli-rs could not be built. Using %s as the main engine instead (run the installer again to retry).";;
    rs_fail_drop) echo "ani-cli-rs could not be built. Continuing without a backup engine.";;
    rs_fail_die) echo "ani-cli-rs could not be built. Run the installer again or choose another engine.";;
    upgrade_notice) echo "New in this version: ani-cli-rs (English engine that embeds subtitles and picks the exact anime) with ani-cli as backup, and an automatic audio check on every download. The questions below start from the new defaults.";;
    found_prev) echo "Found previous settings: AniList user %s, engine %s.";;
    reuse_prev) echo "Reuse them?";;
    mode_pick) echo "Setup mode:";;
    mode_quick) echo "Quick - only the essentials (recommended)";;
    mode_custom) echo "Custom - every option";;
    q_user) echo "Your AniList username";;
    q_audio) echo "Preferred version:";;
    audio_sub) echo "Subtitled (sub)";;
    audio_dub) echo "Dubbed (dub)";;
    audio_note_tupi) echo "(ani-tupi relies on the source naming the title 'Dublado'/'Dub'.)";;
    q_audio_fb) echo "If your preferred version is not available, download the other one?";;
    q_dir) echo "Download folder";;
    q_ahead_fin) echo "Episodes to download in advance - finished anime";;
    q_ahead_air) echo "Episodes to download in advance - anime still airing";;
    q_planning) echo "Also get Ep 1 of 'Planning' anime once they start airing?";;
    q_interval) echo "Check for new episodes every (e.g. 30m, 1h, 6h; minimum 15m)";;
    q_retry) echo "Wait this many hours before retrying a failed episode";;
    q_timeout) echo "Give up on one download after this many minutes";;
    q_minfree) echo "Pause downloads when free storage is below (GB)";;
    q_trash) echo "Days watched episodes stay in the trash before deletion";;
    q_wifi) echo "Download only on Wi-Fi (unmetered networks)?";;
    q_battery) echo "Skip runs while the battery is low?";;
    q_autoup) echo "Keep the download engine up to date automatically?";;
    q_upevery) echo "Check for engine updates every (days)";;
    bad_value) echo "Invalid value, try again.";;
    bad_preset) echo "Invalid value for %s: %s";;
    need_user) echo "An AniList username is required (use --username NAME).";;
    summary) echo "Your settings";;
    s_user) echo "AniList user";;
    s_engine) echo "Engine";;
    s_ui) echo "Language";;
    s_audio) echo "Version";;
    s_dir) echo "Download folder";;
    s_ahead) echo "In advance";;
    s_every) echo "Check every";;
    s_retry) echo "Retry failed after";;
    s_net) echo "Network";;
    s_update) echo "Auto-update";;
    on) echo "on";; off) echo "off";;
    fin) echo "finished";; air) echo "airing";;
    wifi_only) echo "Wi-Fi only";; any_net) echo "any network";;
    confirm) echo "Continue with these settings?";;
    cancelled) echo "Cancelled. Nothing was changed.";;
    warn_upgrade) printf '%s\n' \
      "HEADS-UP: the next step runs 'pkg update && pkg upgrade'." \
      "  - It can take several minutes and may update Termux's own core tools." \
      "  - If it asks a question, just press Enter / answer Y." \
      "  - If the installer stops or Termux restarts during this step, run the SAME" \
      "    command again: your answers are saved and it continues from here.";;
    st_storage) echo "Checking storage access";;
    storage_fail) echo "Cannot write to /sdcard/Download. Allow storage access for Termux and run the installer again.";;
    st_pkg) echo "Updating Termux packages (see the heads-up above)";;
    pkg_upgrade_warn) echo "pkg upgrade did not finish cleanly. Continuing; if something fails below, run the installer again.";;
    st_pkg_install) echo "Installing packages (this can take a few minutes)";;
    pkg_fail) echo "Package installation failed. Run the installer again.";;
    py_old) echo "ani-tupi needs Python 3.12 or newer (found: %s).";;
    st_anicli) echo "Installing ani-cli";;
    anicli_fail) echo "Could not download ani-cli and none is installed.";;
    anicli_keep) echo "Download failed, keeping the installed ani-cli.";;
    st_tupi) echo "Installing ani-tupi (the first run compiles pydantic-core: 5-15 min, keep Termux open)";;
    tupi_dep_fail) echo "Could not install the Python package %s.";;
    tupi_fail) echo "Could not install ani-tupi.";;
    tupi_import) echo "ani-tupi installed but not compatible with this tool. Run: anilist-autodl update";;
    st_files) echo "Installing files";;
    migrated) echo "Previous installation found: old files kept as *.bak / *.old in your home folder.";;
    st_job) echo "Registering the automatic job (every %s min, %s, survives reboot)";;
    st_notify) echo "Sending a test notification";;
    notify_text) echo "Setup complete";;
    notify_fail) echo "No notification: install the Termux:API app (same source as Termux) and allow its notifications.";;
    done_title) echo "Installed!";;
    done_user) echo "AniList user";;
    done_engine) echo "Engine";;
    done_dir) echo "Downloads";;
    done_cmds) printf '%s\n' \
      "Useful commands:" \
      "  anilist-autodl run      download now (live output)" \
      "  anilist-autodl status   settings, scheduled job, last log lines" \
      "  anilist-autodl logs     follow the log" \
      "  anilist-autodl config   change any setting" \
      "  anilist-autodl update   update the engine now";;
    done_manual) printf '%s\n' \
      "One manual step: Android Settings > Apps > Termux and Termux:API >" \
      "Battery > Unrestricted / Don't optimize (otherwise Android may kill long downloads).";;
    run_now) echo "Run a download check now?";;
    reconf_done) echo "Settings saved and the schedule was updated.";;
    reconf_engine) echo "The engine changed: installing it now.";;
    no_conf) echo "No saved settings found. Run the installer first.";;
    un_need_yes) echo "Uninstall needs a terminal to confirm (or pass --yes).";;
    un_confirm) echo "Remove anilist-autodl (job, scripts, settings, logs)? Your downloaded episodes are kept.";;
    un_done) echo "Removed. Downloaded episodes were not touched.";;
    *) echo "$1";;
  esac
}
_m_pt() {
  case "$1" in
    boot) echo "Baixando o anilist-autodl do GitHub...";;
    boot_fail) echo "Não foi possível baixar o instalador (verifique a conexão). URL: %s";;
    need_termux) echo "Este instalador deve ser executado dentro do Termux.";;
    no_tty) echo "Sem terminal para perguntas: usando flags/padrões (modo --yes).";;
    lang_pick) echo "Motor de download principal:";;
    eng_rs) echo "ani-cli-rs  (inglês; port em Rust: embute legendas, escolhe o anime exato) - recomendado";;
    eng_cli) echo "ani-cli  (inglês; o original, simples)";;
    eng_tupi) echo "ani-tupi  (português; fontes brasileiras)";;
    eng_none) echo "Nenhum";;
    q_backup) echo "Motor de reserva (usado quando o principal não entrega um arquivo válido):";;
    q_prefer_subs) echo "ani-cli-rs: quando um arquivo legendado vier sem faixas de legenda, tentar o outro catálogo antes de aceitar?";;
    st_rs) echo "Compilando o ani-cli-rs a partir do código-fonte (Rust: 5-15 min, mantenha o Termux aberto)";;
    rs_fail_swap) echo "Não foi possível compilar o ani-cli-rs. Usando %s como motor principal (rode o instalador de novo para tentar outra vez).";;
    rs_fail_drop) echo "Não foi possível compilar o ani-cli-rs. Continuando sem motor de reserva.";;
    rs_fail_die) echo "Não foi possível compilar o ani-cli-rs. Rode o instalador de novo ou escolha outro motor.";;
    upgrade_notice) echo "Novidade desta versão: ani-cli-rs (motor em inglês que embute legendas e escolhe o anime exato) com o ani-cli de reserva, e uma checagem automática de áudio em todo download. As perguntas abaixo partem dos novos padrões.";;
    found_prev) echo "Configuração anterior encontrada: usuário AniList %s, motor %s.";;
    reuse_prev) echo "Reaproveitar?";;
    mode_pick) echo "Modo de configuração:";;
    mode_quick) echo "Rápido - só o essencial (recomendado)";;
    mode_custom) echo "Personalizado - todas as opções";;
    q_user) echo "Seu usuário do AniList";;
    q_audio) echo "Versão preferida:";;
    audio_sub) echo "Legendado (sub)";;
    audio_dub) echo "Dublado (dub)";;
    audio_note_tupi) echo "(o ani-tupi depende da fonte indicar 'Dublado'/'Dub' no título.)";;
    q_audio_fb) echo "Se a versão preferida não existir, baixar a outra?";;
    q_dir) echo "Pasta de downloads";;
    q_ahead_fin) echo "Episódios para baixar adiantado - animes finalizados";;
    q_ahead_air) echo "Episódios para baixar adiantado - animes em exibição";;
    q_planning) echo "Baixar o ep. 1 dos animes em 'Planning' quando começarem a ser exibidos?";;
    q_interval) echo "Verificar novos episódios a cada (ex.: 30m, 1h, 6h; mínimo 15m)";;
    q_retry) echo "Esperar quantas horas antes de tentar de novo um episódio que falhou";;
    q_timeout) echo "Desistir de um download após quantos minutos";;
    q_minfree) echo "Pausar downloads quando o espaço livre for menor que (GB)";;
    q_trash) echo "Dias que episódios assistidos ficam na lixeira antes de apagar";;
    q_wifi) echo "Baixar só no Wi-Fi (redes sem franquia)?";;
    q_battery) echo "Pular execuções com a bateria fraca?";;
    q_autoup) echo "Manter o motor de download atualizado automaticamente?";;
    q_upevery) echo "Verificar atualizações do motor a cada (dias)";;
    bad_value) echo "Valor inválido, tente de novo.";;
    bad_preset) echo "Valor inválido para %s: %s";;
    need_user) echo "É preciso informar o usuário do AniList (use --username NOME).";;
    summary) echo "Suas configurações";;
    s_user) echo "Usuário AniList";;
    s_engine) echo "Motor";;
    s_ui) echo "Idioma";;
    s_audio) echo "Versão";;
    s_dir) echo "Pasta de downloads";;
    s_ahead) echo "Adiantado";;
    s_every) echo "Verificar a cada";;
    s_retry) echo "Nova tentativa após";;
    s_net) echo "Rede";;
    s_update) echo "Atualização automática";;
    on) echo "ligada";; off) echo "desligada";;
    fin) echo "finalizados";; air) echo "em exibição";;
    wifi_only) echo "só Wi-Fi";; any_net) echo "qualquer rede";;
    confirm) echo "Continuar com essas configurações?";;
    cancelled) echo "Cancelado. Nada foi alterado.";;
    warn_upgrade) printf '%s\n' \
      "ATENÇÃO: o próximo passo roda 'pkg update && pkg upgrade'." \
      "  - Pode levar vários minutos e atualizar ferramentas centrais do próprio Termux." \
      "  - Se ele fizer uma pergunta, é só dar Enter / responder Y." \
      "  - Se o instalador parar ou o Termux reiniciar nessa etapa, rode o MESMO" \
      "    comando de novo: suas respostas estão salvas e ele continua daqui.";;
    st_storage) echo "Verificando acesso ao armazenamento";;
    storage_fail) echo "Não consigo gravar em /sdcard/Download. Permita o acesso ao armazenamento para o Termux e rode o instalador de novo.";;
    st_pkg) echo "Atualizando pacotes do Termux (veja o aviso acima)";;
    pkg_upgrade_warn) echo "O pkg upgrade não terminou direito. Continuando; se algo falhar abaixo, rode o instalador de novo.";;
    st_pkg_install) echo "Instalando pacotes (pode levar alguns minutos)";;
    pkg_fail) echo "Falha ao instalar os pacotes. Rode o instalador de novo.";;
    py_old) echo "O ani-tupi exige Python 3.12 ou mais novo (encontrado: %s).";;
    st_anicli) echo "Instalando o ani-cli";;
    anicli_fail) echo "Não foi possível baixar o ani-cli e não há nenhum instalado.";;
    anicli_keep) echo "Falha no download, mantendo o ani-cli instalado.";;
    st_tupi) echo "Instalando o ani-tupi (na primeira vez compila o pydantic-core: 5-15 min, mantenha o Termux aberto)";;
    tupi_dep_fail) echo "Não foi possível instalar o pacote Python %s.";;
    tupi_fail) echo "Não foi possível instalar o ani-tupi.";;
    tupi_import) echo "O ani-tupi foi instalado, mas não é compatível com esta ferramenta. Rode: anilist-autodl update";;
    st_files) echo "Instalando os arquivos";;
    migrated) echo "Instalação anterior encontrada: os arquivos antigos ficaram como *.bak / *.old na sua pasta pessoal.";;
    st_job) echo "Registrando o job automático (a cada %s min, %s, sobrevive a reinício)";;
    st_notify) echo "Enviando uma notificação de teste";;
    notify_text) echo "Instalação concluída";;
    notify_fail) echo "Sem notificação: instale o app Termux:API (da mesma fonte do Termux) e permita as notificações dele.";;
    done_title) echo "Instalado!";;
    done_user) echo "Usuário AniList";;
    done_engine) echo "Motor";;
    done_dir) echo "Downloads";;
    done_cmds) printf '%s\n' \
      "Comandos úteis:" \
      "  anilist-autodl run      baixar agora (saída ao vivo)" \
      "  anilist-autodl status   configurações, job agendado, últimas linhas do log" \
      "  anilist-autodl logs     acompanhar o log" \
      "  anilist-autodl config   mudar qualquer configuração" \
      "  anilist-autodl update   atualizar o motor agora";;
    done_manual) printf '%s\n' \
      "Um passo manual: Configurações do Android > Apps > Termux e Termux:API >" \
      "Bateria > Sem restrições / Não otimizar (senão o Android pode encerrar downloads longos).";;
    run_now) echo "Executar uma verificação de downloads agora?";;
    reconf_done) echo "Configurações salvas e agendamento atualizado.";;
    reconf_engine) echo "O motor mudou: instalando agora.";;
    no_conf) echo "Nenhuma configuração salva. Rode o instalador primeiro.";;
    un_need_yes) echo "Para desinstalar é preciso um terminal para confirmar (ou use --yes).";;
    un_confirm) echo "Remover o anilist-autodl (job, scripts, configurações, logs)? Seus episódios baixados são mantidos.";;
    un_done) echo "Removido. Os episódios baixados não foram tocados.";;
    *) echo "$1";;
  esac
}

UI=en
m() { local k="$1" f; shift; f="$("_m_$UI" "$k")"; # shellcheck disable=SC2059
  printf "$f" "$@"; }

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31mError:\033[0m %s\n' "$*" >&2; exit 1; }
out()  { printf '%s\n' "$*"; }   # stdout stays the terminal even under `curl | bash`; only stdin is the script

# ------------------------------------------------------------------ options / state
KEYS=(AUTODL_LANG AUTODL_ENGINE AUTODL_BACKUP_ENGINE PREFER_SUBS ANILIST_USERNAME AUDIO AUDIO_FALLBACK DOWNLOAD_DIR AHEAD_FINISHED AHEAD_AIRING
      DOWNLOAD_PLANNING INTERVAL_MINUTES RETRY_COOLDOWN_HOURS TIMEOUT_MINUTES MIN_FREE_GB TRASH_DAYS
      WIFI_ONLY BATTERY_NOT_LOW AUTO_UPDATE UPDATE_EVERY_DAYS)
declare -A PRESET=()
ACTION=install          # install | reconfigure | uninstall
MODE=""                 # quick | custom
ASSUME_YES=0
NO_RUN=0
INTERACTIVE=1

init_defaults() {
  AUTODL_LANG=""; AUTODL_ENGINE=""; AUTODL_BACKUP_ENGINE=""; PREFER_SUBS=true; ANILIST_USERNAME=""
  UPGRADE_NOTICE=0
  AUDIO=sub; AUDIO_FALLBACK=true
  DOWNLOAD_DIR=/sdcard/Download/Anime
  AHEAD_FINISHED=3; AHEAD_AIRING=1; DOWNLOAD_PLANNING=true
  INTERVAL_MINUTES=60; RETRY_COOLDOWN_HOURS=6; TIMEOUT_MINUTES=60
  MIN_FREE_GB=2; TRASH_DAYS=3
  WIFI_ONLY=true; BATTERY_NOT_LOW=true
  AUTO_UPDATE=true; UPDATE_EVERY_DAYS=7
}

usage() { sed -n '2,20p' "${BASH_SOURCE[0]:-$0}" 2>/dev/null | sed 's/^# \{0,1\}//'; }

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --lang)        PRESET[AUTODL_LANG]="${2:-}"; shift;;
      --engine)      PRESET[AUTODL_ENGINE]="${2:-}"; shift;;
      --username)    PRESET[ANILIST_USERNAME]="${2:-}"; shift;;
      --mode)        MODE="${2:-}"; case "$MODE" in quick|custom) ;; *) die "--mode must be quick or custom";; esac; shift;;
      --set)         case "${2:-}" in *=*) PRESET["${2%%=*}"]="${2#*=}";; *) die "--set needs KEY=VALUE";; esac; shift;;
      -y|--yes)      ASSUME_YES=1;;
      --reconfigure) ACTION=reconfigure;;
      --uninstall)   ACTION=uninstall;;
      --no-run)      NO_RUN=1;;
      -h|--help)     usage; exit 0;;
      *) die "Unknown option: $1 (see --help)";;
    esac
    shift
  done
}

is_preset() { [ -n "${PRESET[$1]+x}" ]; }

# ------------------------------------------------------------------ prompts (always via /dev/tty)
prompt_read() {  # prompt_read "text" -> REPLY
  REPLY=""
  printf '%s' "$1" > /dev/tty
  IFS= read -r REPLY < /dev/tty || REPLY=""
}

# validators
v_user()  { [[ "$1" =~ ^[A-Za-z0-9_-]+$ ]]; }
v_posint() { [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1 ]; }
v_num()   { [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]; }
v_dir()   { [[ "$1" == /* || "$1" == "~"* ]] && [[ "$1" != *"'"* ]]; }
v_interval() { local n; n="$(interval_to_min "$1")" && [ "$n" -ge 15 ]; }

interval_to_min() {  # 30m -> 30, 1h -> 60, 2 -> 120 (bare number = hours), 1.5h -> 90
  local v="${1,,}" n
  case "$v" in
    *m) n="${v%m}"; [[ "$n" =~ ^[0-9]+$ ]] && echo "$n" && return 0;;
    *h) n="${v%h}";;
    *)  n="$v";;
  esac
  [[ "$n" =~ ^[0-9]+([.][0-9]+)?$ ]] || return 1
  awk -v h="$n" 'BEGIN{printf "%d", h*60 + 0.5}'
}
min_to_display() { local n="$1"; if [ $((n % 60)) -eq 0 ]; then echo "$((n / 60))h"; else echo "${n}m"; fi; }

norm_yn() {  # -> true|false  (accepts y/yes/s/sim/true/1 and n/no/nao/não/false/0)
  case "${1,,}" in
    y|yes|s|sim|true|1|on)  echo true;;
    n|no|nao|não|false|0|off) echo false;;
    *) return 1;;
  esac
}

ask() {  # ask VAR "prompt" default [validator]
  local var="$1" label="$2" def="$3" validator="${4:-}" ans
  if is_preset "$var"; then
    ans="${PRESET[$var]}"
    if [ -n "$validator" ] && ! "$validator" "$ans"; then die "$(m bad_preset "$var" "$ans")"; fi
    printf -v "$var" '%s' "$ans"; return 0
  fi
  if [ "$INTERACTIVE" = 0 ]; then printf -v "$var" '%s' "$def"; return 0; fi
  while :; do
    prompt_read "$label [$def]: "; ans="${REPLY:-$def}"
    if [ -z "$validator" ] || "$validator" "$ans"; then printf -v "$var" '%s' "$ans"; return 0; fi
    warn "$(m bad_value)"
  done
}

ask_yn() {  # ask_yn VAR "prompt" default(true|false)
  local var="$1" label="$2" def="$3" ans hint="[Y/n]"
  [ "$UI" = pt ] && hint="[S/n]"
  [ "$def" = false ] && { hint="[y/N]"; [ "$UI" = pt ] && hint="[s/N]"; }
  if is_preset "$var"; then
    ans="$(norm_yn "${PRESET[$var]}")" || die "$(m bad_preset "$var" "${PRESET[$var]}")"
    printf -v "$var" '%s' "$ans"; return 0
  fi
  if [ "$INTERACTIVE" = 0 ]; then printf -v "$var" '%s' "$def"; return 0; fi
  while :; do
    prompt_read "$label $hint: "
    if [ -z "$REPLY" ]; then printf -v "$var" '%s' "$def"; return 0; fi
    if ans="$(norm_yn "$REPLY")"; then printf -v "$var" '%s' "$ans"; return 0; fi
    warn "$(m bad_value)"
  done
}

ask_choice() {  # ask_choice VAR "heading" default_value  value1 "label1" value2 "label2" ...
  local var="$1" heading="$2" def="$3"; shift 3
  local -a vals=() labs=(); local i defidx=1 ans
  while [ $# -ge 2 ]; do vals+=("$1"); labs+=("$2"); shift 2; done
  for i in "${!vals[@]}"; do [ "${vals[$i]}" = "$def" ] && defidx=$((i + 1)); done
  if is_preset "$var"; then
    for i in "${!vals[@]}"; do [ "${vals[$i]}" = "${PRESET[$var]}" ] && { printf -v "$var" '%s' "${vals[$i]}"; return 0; }; done
    die "$(m bad_preset "$var" "${PRESET[$var]}")"
  fi
  if [ "$INTERACTIVE" = 0 ]; then printf -v "$var" '%s' "$def"; return 0; fi
  out ""; out "$heading"
  for i in "${!vals[@]}"; do out "  $((i + 1))) ${labs[$i]}"; done
  while :; do
    prompt_read "> [$defidx]: "; ans="${REPLY:-$defidx}"
    if [[ "$ans" =~ ^[0-9]+$ ]] && [ "$ans" -ge 1 ] && [ "$ans" -le "${#vals[@]}" ]; then
      printf -v "$var" '%s' "${vals[$((ans - 1))]}"; return 0
    fi
    warn "$(m bad_value)"
  done
}

# ------------------------------------------------------------------ source location / bootstrap
find_sources() {  # sets SRCF to the directory that holds fetch_anime.py (repo layout or installed layout)
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || here=""
  SRC_ROOT="$here"; SRCF=""
  if   [ -n "$here" ] && [ -f "$here/src/fetch_anime.py" ]; then SRCF="$here/src"
  elif [ -n "$here" ] && [ -f "$here/fetch_anime.py" ];     then SRCF="$here"
  fi
}

bootstrap() {
  local tmp
  say "$(_m_en boot) / $(_m_pt boot)"
  tmp="$(mktemp -d)" || die "mktemp failed"
  if ! curl -fsSL "$TARBALL_URL" | tar xz --strip-components=1 -C "$tmp" 2>/dev/null || [ ! -f "$tmp/install.sh" ]; then
    rm -rf "$tmp"
    # shellcheck disable=SC2059
    die "$(printf "$(_m_en boot_fail)" "$TARBALL_URL") / $(printf "$(_m_pt boot_fail)" "$TARBALL_URL")"
  fi
  export AUTODL_BOOTSTRAPPED=1 AUTODL_CLEAN_SRC="$tmp"
  # Re-run from a real file so questions can be read from the terminal.
  if ( : < /dev/tty ) 2>/dev/null; then exec bash "$tmp/install.sh" "$@" < /dev/tty; fi
  exec bash "$tmp/install.sh" "$@"
}

# ------------------------------------------------------------------ steps
load_previous() {
  OLD_ENGINE=""; OLD_BACKUP=""; HAD_CONFIG=0
  if [ -f "$CONF" ]; then
    # shellcheck disable=SC1090
    . "$CONF"; HAD_CONFIG=1; OLD_ENGINE="$AUTODL_ENGINE"; OLD_BACKUP="$AUTODL_BACKUP_ENGINE"
    # A config written by an older version (no backup key) that used ani-cli: when asked interactively, start from the
    # new defaults (ani-cli-rs + ani-cli backup). Unattended runs never switch engines on their own.
    if ! grep -q '^AUTODL_BACKUP_ENGINE=' "$CONF" && [ "$AUTODL_ENGINE" = ani-cli ] && [ "$INTERACTIVE" = 1 ]; then
      AUTODL_ENGINE=ani-cli-rs; AUTODL_BACKUP_ENGINE=ani-cli; UPGRADE_NOTICE=1
    fi
  elif [ -f "$HOME/fetch_anime.py" ]; then            # pre-1.0 layout: reuse what it knew
    local u
    u="$(sed -n "s/^ANILIST_USERNAME = '\\(.*\\)'.*/\\1/p" "$HOME/fetch_anime.py" | head -n1)"
    [ "$u" = "YOUR_ANILIST_USERNAME" ] || ANILIST_USERNAME="$u"
    if [ -f "$HOME/fetch_episode_tupi.py" ]; then AUTODL_ENGINE=ani-tupi; fi
    local old_dir
    old_dir="$(sed -n "s/^DOWNLOAD_DIR = '\\(.*\\)'.*/\\1/p" "$HOME/fetch_anime.py" | head -n1)"
    [ -n "$old_dir" ] && DOWNLOAD_DIR="$old_dir"
  fi
  [ -n "$AUTODL_LANG" ] || { case "${LANG:-}" in pt*) AUTODL_LANG=pt;; *) AUTODL_LANG=en;; esac; }
}

choose_ui_language() {
  if is_preset AUTODL_LANG; then
    ask_choice AUTODL_LANG "" "$AUTODL_LANG" en "English" pt "Português (Brasil)"     # validates the preset only
  elif [ "$INTERACTIVE" = 1 ] && [ "$HAD_CONFIG" = 0 ] && [ "$ACTION" = install ]; then
    ask_choice AUTODL_LANG "Language / Idioma:" "$AUTODL_LANG" \
      en "English  (English sources: ani-cli-rs, with ani-cli as backup)" pt "Português  (fontes brasileiras: ani-tupi)"
  fi
  case "$AUTODL_LANG" in en|pt) ;; *) AUTODL_LANG=en;; esac
  UI="$AUTODL_LANG"
}

default_backup_for() { [ "$1" = ani-cli-rs ] && echo ani-cli || echo ""; }

chain_has() { [ "$AUTODL_ENGINE" = "$1" ] || [ "${AUTODL_BACKUP_ENGINE:-}" = "$1" ]; }

questions() {
  if [ -z "$MODE" ]; then
    if [ "$ACTION" = reconfigure ]; then MODE=custom
    else ask_choice MODE "$(m mode_pick)" quick quick "$(m mode_quick)" custom "$(m mode_custom)"; fi
  fi

  # Engines. Quick mode derives them from the language; custom mode (or --engine / --set) lets you choose.
  local def_engine="$AUTODL_ENGINE" def_backup="$AUTODL_BACKUP_ENGINE"
  if [ -z "$def_engine" ]; then
    if [ "$UI" = pt ]; then def_engine=ani-tupi; def_backup=""; else def_engine=ani-cli-rs; def_backup=ani-cli; fi
  fi
  if [ "$MODE" = custom ] || is_preset AUTODL_ENGINE; then
    ask_choice AUTODL_ENGINE "$(m lang_pick)" "$def_engine" \
      ani-cli-rs "$(m eng_rs)" ani-cli "$(m eng_cli)" ani-tupi "$(m eng_tupi)"
    [ "$AUTODL_ENGINE" = "$def_engine" ] || def_backup="$(default_backup_for "$AUTODL_ENGINE")"
  else
    AUTODL_ENGINE="$def_engine"
  fi
  if [ "$MODE" = custom ] || is_preset AUTODL_BACKUP_ENGINE; then
    local -a opts=(none "$(m eng_none)") e
    for e in ani-cli-rs ani-cli ani-tupi; do
      [ "$e" = "$AUTODL_ENGINE" ] && continue
      case "$e" in ani-cli-rs) opts+=("$e" "$(m eng_rs)");; ani-cli) opts+=("$e" "$(m eng_cli)");; *) opts+=("$e" "$(m eng_tupi)");; esac
    done
    ask_choice AUTODL_BACKUP_ENGINE "$(m q_backup)" "${def_backup:-none}" "${opts[@]}"
    [ "$AUTODL_BACKUP_ENGINE" = none ] && AUTODL_BACKUP_ENGINE=""
  else
    AUTODL_BACKUP_ENGINE="$def_backup"
  fi

  ask ANILIST_USERNAME "$(m q_user)" "${ANILIST_USERNAME:-}" v_user
  [ -n "$ANILIST_USERNAME" ] || die "$(m need_user)"

  local head; head="$(m q_audio)"
  chain_has ani-tupi && head="$head $(m audio_note_tupi)"
  ask_choice AUDIO "$head" "$AUDIO" sub "$(m audio_sub)" dub "$(m audio_dub)"

  [ "$MODE" = custom ] || return 0

  ask_yn AUDIO_FALLBACK "$(m q_audio_fb)" "$AUDIO_FALLBACK"
  chain_has ani-cli-rs && ask_yn PREFER_SUBS "$(m q_prefer_subs)" "$PREFER_SUBS"
  ask    DOWNLOAD_DIR "$(m q_dir)" "$DOWNLOAD_DIR" v_dir
  ask    AHEAD_FINISHED "$(m q_ahead_fin)" "$AHEAD_FINISHED" v_posint
  ask    AHEAD_AIRING "$(m q_ahead_air)" "$AHEAD_AIRING" v_posint
  ask_yn DOWNLOAD_PLANNING "$(m q_planning)" "$DOWNLOAD_PLANNING"
  if ! is_preset INTERVAL_MINUTES; then            # a preset is converted/validated in apply_presets_quiet
    local iv; iv="$(min_to_display "$INTERVAL_MINUTES")"
    ask iv "$(m q_interval)" "$iv" v_interval
    INTERVAL_MINUTES="$(interval_to_min "$iv")"
  fi
  ask    RETRY_COOLDOWN_HOURS "$(m q_retry)" "$RETRY_COOLDOWN_HOURS" v_num
  ask    TIMEOUT_MINUTES "$(m q_timeout)" "$TIMEOUT_MINUTES" v_posint
  ask    MIN_FREE_GB "$(m q_minfree)" "$MIN_FREE_GB" v_num
  ask    TRASH_DAYS "$(m q_trash)" "$TRASH_DAYS" v_num
  ask_yn WIFI_ONLY "$(m q_wifi)" "$WIFI_ONLY"
  ask_yn BATTERY_NOT_LOW "$(m q_battery)" "$BATTERY_NOT_LOW"
  ask_yn AUTO_UPDATE "$(m q_autoup)" "$AUTO_UPDATE"
  [ "$AUTO_UPDATE" = true ] && ask UPDATE_EVERY_DAYS "$(m q_upevery)" "$UPDATE_EVERY_DAYS" v_posint
}

apply_presets_quiet() {  # keys that were set with --set but not asked in quick mode
  local k yn
  for k in "${KEYS[@]}"; do
    if is_preset "$k"; then
      case "$k" in
        AUDIO_FALLBACK|PREFER_SUBS|DOWNLOAD_PLANNING|WIFI_ONLY|BATTERY_NOT_LOW|AUTO_UPDATE)
          yn="$(norm_yn "${PRESET[$k]}")" || die "$(m bad_preset "$k" "${PRESET[$k]}")"
          printf -v "$k" '%s' "$yn";;
        INTERVAL_MINUTES)
          v_interval "${PRESET[$k]}" || die "$(m bad_preset "$k" "${PRESET[$k]}")"
          INTERVAL_MINUTES="$(interval_to_min "${PRESET[$k]}")";;
        *) printf -v "$k" '%s' "${PRESET[$k]}";;
      esac
    fi
  done
  [ "$AUTODL_BACKUP_ENGINE" = none ] && AUTODL_BACKUP_ENGINE=""
  DOWNLOAD_DIR="${DOWNLOAD_DIR/#\~/$HOME}"
}

validate_all() {
  local k
  v_user "$ANILIST_USERNAME" || die "$(m bad_preset ANILIST_USERNAME "$ANILIST_USERNAME")"
  case "$AUTODL_ENGINE" in ani-cli|ani-cli-rs|ani-tupi) ;; *) die "$(m bad_preset AUTODL_ENGINE "$AUTODL_ENGINE")";; esac
  case "$AUTODL_BACKUP_ENGINE" in ""|ani-cli|ani-cli-rs|ani-tupi) ;; *) die "$(m bad_preset AUTODL_BACKUP_ENGINE "$AUTODL_BACKUP_ENGINE")";; esac
  [ "$AUTODL_BACKUP_ENGINE" != "$AUTODL_ENGINE" ] || die "$(m bad_preset AUTODL_BACKUP_ENGINE "$AUTODL_BACKUP_ENGINE")"
  case "$AUDIO" in sub|dub) ;; *) die "$(m bad_preset AUDIO "$AUDIO")";; esac
  v_dir "$DOWNLOAD_DIR" || die "$(m bad_preset DOWNLOAD_DIR "$DOWNLOAD_DIR")"
  for k in AHEAD_FINISHED AHEAD_AIRING TIMEOUT_MINUTES UPDATE_EVERY_DAYS; do
    v_posint "${!k}" || die "$(m bad_preset "$k" "${!k}")"
  done
  for k in RETRY_COOLDOWN_HOURS MIN_FREE_GB TRASH_DAYS; do
    v_num "${!k}" || die "$(m bad_preset "$k" "${!k}")"
  done
  { [[ "$INTERVAL_MINUTES" =~ ^[0-9]+$ ]] && [ "$INTERVAL_MINUTES" -ge 15 ]; } || die "$(m bad_preset INTERVAL_MINUTES "$INTERVAL_MINUTES")"
}

show_summary() {
  local net upd
  [ "$WIFI_ONLY" = true ] && net="$(m wifi_only)" || net="$(m any_net)"
  [ "$AUTO_UPDATE" = true ] && upd="$(m on) / $UPDATE_EVERY_DAYS d" || upd="$(m off)"
  out ""; out "== $(m summary) =="
  out "  $(m s_user): $ANILIST_USERNAME"
  out "  $(m s_engine): $AUTODL_ENGINE$([ -n "$AUTODL_BACKUP_ENGINE" ] && echo " + $AUTODL_BACKUP_ENGINE")   ($(m s_ui): $AUTODL_LANG)"
  out "  $(m s_audio): $AUDIO$([ "$AUDIO_FALLBACK" = true ] && echo " (+ fallback)")"
  out "  $(m s_dir): $DOWNLOAD_DIR"
  out "  $(m s_ahead): $AHEAD_FINISHED ($(m fin)) / $AHEAD_AIRING ($(m air))"
  out "  $(m s_every): $(min_to_display "$INTERVAL_MINUTES")   $(m s_retry): ${RETRY_COOLDOWN_HOURS}h"
  out "  $(m s_net): $net"
  out "  $(m s_update): $upd"
}

write_config() {
  mkdir -p "$(dirname "$CONF")"
  {
    echo "# anilist-autodl settings - change them with: anilist-autodl config"
    local k
    for k in "${KEYS[@]}"; do printf "%s='%s'\n" "$k" "${!k}"; done
  } > "$CONF.tmp" && mv "$CONF.tmp" "$CONF"
}

step_storage() {
  say "$(m st_storage)"
  if [ ! -d "$HOME/storage/shared" ]; then
    termux-setup-storage
    local _; for _ in $(seq 1 30); do [ -d "$HOME/storage/shared" ] && break; sleep 1; done
  fi
  [ -w /sdcard/Download ] || die "$(m storage_fail)"
  mkdir -p "$DOWNLOAD_DIR" 2>/dev/null || true
}

step_pkg_update() {
  out ""; out "$(m warn_upgrade)"; out ""
  say "$(m st_pkg)"
  export DEBIAN_FRONTEND=noninteractive
  pkg update -y && pkg upgrade -y -o Dpkg::Options::="--force-confold" || warn "$(m pkg_upgrade_warn)"
}

step_pkg_install() {
  say "$(m st_pkg_install)"
  local pk="python git curl ffmpeg termux-api"
  chain_has ani-cli && pk="$pk aria2 fzf"
  chain_has ani-cli-rs && pk="$pk rust termux-tools aria2"
  chain_has ani-tupi && pk="$pk rust clang make binutils libjpeg-turbo libpng freetype python-pillow"
  # yt-dlp comes from pip when ani-tupi is used (it imports it), otherwise from Termux
  chain_has ani-tupi || pk="$pk yt-dlp"
  # shellcheck disable=SC2086
  pkg install -y $pk || die "$(m pkg_fail)"
}

step_ani_cli_rs() {
  say "$(m st_rs)"
  local src="$INSTALL_DIR/ani-cli-rs-src" jobs
  jobs="$(nproc 2>/dev/null || echo 2)"; [ "$jobs" -gt 4 ] && jobs=4     # more jobs can exhaust a phone's RAM
  mkdir -p "$INSTALL_DIR"
  if [ -d "$src/.git" ]; then
    git -C "$src" fetch --depth 1 origin && git -C "$src" reset --hard FETCH_HEAD || return 1
  else
    rm -rf "$src"; git clone --depth 1 https://github.com/vorlie/ani-cli-rs.git "$src" || return 1
  fi
  ( cd "$src" && CARGO_BUILD_JOBS="$jobs" cargo build --release --locked ) || return 1
  install -Dm755 "$src/target/release/ani-cli-rs" "$PREFIX/bin/ani-cli-rs" || return 1
  "$PREFIX/bin/ani-cli-rs" --version >/dev/null 2>&1
}

step_ani_cli() {
  say "$(m st_anicli)"
  local tmpd; tmpd="$(mktemp -d)"
  if git clone --depth 1 https://github.com/pystardust/ani-cli.git "$tmpd/ani-cli"; then
    cp "$tmpd/ani-cli/ani-cli" "$PREFIX/bin/ani-cli"
    chmod +x "$PREFIX/bin/ani-cli"
    termux-fix-shebang "$PREFIX/bin/ani-cli" 2>/dev/null || true
  elif [ ! -x "$PREFIX/bin/ani-cli" ]; then
    rm -rf "$tmpd"; die "$(m anicli_fail)"
  else
    warn "$(m anicli_keep)"
  fi
  rm -rf "$tmpd"
}

step_ani_tupi() {
  python3 - <<'PY' || die "$(m py_old "$(python3 --version 2>&1)")"
import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)
PY
  say "$(m st_tupi)"
  ANDROID_API_LEVEL="$(getprop ro.build.version.sdk 2>/dev/null)"; export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-24}"
  local p
  for p in tqdm rich inquirerpy loguru httpx yt-dlp selenium thefuzz beautifulsoup4 diskcache pydantic pydantic-settings; do
    pip install "$p" || pip install --ignore-installed "$p" || die "$(m tupi_dep_fail "$p")"
  done
  pip install -U ani-tupi || pip install -U ani-tupi --no-deps || die "$(m tupi_fail)"
}

step_files() {
  say "$(m st_files)"
  mkdir -p "$INSTALL_DIR"
  local migrated=0 f
  for f in fetch_anime.py:.bak run_downloader.sh:.old fetch_episode_tupi.py:.bak; do
    if [ -f "$HOME/${f%%:*}" ]; then mv -f "$HOME/${f%%:*}" "$HOME/${f%%:*}${f##*:}"; migrated=1; fi
  done
  [ "$migrated" = 1 ] && ok "$(m migrated)"
  if [ "$SRCF" != "$INSTALL_DIR" ]; then
    for f in fetch_anime.py fetch_episode_tupi.py run.sh update.sh anilist-autodl; do
      cp -f "$SRCF/$f" "$INSTALL_DIR/$f" || die "missing $SRCF/$f"
    done
    [ -f "$SRC_ROOT/install.sh" ] && [ "$SRC_ROOT" != "$INSTALL_DIR" ] && cp -f "$SRC_ROOT/install.sh" "$INSTALL_DIR/install.sh"
  fi
  chmod +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR/anilist-autodl"
  python3 -m py_compile "$INSTALL_DIR/fetch_anime.py" "$INSTALL_DIR/fetch_episode_tupi.py" || die "python syntax error"
  rm -rf "$INSTALL_DIR/__pycache__"
  ln -sf "$INSTALL_DIR/anilist-autodl" "$PREFIX/bin/anilist-autodl"

  # old yt-dlp workarounds that cause problems with ani-cli
  if [ -f "$HOME/.config/yt-dlp/config" ]; then
    cp "$HOME/.config/yt-dlp/config" "$HOME/.config/yt-dlp/config.bak"
    sed -i '/--force-overwrite/d;/--no-m3u8-fixup/d;/postprocessor-args/d' "$HOME/.config/yt-dlp/config"
  fi
}

step_job() {
  local net=unmetered
  [ "$WIFI_ONLY" = false ] && net=any
  say "$(m st_job "$INTERVAL_MINUTES" "$([ "$WIFI_ONLY" = true ] && m wifi_only || m any_net)")"
  termux-job-scheduler --job-id "$JOB_ID" --script "$INSTALL_DIR/run.sh" \
    --period-ms $(( INTERVAL_MINUTES * 60000 )) --network "$net" \
    --battery-not-low "$BATTERY_NOT_LOW" --persisted true
  termux-job-scheduler --pending
}

step_notify() {
  say "$(m st_notify)"
  timeout 15 termux-notification --title "Anime Downloader" --content "$(m notify_text)" --priority high \
    < /dev/null || warn "$(m notify_fail)"
}

cleanup_src() { [ -n "${AUTODL_CLEAN_SRC:-}" ] && rm -rf "$AUTODL_CLEAN_SRC"; }

do_install() {
  command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
  trap 'command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock; cleanup_src' EXIT
  step_storage
  step_pkg_update
  step_pkg_install
  chain_has ani-cli && step_ani_cli
  chain_has ani-tupi && step_ani_tupi
  if chain_has ani-cli-rs && ! step_ani_cli_rs; then          # the long Rust build is the likeliest step to fail
    if [ "$AUTODL_BACKUP_ENGINE" = ani-cli-rs ]; then
      warn "$(m rs_fail_drop)"; AUTODL_BACKUP_ENGINE=""; write_config
    elif [ -n "$AUTODL_BACKUP_ENGINE" ]; then
      warn "$(m rs_fail_swap "$AUTODL_BACKUP_ENGINE")"; AUTODL_ENGINE="$AUTODL_BACKUP_ENGINE"; AUTODL_BACKUP_ENGINE=""; write_config
    else
      die "$(m rs_fail_die)"
    fi
  fi
  step_files
  if chain_has ani-tupi; then
    python3 "$INSTALL_DIR/fetch_episode_tupi.py" --selftest || die "$(m tupi_import)"
  fi
  step_job
  step_notify

  out ""
  out "=========================================================="
  out " $(m done_title)"
  out " $(m done_user): $ANILIST_USERNAME   $(m done_engine): $AUTODL_ENGINE$([ -n "$AUTODL_BACKUP_ENGINE" ] && echo " + $AUTODL_BACKUP_ENGINE")"
  out " $(m done_dir): $DOWNLOAD_DIR"
  out ""
  out "$(m done_cmds)"
  out ""
  out "$(m done_manual)"
  out "=========================================================="

  if [ "$NO_RUN" = 0 ] && [ "$INTERACTIVE" = 1 ]; then
    local go; ask_yn go "$(m run_now)" false
    if [ "$go" = true ]; then bash "$INSTALL_DIR/run.sh" --foreground; fi
  fi
  return 0
}

do_reconfigure() {
  [ -f "$CONF" ] || die "$(m no_conf)"
  questions; apply_presets_quiet; validate_all
  show_summary
  write_config
  if [ "$AUTODL_ENGINE" != "$OLD_ENGINE" ] || [ "$AUTODL_BACKUP_ENGINE" != "$OLD_BACKUP" ]; then
    ok "$(m reconf_engine)"; find_sources
    [ -n "$SRCF" ] || die "sources not found next to the installer"
    do_install
  else
    step_job
    ok "$(m reconf_done)"
  fi
}

do_uninstall() {
  local go=true
  if [ "$ASSUME_YES" = 0 ]; then
    [ "$INTERACTIVE" = 1 ] || die "$(m un_need_yes)"
    ask_yn go "$(m un_confirm)" false
  fi
  [ "$go" = true ] || { out "$(m cancelled)"; return 0; }
  termux-job-scheduler --cancel --job-id "$JOB_ID" >/dev/null 2>&1
  termux-job-scheduler --cancel --job-id 2 >/dev/null 2>&1
  if termux-job-scheduler --pending 2>/dev/null | grep -q "anilist-autodl"; then
    termux-job-scheduler --cancel-all >/dev/null 2>&1
  fi
  rm -f "$PREFIX/bin/anilist-autodl"
  [ -d "$INSTALL_DIR/ani-cli-rs-src" ] && rm -f "$PREFIX/bin/ani-cli-rs"      # only when this installer built it
  rm -rf "$INSTALL_DIR" "$CONF_DIR" "$HOME/.anime_tmp"
  rm -rf "$HOME/.anime_hold"
  rm -f "$HOME"/.anime_downloader* "$HOME/.anime_download_history.json"
  ok "$(m un_done)"
}

# ------------------------------------------------------------------ main
main() {
  trap cleanup_src EXIT
  parse_args "$@"
  [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ] || die "$(_m_en need_termux) / $(_m_pt need_termux)"

  [ "$ASSUME_YES" = 1 ] && INTERACTIVE=0
  if [ "$INTERACTIVE" = 1 ] && ! ( : < /dev/tty ) 2>/dev/null; then INTERACTIVE=0; warn "$(_m_en no_tty)"; fi

  find_sources
  if [ "$ACTION" = install ] && [ -z "$SRCF" ] && [ -z "${AUTODL_BOOTSTRAPPED:-}" ]; then bootstrap "$@"; fi

  init_defaults
  load_previous
  choose_ui_language

  case "$ACTION" in
    uninstall)   do_uninstall; exit 0;;
    reconfigure) do_reconfigure; exit 0;;
  esac

  [ -n "$SRCF" ] || die "installer files not found"

  local reuse=false
  if [ "$UPGRADE_NOTICE" = 1 ]; then
    out ""; out "$(m upgrade_notice)"
  elif [ "$HAD_CONFIG" = 1 ] && [ -n "$ANILIST_USERNAME" ] && [ -z "$MODE" ]; then
    out "$(m found_prev "$ANILIST_USERNAME" "$AUTODL_ENGINE")"
    ask_yn reuse "$(m reuse_prev)" true
    [ "$INTERACTIVE" = 0 ] && reuse=true
  fi
  if [ "$reuse" = true ]; then apply_presets_quiet; else questions; apply_presets_quiet; fi
  [ -n "$ANILIST_USERNAME" ] || die "$(m need_user)"
  validate_all

  show_summary
  if [ "$INTERACTIVE" = 1 ] && [ "$reuse" != true ]; then
    local go; ask_yn go "$(m confirm)" true
    [ "$go" = true ] || { out "$(m cancelled)"; exit 0; }
  fi
  write_config      # saved BEFORE the long steps: a re-run picks the same answers up
  do_install
  exit 0
}

main "$@"
