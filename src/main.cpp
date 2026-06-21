#include <Arduino.h>
#include <TFT_eSPI.h>

#include "cake_frames.h"
#include "rainyhearts_font.h"
#include <LittleFS.h>
#include "config.h"
#include <WiFiManager.h>

constexpr uint8_t PIN_BUTTON = 14;
constexpr uint8_t PIN_BOOT_BTN = 0;  // onboard BOOT button, works without wiring
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

bool connectWiFi() {
    // SCREEN 1: Connecting — drawn before the blocking autoConnect() call
    tft.fillScreen(TFT_NAVY);
    tft.setTextColor(TFT_WHITE, TFT_NAVY);
    tft.setTextDatum(MC_DATUM);
    tft.setTextFont(2);
    tft.drawString("Connecting...", 120, 160);
    Serial.println("WiFi: connecting");

    WiFiManager wm;
    wm.setConfigPortalTimeout(WIFI_TIMEOUT_MS / 1000);  // seconds, not ms

    // SCREEN 2: Portal active — drawn inside callback when AP comes up
    wm.setAPCallback([](WiFiManager* myWM) {
        tft.fillScreen(TFT_NAVY);
        tft.setTextColor(TFT_WHITE, TFT_NAVY);
        tft.setTextDatum(MC_DATUM);
        tft.setTextFont(4);
        tft.drawString("Setup WiFi:", 120, 130);
        tft.setTextFont(2);  // reset — setTextFont is not sticky
        tft.drawString(WIFI_AP_NAME, 120, 170);
        tft.drawString("192.168.4.1", 120, 194);
    });

    bool ok = wm.autoConnect(WIFI_AP_NAME);

    // Reinstate TFT state — WiFiManager's blocking loop leaves TFT_eSPI in an undefined state
    tft.init();
    tft.setRotation(2);
    tft.setSwapBytes(true);

    if (ok) {
        // SCREEN 3: Connected
        tft.fillScreen(TFT_NAVY);
        tft.setTextColor(TFT_WHITE, TFT_NAVY);
        tft.setTextDatum(MC_DATUM);
        tft.setTextFont(2);
        tft.drawString("WiFi connected!", 120, 160);
        Serial.println("WiFi connected");
        delay(1000);
        return true;
    } else {
        // SCREEN 4: Offline mode (persistent; distinct dark-grey background)
        tft.fillScreen(TFT_DARKGREY);
        tft.setTextColor(TFT_WHITE, TFT_DARKGREY);
        tft.setTextDatum(MC_DATUM);
        tft.setTextFont(2);
        tft.drawString("Offline mode", 120, 148);
        tft.drawString("Press button to play", 120, 172);
        Serial.println("WiFi offline - portal timed out");
        return false;
    }
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

    pinMode(PIN_BUTTON, INPUT_PULLUP);
    pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
    pinMode(PIN_BUZZER, OUTPUT);

    tft.init();
    tft.setRotation(2);
    tft.setSwapBytes(true);  // image data is big-endian RGB565

    bool wifiOk = connectWiFi();

    if (wifiOk) {
        // Sync clock before any HTTPS — mbedTLS validates cert notBefore/notAfter
        // against system time, which is epoch-zero at cold boot without NTP.
        configTime(0, 0, "pool.ntp.org", "time.nist.gov");

        // Phase 7: manifest fetch + asset sync goes here
        // if (wifiOk) { syncAssets(); }

        drawCake(0);
    }
    // If !wifiOk: "Offline mode" screen persists; do NOT call drawCake(0)
}

void loop() {
    static bool lastButton = HIGH;
    bool now = digitalRead(PIN_BUTTON) && digitalRead(PIN_BOOT_BTN);

    if (lastButton == HIGH && now == LOW) {
        delay(20);
        countdown();
        playMelody();
        drawCake(0);  // back to idle smile
    }
    lastButton = now;
}