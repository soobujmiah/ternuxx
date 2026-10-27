# Curated Native optional software: id|display label|packages|official repository.
# Missing candidates fail the existing exact-plan resolver; no alternate repo is added.
_NT_NATIVE_APP_CATALOG=(
  'browser|Internet: Firefox browser|firefox|termux-x11'
  'music|Media: Audacious music player|audacious audacious-plugins|termux-x11'
  'images|Graphics: Ristretto image viewer|ristretto|termux-x11'
  'pdf|Office: Evince PDF viewer|evince|termux-x11'
  'editor|Editors: Mousepad|mousepad|termux-x11'
  'archive|Files: Xarchiver|xarchiver|termux-x11'
  'video|Media: VLC player (GUI)|vlc-qt|termux-x11'
  'gimp|Graphics: GIMP image editor|gimp|termux-x11'
  'inkscape|Graphics: Inkscape vector editor|inkscape|termux-x11'
  'krita|Graphics: Krita painting|krita|termux-x11'
  'blender|Graphics: Blender 4.5 (TUR community repository)|blender4|tur-packages'
  'darktable|Graphics: Darktable photo workflow|darktable|termux-x11'
  'rawtherapee|Graphics: RawTherapee RAW photos|rawtherapee|termux-x11'
  'imagemagick|Graphics: ImageMagick CLI tools|imagemagick|termux-main'
  'openscad|CAD: OpenSCAD (Blender available in PRoot)|openscad|termux-main'
  'audacity|Media: Audacity audio editor|audacity|termux-x11'
  'kdenlive|Media: Kdenlive video editor|kdenlive|termux-x11'
  'handbrake|Media: HandBrake video transcoder|handbrake|termux-x11'
  'ffmpeg|Media: FFmpeg CLI conversion|ffmpeg|termux-main'
  'mpv|Media: mpv video player|mpv|termux-main'
  'flameshot|Graphics: Flameshot screenshot tool|flameshot|termux-x11'
  'abiword|Office: AbiWord word processor|abiword|termux-x11'
  'gnumeric|Office: Gnumeric spreadsheets|gnumeric|termux-x11'
  'qalculate|Office: Qalculate calculator|qalculate-gtk|termux-x11'
  'texstudio|Office: TeXstudio LaTeX editor|texstudio|termux-x11'
  'geany|Development: Geany IDE|geany|termux-x11'
  'kate|Development: Kate editor|kate|termux-x11'
  'meld|Development: Meld visual diff|meld|termux-x11'
  'qgit|Development: QGit history viewer|qgit|termux-x11'
  'neovim|Development: Neovim terminal editor|neovim|termux-main'
  'lazygit|Development: Lazygit terminal Git UI|lazygit|termux-main'
  'nodejs|Development / AI: Node.js LTS + npm prerequisites|nodejs-lts|termux-main'
  'rust|Development: Rust toolchain|rust|termux-main'
  'golang|Development: Go toolchain|golang|termux-main'
  'jq|Development: jq JSON processor|jq|termux-main'
  'sqlite|Development: SQLite CLI|sqlite|termux-main'
  'taskmanager|System: XFCE task manager|xfce4-taskmanager|termux-x11'
  'ncdu|System: ncdu disk usage|ncdu|termux-main'
  'duf|System: duf filesystem usage|duf|termux-main'
  'lsof|System: lsof open files|lsof|termux-main'
  'strace|System: strace diagnostics|strace|termux-main'
  'keepassxc|Security: KeePassXC password manager|keepassxc|termux-x11'
  'rclone|Network: Rclone cloud file transfer|rclone|termux-main'
  'syncthing|Network: Syncthing (start separately)|syncthing|termux-main'
  'aria2|Network: aria2 download tools|aria2|termux-main'
  'nmap|Network: Nmap diagnostics|nmap|termux-main'
  'iperf3|Network: iperf3 throughput tools|iperf3|termux-main'
  'qbittorrent|Internet: qBittorrent|qbittorrent|termux-x11'
  'gnuplot|Science: Gnuplot|gnuplot|termux-main'
  'octave|Science: GNU Octave|octave|termux-main'
  'ai-codex|AI: Codex Termux @next setup recipe + Node.js LTS|nodejs-lts|termux-main'
  'ai-hermes|AI: Hermes canary setup guide (experimental; no agent install)|curl gnupg|termux-main'
)

_nt_native_app_lookup() {
  local entry id label packages repo
  for entry in "${_NT_NATIVE_APP_CATALOG[@]}"; do
    IFS='|' read -r id label packages repo <<<"$entry"
    [ "$id" = "$1" ] || continue
    read -r -a _NT_OPTIONAL_PACKAGES <<<"$packages"
    _NT_OPTIONAL_REPO="$repo"
    return 0
  done
  return 1
}

_nt_native_app_repository() {
  local entry id label packages repo package
  for entry in "${_NT_NATIVE_APP_CATALOG[@]}"; do
    IFS='|' read -r id label packages repo <<<"$entry"
    for package in $packages; do
      if [ "$package" = "$1" ]; then printf '%s\n' "$repo"; return 0; fi
    done
  done
  return 1
}

_nt_choose_native_apps() {
  local entry id label packages repo
  local -a options=('none|No optional apps')
  for entry in "${_NT_NATIVE_APP_CATALOG[@]}"; do
    IFS='|' read -r id label packages repo <<<"$entry"
    options+=("$id|$label")
  done
  _nt_pick 'Optional Native apps (select none to skip extras)' multi none "${options[@]}"
}


_nt_ai_guidance() {
  local provider="$1" selection=",${2:-},"
  case "$selection" in
    *,ai-codex,*)
      nt_info "$provider Codex: prerequisites selected; agent installation is a separate explicit step."
      if [ "$provider" = native ]; then
        nt_info 'Owner-used community build: npm install -g @mmmbuto/codex-cli-termux@next'
      else
        nt_info 'Inside the guest: npm install -g @openai/codex'
      fi ;;
  esac
  case "$selection" in
    *,ai-hermes,*)
      if [ "$provider" = native ]; then
        nt_warn 'Hermes Native canary is experimental: current upstream docs report the Termux package broken. No repository/key was added.'
      else
        nt_info 'Hermes: use the upstream Linux installer inside the guest; PRoot acceptance is separate.'
      fi ;;
  esac
  case "$selection" in
    *,ai-claude,*) nt_info 'Claude Code: use the upstream Linux installer inside the guest; Native Android is not selected.' ;;
  esac
  case "$selection" in
    *,ai-codex,*|*,ai-hermes,*|*,ai-claude,*)
      nt_info 'AI setup recipes, source/trust notes and login steps: docs/AI-TOOLS.md (repository).'
      nt_info 'No agent login, API key collection or external installer execution was performed.' ;;
  esac
}
