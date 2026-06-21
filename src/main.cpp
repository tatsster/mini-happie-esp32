#include <Arduino.h>
#include <TFT_eSPI.h>

#include "cake_frames.h"
#include "rainyhearts_font.h"
#include <LittleFS.h>
#include "config.h"
#include <WiFiManager.h>
#include <HTTPClient.h>
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

void syncManifest() {
    // D-01/D-02: Show syncing screen before blocking HTTP call
    tft.fillScreen(TFT_NAVY);
    tft.setTextColor(TFT_WHITE, TFT_NAVY);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString("Syncing...", 120, 160);

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
        return;  // D-04: silent fallback
    }

    JsonDocument doc;  // v7 API — no capacity template, heap-allocated elastically
    DeserializationError err = deserializeJson(doc, http.getStream());
    http.end();

    if (err) {
        Serial.printf("Manifest parse error: %s\n", err.c_str());
        return;  // D-04: silent fallback
    }

    // D-03: log frame and song counts on successful parse
    JsonArray frames = doc["frames"].as<JsonArray>();
    JsonArray songs  = doc["songs"].as<JsonArray>();
    Serial.printf("Manifest: %d frames, %d songs\n", frames.size(), songs.size());
    // Phase 8 will use frames/songs arrays for asset download
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