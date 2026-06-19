#pragma once

// ── Server URL ──────────────────────────────────────────────────────────────
// Edit this to your manager web server with HTTP/HTTPS:
#define SERVER_URL "https://happie.liftlab.dev"

// ── WiFi ────────────────────────────────────────────────────────────────────
#define WIFI_AP_NAME    "MiniHappie-Setup"  // captive portal AP SSID
#define WIFI_TIMEOUT_MS 180000              // portal timeout in ms (WIFI-03)

// ── NVS ─────────────────────────────────────────────────────────────────────
#define NVS_ETAG_NS     "etags"             // Preferences namespace for ETag storage (Phase 8)
