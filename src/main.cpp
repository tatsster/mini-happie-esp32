#include <Arduino.h>
#include <TFT_eSPI.h>

#include "cake_frames.h"
#include "rainyhearts_font.h"
#include <FS.h>
#include <LittleFS.h>
#include "config.h"
#include <WiFiManager.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>

constexpr uint8_t PIN_BUZZER = 25;

TFT_eSPI tft = TFT_eSPI();

constexpr uint16_t COLOR_DARK_PINK = 0x8909;  // #89204A, sampled from the cake outline

struct Note { uint16_t freq; uint16_t ms; };
const Note melody[] = {
    {294, 250}, {294, 250}, {330, 500}, {294, 500}, {392, 500}, {370, 1000},
    {294, 250}, {294, 250}, {330, 500}, {294, 500}, {440, 500}, {392, 1000},
    {294, 250}, {294, 250}, {587, 500}, {494, 500}, {392, 500}, {370, 500}, {330, 1000},
    {523, 250}, {523, 250}, {494, 500}, {392, 500}, {440, 500}, {392, 1000},
};
constexpr size_t MELODY_LEN = sizeof(melody) / sizeof(melody[0]);

// Draw a cake frame, optionally with text over it
// Offset to center 128×160 frames on the 240×320 screen
constexpr int16_t CAKE_X = (240 - CAKE_W) / 2;  // 56
constexpr int16_t CAKE_Y = (320 - CAKE_H) / 2;  // 80

void drawCake(uint8_t frame, const char *text = nullptr, uint8_t textSize = 1, int16_t textY = 36) {
    tft.fillScreen(TFT_BLACK);
    tft.pushImage(CAKE_X, CAKE_Y, CAKE_W, CAKE_H, CAKE_FRAMES[frame % CAKE_FRAME_COUNT]);
    if (text) {
        tft.setFreeFont(&rainyhearts16px);
        tft.setTextColor(COLOR_DARK_PINK);  // no bg color -> transparent over image
        tft.setTextDatum(MC_DATUM);
        tft.setTextSize(textSize);
        tft.drawString(text, 120, textY);
        tft.setTextSize(1);
        tft.setTextFont(1);
    }
}

// Buzzer plays the melody note by note
void playMelody() {
    for (size_t i = 0; i < MELODY_LEN; i++) {
        if (melody[i].freq > 0) {
            tone(PIN_BUZZER, melody[i].freq, melody[i].ms);
        }
        delay(melody[i].ms);
        noTone(PIN_BUZZER);
        delay(30);
    }
}

// One expression per step: 3 -> smile, 2 -> excited, 1 -> wink, finale -> happy
// Requires CAKE_FRAME_COUNT >= 4
void countdown() {
    const char *nums[] = {"3", "2", "1"};
    for (uint8_t i = 0; i < 3; i++) {
        drawCake(i, nums[i], 3, 36);  // 16px font x3 = chunky 48px digits
        tone(PIN_BUZZER, 880, 80);
        delay(700);
    }
    drawCake(3, "happy birthday!");
}

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

        // Step 8: get Content-Length
        int contentLength = http.getSize();

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
        uint8_t buf[512];
        int written = 0;
        while (http.connected() && written < contentLength) {
            int avail = stream->available();
            if (avail > 0) {
                int toRead = min(avail, (int)sizeof(buf));
                int n = stream->readBytes(buf, toRead);
                tmp.write(buf, n);
                written += n;
            } else {
                vTaskDelay(1);  // yield to IDLE0 — prevents WDT timeout (D-26)
            }
        }

        // Step 14: close temp file
        tmp.close();

        // Step 15: integrity check — only remove tmpPath on failure, NOT finalPath (D-13)
        if (written != contentLength) {
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
        LittleFS.rename(tmpPath, finalPath);

        // Step 18: persist new ETag to NVS only after successful write (integrity passed)
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

    // Step 3: download frames
    for (JsonVariant name : frames) {
        String fname = name.as<String>();
        String finalPath = "/frames/" + fname;
        String tmpPath   = "/tmp_" + fname;
        String url       = String(SERVER_URL) + "/frames/" + fname;
        downloadIfChanged(url.c_str(), finalPath.c_str(), tmpPath.c_str(), fname.c_str());
        vTaskDelay(10);  // yield between assets
    }

    // Step 4: download songs
    for (JsonVariant name : songs) {
        String sname    = name.as<String>();
        String finalPath = "/songs/" + sname;
        String tmpPath   = "/tmp_" + sname;
        String url       = String(SERVER_URL) + "/songs/" + sname;
        downloadIfChanged(url.c_str(), finalPath.c_str(), tmpPath.c_str(), sname.c_str());
        vTaskDelay(10);
    }

    // Steps 5-7: signal completion
    g_assetsReady = true;
    g_syncState = SYNC_DONE;
    Serial.println("[sync] done — assetsReady");
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

void setup() {
    Serial.begin(115200);

    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS mount failed — continuing without FS");
        // Phase 9 (LittleFS playback) will fail gracefully; no restart loop
    } else {
        Serial.println("LittleFS mounted");
    }
    // Optional: Serial.printf("LittleFS: %u KB used / %u KB total\n",
    //     LittleFS.usedBytes() / 1024, LittleFS.totalBytes() / 1024);

    pinMode(PIN_BUZZER, OUTPUT);

    tft.init();
    tft.setRotation(2);
    tft.setSwapBytes(true);  // image data is big-endian RGB565

    bool wifiOk = connectWiFi();

    if (wifiOk) {
        // Sync clock before any HTTPS — mbedTLS validates cert notBefore/notAfter
        // against system time, which is epoch-zero at cold boot without NTP.
        configTime(0, 0, "pool.ntp.org", "time.nist.gov");
        syncManifest();
    }
    countdown();
    playMelody();
    drawCake(0);
}

void loop() {
    // Auto-play is driven from setup(). Nothing to poll.
}