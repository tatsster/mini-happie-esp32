#include <Arduino.h>
#include <TFT_eSPI.h>

#include <FS.h>
#include <LittleFS.h>
#include "config.h"
#include <WiFiManager.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>

constexpr uint8_t PIN_BUZZER = 25;

TFT_eSPI tft = TFT_eSPI();

// Frame buffer: 128×160 pixels × 2 bytes = 40,960 bytes — file scope (.bss), never stack
static uint16_t frameBuf[128 * 160];

// Frame centering constants: center 128×160 on 240×320 display (D-03)
constexpr int16_t FRAME_X = (240 - 128) / 2;  // 56
constexpr int16_t FRAME_Y = (320 - 160) / 2;  // 80
constexpr uint8_t MAX_FRAMES = 32;  // sequential-probe cap (D-07)

enum SyncState { SYNC_IDLE, SYNC_CONNECTING, SYNC_DOWNLOADING, SYNC_DONE, SYNC_FAILED };
volatile SyncState g_syncState = SYNC_IDLE;
volatile bool g_assetsReady = false;

bool connectWiFi() {
    Serial.println("WiFi: connecting");

    WiFiManager wm;
    wm.setConfigPortalTimeout(WIFI_TIMEOUT_MS / 1000);  // seconds, not ms

    // Portal active — no tft.* calls; sync task owns no TFT (D-02/D-09)
    wm.setAPCallback([](WiFiManager* myWM) {
        g_syncState = SYNC_CONNECTING;
        Serial.println("[sync] portal active");
    });

    bool ok = wm.autoConnect(WIFI_AP_NAME);

    if (ok) {
        Serial.println("WiFi connected");
        return true;
    } else {
        Serial.println("WiFi offline...");
        return false;
    }
}

