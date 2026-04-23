#!/usr/bin/env bash
#
# Build the Omniclaw macOS .pkg installer end-to-end (mirrors build.ps1 on Windows).
#
# 1. uv sync for mcp-server, orchestrator, discord-bot
# 2. npm build + copy frontend to mcp-server/static/
# 3. pip install PyInstaller + combined runtime deps
# 4. PyInstaller (one-folder bundle)
# 5. Optional: download Ollama.dmg for bundling
# 6. Assemble Omniclaw.app (PyInstaller output in Contents/MacOS, optional Ollama.dmg in Resources)
# 7. pkgbuild + productbuild → installer/macos/Output/OmniclawInstaller.pkg
#
# Usage:
#   ./build-mac.sh
#   ./build-mac.sh --skip-frontend --skip-sync --skip-ollama-download
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="${ROOT}/frontend"
SERVER="${ROOT}/mcp-server"
ORCHESTRATOR="${ROOT}/orchestrator"
DISCORD_BOT="${ROOT}/discord-bot"
STATIC_DEST="${SERVER}/static"
MAC_INSTALLER="${ROOT}/installer/macos"
PKG_ROOT="${ROOT}/installer/macos/.pkgroot"
BUILD_STAGING="${ROOT}/installer/macos/.staging"
OUTPUT_DIR="${MAC_INSTALLER}/Output"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "${MAC_INSTALLER}/Info.plist" 2>/dev/null || echo "0.1.0")"
OLLAMA_DMG="${MAC_INSTALLER}/Ollama.dmg"

SKIP_FRONTEND=0
SKIP_SYNC=0
SKIP_OLLAMA=0

for arg in "$@"; do
	case "$arg" in
	--skip-frontend) SKIP_FRONTEND=1 ;;
	--skip-sync) SKIP_SYNC=1 ;;
	--skip-ollama-download) SKIP_OLLAMA=1 ;;
	*)
		echo "Unknown option: $arg" >&2
		echo "Usage: $0 [--skip-frontend] [--skip-sync] [--skip-ollama-download]" >&2
		exit 1
		;;
	esac
done

step() { printf '\n==> %s\n' "$1"; }

require_cmd() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "Required command not found: $1" >&2
		exit 1
	}
}

require_cmd pkgbuild
require_cmd productbuild
if [[ "$SKIP_SYNC" -eq 0 ]]; then
	require_cmd uv
fi
if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
	require_cmd npm
fi

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
	PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
	PYTHON="python"
else
	echo "python3 or python not found" >&2
	exit 1
fi

if [[ "$SKIP_SYNC" -eq 0 ]]; then
	for svc in "$SERVER" "$ORCHESTRATOR" "$DISCORD_BOT"; do
		step "uv sync — $(basename "$svc")"
		( cd "$svc" && uv sync )
	done
else
	echo "Skipping uv sync (--skip-sync)" >&2
fi

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
	step "Building React frontend"
	( cd "$FRONTEND" && npm install && npm run build )
	FRONTEND_DIST="${FRONTEND}/dist"
	[[ -d "$FRONTEND_DIST" ]] || {
		echo "Frontend build output not found at $FRONTEND_DIST" >&2
		exit 1
	}
	step "Copying frontend build to mcp-server/static/"
	rm -rf "$STATIC_DEST"
	cp -R "$FRONTEND_DIST" "$STATIC_DEST"
else
	echo "Skipping frontend build (--skip-frontend)" >&2
	[[ -d "$STATIC_DEST" ]] || {
		echo "static/ folder missing; run without --skip-frontend first." >&2
		exit 1
	}
fi

step "Installing Python dependencies for PyInstaller"
(
	cd "$SERVER"
	"$PYTHON" -m pip install -q pyinstaller
	"$PYTHON" -m pip install -q \
		beautifulsoup4 fastmcp httpx "mcp[cli]" fastapi "uvicorn[standard]" \
		google-genai python-dotenv pydantic "discord.py" aiohttp playwright
)

step "Bundling with PyInstaller (MCP + orchestrator + Discord bot)"
( cd "$SERVER" && "$PYTHON" -m PyInstaller omniclaw.spec --noconfirm --clean )

DIST_APP="${SERVER}/dist/Omniclaw.app"
[[ -d "$DIST_APP" ]] || {
	echo "PyInstaller BUNDLE output not found at $DIST_APP" >&2
	echo "(The macOS spec must emit Omniclaw.app via BUNDLE — see omniclaw.spec.)" >&2
	exit 1
}
echo "PyInstaller app bundle ready at $DIST_APP"

if [[ "$SKIP_OLLAMA" -eq 0 ]]; then
	step "Downloading Ollama disk image (macOS)"
	if curl -fsSL -o "$OLLAMA_DMG" "https://ollama.com/download/Ollama.dmg"; then
		echo "Ollama DMG saved to $OLLAMA_DMG"
	else
		echo "Warning: could not download Ollama.dmg; post-install will prompt users to install Ollama manually." >&2
		rm -f "$OLLAMA_DMG"
	fi
else
	echo "Skipping Ollama download (--skip-ollama-download)" >&2
fi

step "Staging Omniclaw.app for the installer"
rm -rf "$BUILD_STAGING" "$PKG_ROOT"
mkdir -p "$PKG_ROOT" "$BUILD_STAGING"
cp -R "$DIST_APP" "$PKG_ROOT/"
if [[ -f "$OLLAMA_DMG" ]]; then
	mkdir -p "$PKG_ROOT/Omniclaw.app/Contents/Resources"
	cp "$OLLAMA_DMG" "$PKG_ROOT/Omniclaw.app/Contents/Resources/"
fi

mkdir -p "$OUTPUT_DIR"
COMPONENT_PKG="${BUILD_STAGING}/Omniclaw-component.pkg"
FINAL_PKG="${OUTPUT_DIR}/OmniclawInstaller.pkg"

step "pkgbuild (payload + scripts)"
pkgbuild \
	--root "$PKG_ROOT" \
	--identifier "com.omniclaw.pkg.app" \
	--version "$VERSION" \
	--install-location /Applications \
	--scripts "${MAC_INSTALLER}/scripts" \
	"$COMPONENT_PKG"

step "productbuild (distribution archive)"
productbuild --package "$COMPONENT_PKG" "$FINAL_PKG"

echo ""
echo "============================================"
echo "  Build complete!"
echo "  Installer: $FINAL_PKG"
echo "============================================"
