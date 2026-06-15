#!/usr/bin/env bash
# Smoke-check that server/static/index.html contains all required tokens.
# CWD-independent: paths are anchored to this script's own location.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML="$SCRIPT_DIR/../server/static/index.html"

if [ ! -f "$HTML" ]; then
  echo "MISSING FILE: $HTML"
  echo "Expected: $(realpath "$HTML" 2>/dev/null || echo "$HTML")"
  exit 1
fi

check() {
  local token="$1"
  if ! grep -qF "$token" "$HTML"; then
    echo "MISSING: $token"
    exit 1
  fi
}

# Required tokens
check "Mini Happie Manager"
check "tailwind.min.css"
check "/upload/frame"
check "/upload/song"
check "/manifest.json"
check "grid-cols-2"
check "Delete Frame"
check "Delete Song"
check "textContent"
check "Choose a PNG or JPEG"
check "auto-scaled to fit"
check "Choose a song sheet"
check "Plain text (.txt)"
check "Uploading"
check "No frames uploaded"
check "No songs uploaded"
check '.replace(/\.[^.]+$/'

# XSS safety — these must NOT appear
# Thumbnails are created via document.createElement("img") in JS — no literal <img in HTML source.
# If a literal <img tag appears it means someone bypassed the JS path (could be innerHTML risk).
if grep -qiF '<img' "$HTML"; then
  echo "FORBIDDEN: literal <img tag in HTML source — use document.createElement('img') instead"
  exit 1
fi

if grep -qF 'innerHTML' "$HTML"; then
  echo "FORBIDDEN: innerHTML found (use textContent for XSS safety)"
  exit 1
fi

echo "OK"
