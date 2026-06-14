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
check "Birthday Device Manager"
check "tailwind.min.css"
check "/upload/frame"
check "/upload/song"
check "/manifest.json"
check "grid-cols-2"
check "Delete Frame"
check "Delete Song"
check "textContent"
check "Choose a PNG file"
check "128 × 160 pixels required"
check "Choose a song sheet"
check "Plain text (.txt)"
check "Uploading"
check "No frames uploaded"
check "No songs uploaded"
check '.replace(/\.[^.]+$/'

# XSS safety — these must NOT appear
if grep -qiF '<img' "$HTML"; then
  echo "FORBIDDEN: <img tag found (UI-03 is deferred — no img tags allowed)"
  exit 1
fi

if grep -qF 'innerHTML' "$HTML"; then
  echo "FORBIDDEN: innerHTML found (use textContent for XSS safety)"
  exit 1
fi

echo "OK"