bool downloadIfChanged(const char* url, const char* finalPath, const char* tmpPath, const char* nvsKey) {
    // WR-04: NVS keys are limited to 15 chars (NVS_KEY_NAME_MAX_SIZE). Truncate with log.
    char safeKey[16];
    if (strlen(nvsKey) > 15) {
        snprintf(safeKey, sizeof(safeKey), "%.15s", nvsKey);
        Serial.printf("[sync] WARNING: NVS key '%s' exceeds 15 chars, truncated to '%s'\n", nvsKey, safeKey);
        nvsKey = safeKey;
    }

    for (int attempt = 0; attempt < 2; attempt++) {
        // Step 1: read stored ETag from NVS
        Preferences prefs;
        prefs.begin(NVS_ETAG_NS, true);  // read-only
        String storedETag = prefs.getString(nvsKey, "");
        prefs.end();

        // Step 2: set up HTTPClient
        HTTPClient http;
        http.begin(url);
        http.setFollowRedirects(HTTPC_FORCE_FOLLOW_REDIRECTS);
        http.useHTTP10(true);

        // Step 3: send If-None-Match if we have a cached ETag
        if (storedETag.length() > 0) {
            http.addHeader("If-None-Match", storedETag);
        }

        // Step 4: register ETag response header collection — MUST be before GET()
        const char* headerKeys[] = {"ETag"};
        http.collectHeaders(headerKeys, 1);

        // Step 5: issue request
        int code = http.GET();

        // Step 6: 304 — nothing changed, skip download
        if (code == 304) {
            Serial.printf("[sync] %s: 304 skipped\n", nvsKey);
            http.end();
            return false;
        }

        // Step 7: non-200 failure
        if (code != 200) {
            Serial.printf("[sync] %s: attempt %d error %d\n", nvsKey, attempt, code);
            http.end();
            if (attempt == 0) {
                vTaskDelay(2000 / portTICK_PERIOD_MS);
                continue;
            } else {
                return false;
            }
        }

        // Step 8: get Content-Length (-1 if server omits header)
        int contentLength = http.getSize();
        bool lengthKnown = (contentLength >= 0);  // CR-02: handle unknown-length streaming

        // Step 9: get stream pointer
        WiFiClient* stream = http.getStreamPtr();

        // Step 10: open temp file for writing
        fs::File tmp = LittleFS.open(tmpPath, FILE_WRITE, true);

        // Step 11: bail if file open failed
        if (!tmp) {
            Serial.printf("[sync] %s: failed to open tmp file\n", nvsKey);
            http.end();
            if (attempt == 0) {
                vTaskDelay(2000 / portTICK_PERIOD_MS);
                continue;
            } else {
                return false;
            }
        }

        // Step 12-13: stream download in 512-byte chunks; yield to IDLE0 between chunks
        // CR-02: loop until disconnected when length unknown; WR-01: break on 10s stall
        uint8_t buf[512];
        int written = 0;
        bool writeError = false;
        unsigned long lastProgress = millis();
        while (http.connected() && (!lengthKnown || written < contentLength)) {
            int avail = stream->available();
            if (avail > 0) {
                int toRead = min(avail, (int)sizeof(buf));
                int n = stream->readBytes(buf, toRead);
                size_t actual = tmp.write(buf, n);  // WR-02: check write return value
                if ((int)actual != n) {
                    writeError = true;
                    break;
                }
                written += n;
                lastProgress = millis();
            } else {
                if (millis() - lastProgress > 10000UL) {  // WR-01: 10s no-progress timeout
                    Serial.printf("[sync] %s: stalled\n", nvsKey);
                    break;
                }
                vTaskDelay(1);  // yield to IDLE0 — prevents WDT timeout (D-26)
            }
        }

        // Step 14: close temp file
        tmp.close();

        // WR-02: write error (fs full?) — clean up and retry/fail
        if (writeError) {
            Serial.printf("[sync] %s: write error (fs full?)\n", nvsKey);
            LittleFS.remove(tmpPath);
            http.end();
            if (attempt == 0) { vTaskDelay(2000 / portTICK_PERIOD_MS); continue; }
            else { return false; }
        }

        // Step 15: integrity check — only when Content-Length was declared (CR-02)
        // Only remove tmpPath on failure, NOT finalPath (D-13)
        if (lengthKnown && written != contentLength) {
            Serial.printf("[sync] %s: truncated %d/%d attempt %d\n", nvsKey, written, contentLength, attempt);
            LittleFS.remove(tmpPath);
            http.end();
            if (attempt == 0) {
                vTaskDelay(2000 / portTICK_PERIOD_MS);
                continue;
            } else {
                return false;
            }
        }

        // Step 16: read ETag response header before http.end()
        String serverETag = http.header("ETag");
        http.end();

        // Step 17: atomic replacement — remove existing then rename tmp (D-12)
        LittleFS.remove(finalPath);
        bool renamed = LittleFS.rename(tmpPath, finalPath);
        if (!renamed) {
            Serial.printf("[sync] %s: rename failed, keeping old ETag\n", nvsKey);
            // tmpPath may or may not still exist; attempt cleanup
            LittleFS.remove(tmpPath);
            if (attempt == 0) {
                vTaskDelay(2000 / portTICK_PERIOD_MS);
                continue;
            } else {
                return false;
            }
        }

        // Step 18: persist new ETag only after confirmed rename (D-12)
        if (serverETag.length() > 0) {
            Preferences prefs2;
            prefs2.begin(NVS_ETAG_NS, false);  // read-write
            prefs2.putString(nvsKey, serverETag);
            prefs2.end();
        }

        // Step 19: log success
        Serial.printf("[sync] %s: 200 downloaded %d bytes\n", nvsKey, written);
        return true;
    }
    // Fallthrough: both attempts failed; finalPath left untouched if previously existed (D-13)
    return false;
}

