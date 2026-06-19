#pragma once

// ── Server URL ──────────────────────────────────────────────────────────────
// Edit this to switch between Cloudflare HTTPS and Caddy plain HTTP:
//   Cloudflare (HTTPS):  "https://your-tunnel.trycloudflare.com"
//   Caddy (HTTP):        "http://192.168.1.x:8080"
#define SERVER_URL "https://your-tunnel.trycloudflare.com"

// ── WiFi ────────────────────────────────────────────────────────────────────
#define WIFI_AP_NAME    "MiniHappie-Setup"  // captive portal AP SSID
#define WIFI_TIMEOUT_MS 180000              // portal timeout in ms (WIFI-03)

// ── NVS ─────────────────────────────────────────────────────────────────────
#define NVS_ETAG_NS     "etags"             // Preferences namespace for ETag storage (Phase 8)
