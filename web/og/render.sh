#!/usr/bin/env sh
# Render the share card (og/card.html) to public/og-image.png at 1200x630 with headless Chrome or Edge.
#   sh og/render.sh            (run from web/)
set -e
cd "$(dirname "$0")/.."
BROWSER="${BROWSER:-$(command -v google-chrome || command -v chromium || command -v chrome || true)}"
[ -z "$BROWSER" ] && [ -x "/c/Program Files/Google/Chrome/Application/chrome.exe" ] && BROWSER="/c/Program Files/Google/Chrome/Application/chrome.exe"
[ -z "$BROWSER" ] && [ -x "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" ] && BROWSER="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
CARD="file:///$(cd og && pwd -W 2>/dev/null || pwd)/card.html"
OUT="$(cd public && pwd -W 2>/dev/null || pwd)/og-image.png"
"$BROWSER" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1200,630 --screenshot="$OUT" "$CARD" >/dev/null 2>&1
echo "wrote public/og-image.png"