void syncAssets(JsonArray frames, JsonArray songs) {
    // Step 1: ensure directories exist (no-op if already present)
    LittleFS.mkdir("/frames");
    LittleFS.mkdir("/songs");

    // Step 2: signal download phase
    g_syncState = SYNC_DOWNLOADING;

    // WR-03: track success/fail counts for logging
    int succeeded = 0;
    int failed = 0;

    // Step 3: download frames
    for (JsonVariant name : frames) {
        String fname = name.as<String>();
        String finalPath = "/frames/" + fname;
        String tmpPath   = "/tmp_" + fname;
        String url       = String(SERVER_URL) + "/frames/" + fname;
        bool ok = downloadIfChanged(url.c_str(), finalPath.c_str(), tmpPath.c_str(), fname.c_str());
        if (ok) { succeeded++; } else { failed++; }
        vTaskDelay(10);  // yield between assets
    }

    // Step 4: download songs
    for (JsonVariant name : songs) {
        String sname    = name.as<String>();
        String finalPath = "/songs/" + sname;
        String tmpPath   = "/tmp_" + sname;
        String url       = String(SERVER_URL) + "/songs/" + sname;
        bool ok = downloadIfChanged(url.c_str(), finalPath.c_str(), tmpPath.c_str(), sname.c_str());
        if (ok) { succeeded++; } else { failed++; }
        vTaskDelay(10);
    }

    // Steps 5-7: signal completion (WR-03: log success/fail counts)
    // g_assetsReady always set true: main core plays from LittleFS after this flag is set
    g_assetsReady = true;
    g_syncState = SYNC_DONE;
    Serial.printf("[sync] done — assetsReady (downloaded %d, skipped/failed %d)\n", succeeded, failed);
}

void syncManifest() {
    // Runs on core 0 — no tft.* calls (D-02); status shown by main core via g_syncState
    String url = String(SERVER_URL) + "/manifest.json";

    // begin(String url): auto-selects TLSTraits+setInsecure() for https://
    // or plain TransportTraits for http:// — handles both SERVER_URL forms
    HTTPClient http;
    http.begin(url);
    http.setFollowRedirects(HTTPC_FORCE_FOLLOW_REDIRECTS);
    http.useHTTP10(true);  // disable chunked transfer; enables direct stream parsing

    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK) {
        Serial.printf("Manifest fetch failed: %d\n", httpCode);
        http.end();
        g_syncState = SYNC_FAILED;  // D-15: HTTP error → SYNC_FAILED
        return;
    }

    JsonDocument doc;  // v7 API — no capacity template, heap-allocated elastically
    DeserializationError err = deserializeJson(doc, http.getStream());
    http.end();

    if (err) {
        Serial.printf("Manifest parse error: %s\n", err.c_str());
        g_syncState = SYNC_FAILED;  // D-15: JSON parse error → SYNC_FAILED
        return;
    }

    JsonArray frames = doc["frames"].as<JsonArray>();
    JsonArray songs  = doc["songs"].as<JsonArray>();
    Serial.printf("[sync] manifest: %d frames, %d songs\n", frames.size(), songs.size());
    syncAssets(frames, songs);
}

// TFT status helper — main core only; never called from sync task (D-02/D-08)
void showSyncStatus(const char* msg) {
    tft.fillScreen(TFT_NAVY);
    tft.setTextColor(TFT_WHITE, TFT_NAVY);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString(msg, 120, 160);
}

// FreeRTOS task pinned to core 0: WiFi → NTP → manifest → asset downloads (D-01)
void syncTask(void* param) {
    g_syncState = SYNC_CONNECTING;
    Serial.println("[sync] task started on core 0");

    bool wifiOk = connectWiFi();
    if (!wifiOk) {
        g_syncState = SYNC_FAILED;
        Serial.println("[sync] wifi failed");
        vTaskDelete(nullptr);
        return;
    }

    // NTP sync after WiFi — setInsecure() makes this optional but good practice
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");

    // Fetch manifest + download assets (sets g_assetsReady and g_syncState internally)
    syncManifest();

    vTaskDelete(nullptr);
}

