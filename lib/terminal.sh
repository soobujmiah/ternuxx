# Optional shared PRoot terminal client and Native broker service.
nt_cmd_terminal() {
  nt_require_termux || return 1
  nt_require_command python3 || return 1
  python3 "$_TN_LIB_DIR/terminal_cli.py" "$@"
}
