#!/usr/bin/env bash
set -euo pipefail

APP_USER="sif"
APP_GROUP="sif"
APP_DIR="/opt/seen-it-first"
SERVICE_NAME="seen-it-first-edge.service"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DRY_RUN=false

usage() {
  cat <<USAGE
Usage: $0 [--dry-run]

Installs/updates Seen-It-First Edge as a systemd service.

Options:
  --dry-run   Print commands without making changes.
  -h, --help  Show this help message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

log() {
  printf '\n[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

run_cmd() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "DRY-RUN: $*"
  else
    "$@"
  fi
}

require_root() {
  if [[ "${DRY_RUN}" == "false" && "${EUID}" -ne 0 ]]; then
    echo "This installer must be run as root (try: sudo $0)." >&2
    exit 1
  fi
}

select_nologin_shell() {
  if [[ -x "/usr/sbin/nologin" ]]; then
    echo "/usr/sbin/nologin"
  else
    echo "/bin/false"
  fi
}

sync_application() {
  local src_dir="$1"
  log "Syncing application to ${APP_DIR}"
  run_cmd mkdir -p "${APP_DIR}"

  if command -v rsync >/dev/null 2>&1; then
    run_cmd rsync -a --delete \
      --exclude ".git" \
      --exclude "venv" \
      --exclude "__pycache__" \
      --exclude "*.pyc" \
      "${src_dir}/" "${APP_DIR}/"
  else
    echo "Warning: rsync not found; falling back to cp -a (no --delete support)." >&2
    run_cmd cp -a "${src_dir}/." "${APP_DIR}/"
  fi

  run_cmd chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
}

install_service_unit() {
  local source_unit="${APP_DIR}/systemd/${SERVICE_NAME}"
  local target_unit="${SYSTEMD_DIR}/${SERVICE_NAME}"

  if [[ ! -f "${source_unit}" ]]; then
    source_unit="${REPO_ROOT}/systemd/${SERVICE_NAME}"
  fi

  if [[ ! -f "${source_unit}" ]]; then
    echo "Service file not found: ${source_unit}" >&2
    exit 1
  fi

  log "Installing systemd unit"
  run_cmd install -m 0644 "${source_unit}" "${target_unit}"

  if command -v systemd-analyze >/dev/null 2>&1; then
    if [[ "${DRY_RUN}" == "true" ]]; then
      echo "DRY-RUN: systemd-analyze verify ${target_unit}"
    else
      systemd-analyze verify "${target_unit}"
    fi
  fi

  run_cmd systemctl daemon-reload
  run_cmd systemctl enable "${SERVICE_NAME}"
}

post_install_report() {
  log "Post-install verification"
  echo "- Service unit: ${SYSTEMD_DIR}/${SERVICE_NAME}"
  echo "- App directory: ${APP_DIR}"

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "Dry-run mode: verification commands were not executed."
    return
  fi

  echo
  echo "User/Group:"
  id "${APP_USER}"

  echo
  echo "Directory ownership:"
  stat -c '%U:%G %n' "${APP_DIR}" "${APP_DIR}/data" "${APP_DIR}/logs" "${APP_DIR}/venv"

  echo
  echo "Python environment:"
  "${APP_DIR}/venv/bin/python" --version
  "${APP_DIR}/venv/bin/pip" --version

  echo
  echo "Service enablement:"
  systemctl is-enabled "${SERVICE_NAME}"

  echo
  echo "Service status (not started by installer):"
  systemctl status "${SERVICE_NAME}" --no-pager || true

  echo
  echo "To start now: sudo systemctl start ${SERVICE_NAME}"
  echo "Logs: sudo journalctl -u ${SERVICE_NAME} -f"
}

main() {
  require_root
  local nologin_shell
  nologin_shell="$(select_nologin_shell)"

  log "Ensuring group ${APP_GROUP} exists"
  if getent group "${APP_GROUP}" >/dev/null 2>&1; then
    echo "Group ${APP_GROUP} already exists."
  else
    run_cmd groupadd --system "${APP_GROUP}"
  fi

  log "Ensuring user ${APP_USER} exists and is configured"
  if id -u "${APP_USER}" >/dev/null 2>&1; then
    run_cmd usermod -g "${APP_GROUP}" -d "${APP_DIR}" -s "${nologin_shell}" "${APP_USER}"
  else
    run_cmd useradd --system --gid "${APP_GROUP}" --home-dir "${APP_DIR}" --create-home --shell "${nologin_shell}" "${APP_USER}"
  fi

  sync_application "${REPO_ROOT}"

  log "Creating and validating virtual environment"
  if [[ ! -x "${APP_DIR}/venv/bin/python" ]]; then
    run_cmd python3 -m venv --system-site-packages "${APP_DIR}/venv"
  fi

  run_cmd "${APP_DIR}/venv/bin/pip" install --upgrade pip
  run_cmd "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

  log "Ensuring runtime directories exist"
  run_cmd mkdir -p "${APP_DIR}/data" "${APP_DIR}/logs"
  run_cmd chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}/data" "${APP_DIR}/logs" "${APP_DIR}/venv"

  install_service_unit
  post_install_report
}

main