void setup() {
    Serial.begin(115200);

    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS mount failed — continuing without FS");
        // Phase 9 (LittleFS playback) will fail gracefully; no restart loop
    } else {
        Serial.println("LittleFS mounted");
    }

    pinMode(PIN_BUZZER, OUTPUT);

    // Authoritative TFT init — must complete before task launch (D-03)
    tft.init();
    tft.setRotation(2);
    tft.setSwapBytes(true);  // image data is big-endian RGB565

    // Launch sync task on core 0; main core continues immediately (D-01)
    xTaskCreatePinnedToCore(syncTask, "sync", 16384, nullptr, 1, nullptr, 0);

    bool hasAssets = LittleFS.exists("/frames/frame_0.bin");

    if (hasAssets) {
        // Assets cached — loop() plays from LittleFS immediately (OFFLINE-01/OFFLINE-02 fast path)
        return;
    } else {
        // First boot: no cached assets — show status until sync completes or fails (D-07/D-10)
        while (!g_assetsReady) {
            SyncState state = g_syncState;
            if (state == SYNC_CONNECTING || state == SYNC_IDLE) {
                showSyncStatus("Connecting...");
            } else if (state == SYNC_DOWNLOADING) {
                showSyncStatus("Downloading...");
            } else if (state == SYNC_FAILED) {
                showSyncStatus("Sync failed");
                delay(2000);
                break;
            }
            delay(200);  // poll every 200ms
        }
        // loop() handles all playback from here (D-04)
    }
}

void loop() {
    // Step 1: Build frame list via sequential probe (D-07)
    // Cap at MAX_FRAMES=32 to guard against corrupted FS causing unbounded probe (T-09-02)
    char framePaths[MAX_FRAMES][28];
    uint8_t frameCount = 0;
    for (uint8_t i = 0; i < MAX_FRAMES; i++) {
        char path[28];
        snprintf(path, sizeof(path), "/frames/frame_%u.bin", i);
        if (!LittleFS.exists(path)) break;
        memcpy(framePaths[frameCount++], path, sizeof(path));
    }

    // Step 2: No assets — static error screen (D-06/D-11)
    if (frameCount == 0) {
        showSyncStatus("No content. Restart to retry.");
        return;
    }

    // Step 3: Frame animation — 500ms fixed delay per frame (D-10, PLAY-01)
    for (uint8_t i = 0; i < frameCount; i++) {
        fs::File f = LittleFS.open(framePaths[i], FILE_READ);
        if (f) {  // T-09-01: guard open failure (Pitfall 4)
            int n = f.read((uint8_t*)frameBuf, sizeof(frameBuf));
            f.close();  // close before delay — do not hold handle during 500ms (anti-pattern)
            if (n == (int)sizeof(frameBuf)) {
                tft.pushImage(FRAME_X, FRAME_Y, 128, 160, frameBuf);
            } else {
                // T-09-01: short read — skip this frame, never push partial buffer (Pitfall 2)
                Serial.printf("[play] short read frame %u: %d bytes\n", i, n);
            }
        }
        delay(500);  // D-10: delay() calls vTaskDelay internally — yields to FreeRTOS scheduler
    }

    // Step 4: Song playback — probe /songs/song_0.json only (D-08, PLAY-02)
    fs::File sf = LittleFS.open("/songs/song_0.json", FILE_READ);
    if (sf) {
        JsonDocument doc;  // v7 API: heap-allocated elastically, no capacity template
        DeserializationError err = deserializeJson(doc, sf);
        sf.close();  // close before acting on data — do not hold handle during tone() (Pattern 2)
        if (!err) {
            for (JsonObject note : doc.as<JsonArray>()) {
                uint16_t freq = note["freq"];
                uint16_t ms   = note["ms"];
                if (freq > 0) {  // T-09-03: guard freq==0 rests (Pitfall 6)
                    tone(PIN_BUZZER, freq, ms);
                }
                delay(ms);
                noTone(PIN_BUZZER);
                delay(30);
            }
        } else {
            Serial.printf("[play] song parse error: %s\n", err.c_str());
        }
    }
    // If no song file → play silently (no-op) per D-08

    // Step 5: Hot-reload check (D-09)
    // Reset BEFORE returning so next loop() call re-probes the frame list (Pitfall 5)
    if (g_assetsReady) {
        g_assetsReady = false;
        Serial.println("[play] new assets flagged — reloading on next cycle");
    }
    // return — Arduino calls loop() again automatically
}