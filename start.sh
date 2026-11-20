#!/usr/bin/env bash
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

run_python() {
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    ".venv/Scripts/python.exe" "$@"
  elif [[ -x ".venv/bin/python" ]]; then
    ".venv/bin/python" "$@"
  elif command -v python >/dev/null 2>&1; then
    python "$@"
  elif command -v py >/dev/null 2>&1; then
    py "$@"
  else
    echo "ERROR: Python 3.10+ was not found."
    return 127
  fi
}

pause_menu() { read -r -p 'Press Enter to continue...' _; }

inspect_mod() {
  local car_path="${1:-}"
  if [[ -z "$car_path" ]]; then
    read -r -p 'Paste the full path to the extracted mod folder or ZIP: ' car_path
  fi
  car_path="${car_path#\"}"; car_path="${car_path%\"}"
  car_path="${car_path#\'}"; car_path="${car_path%\'}"
  if [[ -z "$car_path" ]]; then
    echo 'No path entered.'; return 1
  fi
  if [[ ! -e "$car_path" ]]; then
    printf 'ERROR: Path not found: %s\n' "$car_path"; return 1
  fi
  local name report
  name="$(basename "${car_path%/}")"
  mkdir -p reports
  report="reports/${name}-report.json"
  printf '\nInput:  %s\nOutput: %s\n\n' "$car_path" "$report"
  run_python -m nfsmw_installer.cli inspect "$car_path" -o "$report"
  local status=$?
  if [[ $status -eq 0 ]]; then
    printf '\nInspection completed. No game files were changed.\nReport: %s\n' "$report"
  else
    printf '\nInspection failed (exit %s).\n' "$status"
  fi
  return "$status"
}

# If a path is passed as an argument (e.g. drag-and-drop), inspect it directly.
if [[ $# -gt 0 ]]; then
  inspect_mod "$1"
  exit $?
fi

while true; do
  echo
  echo '=================================================='
  echo '   NFSMW ADD-ON INSTALLER - CONTROL PANEL'
  echo '=================================================='
  echo '  1. Inspect a car mod folder or ZIP archive'
  echo '  2. Run project tests'
  echo '  3. Open reports folder'
  echo '  4. Show help / current capabilities'
  echo '  5. Exit'
  echo
  read -r -p 'Choose an option [1-5]: ' choice
  case "$choice" in
    1)
      while true; do
        inspect_mod || true
        read -r -p 'Inspect another mod? [y/N]: ' again
        [[ "$again" =~ ^[Yy]$ ]] || break
      done
      ;;
    2)
      run_python -m unittest discover -s tests -v
      pause_menu
      ;;
    3)
      mkdir -p reports
      if command -v explorer.exe >/dev/null 2>&1; then
        explorer.exe "$(cygpath -w "$PWD/reports" 2>/dev/null || printf '%s' "$PWD/reports")" >/dev/null 2>&1 &
      elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$PWD/reports" >/dev/null 2>&1 &
      else
        printf 'Reports folder: %s/reports\n' "$PWD"
      fi
      ;;
    4)
      echo
      echo 'Current version: 0.1.0 (analysis-only foundation)'
      echo '- Inspects extracted folders and ZIP archives.'
      echo '- Detects common Unlimiter, NFSMS, ModLoader, MWPS,'
      echo '  INI, model, texture and resource files.'
      echo '- Parses NFSMS commands and generates JSON reports.'
      echo '- Optional VLT inventory comparison is available via CLI.'
      echo
      echo 'It does NOT yet install cars or modify VLT/BIN files.'
      echo 'RAR/7z listing requires 7-Zip on PATH.'
      pause_menu
      ;;
    5) exit 0 ;;
    *) echo 'Invalid choice.' ;;
  esac
done
