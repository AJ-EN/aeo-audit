#!/bin/bash
set -e

DRY_RUN=false
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    DRY_RUN=true
  fi
done

REPO="AJ-EN/aeo-audit"
BINARY="aeo-audit"
INSTALL_DIR="${HOME}/.local/bin"

# Detect OS/Arch
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case $ARCH in
  x86_64) ARCH="x64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) echo "Unsupported arch: $ARCH"; exit 1 ;;
esac

echo "Target Platform: ${OS}-${ARCH}"

if [ "$DRY_RUN" = true ]; then
  echo "[Dry Run] Would check latest release of ${REPO} on GitHub"
  echo "[Dry Run] Would download matching binary to ${INSTALL_DIR}/${BINARY}"
  echo "[Dry Run] Dry run validation completed successfully!"
  exit 0
fi

# Get latest release
LATEST_URL="https://api.github.com/repos/${REPO}/releases/latest"
DOWNLOAD_URL=$(curl -s "$LATEST_URL" | grep "browser_download_url.*${OS}-${ARCH}" | head -1 | cut -d '"' -f 4)

if [ -z "$DOWNLOAD_URL" ]; then
  echo "No binary for ${OS}-${ARCH}. Install via pipx: pipx install git+https://github.com/${REPO}"
  exit 1
fi

mkdir -p "$INSTALL_DIR"
curl -fsSL "$DOWNLOAD_URL" -o "${INSTALL_DIR}/${BINARY}"
chmod +x "${INSTALL_DIR}/${BINARY}"

echo "Installed ${BINARY} to ${INSTALL_DIR}"
echo "Add to PATH: export PATH=\"${INSTALL_DIR}:\$PATH\""
