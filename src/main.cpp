#include <Arduino.h>
#include <TFT_eSPI.h>

#include "cake_frames.h"
#include "rainyhearts_font.h"

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
void drawCake(uint8_t frame, const char *text = nullptr, uint8_t textSize = 1, int16_t textY = 36) {
    tft.pushImage(0, 0, CAKE_W, CAKE_H, CAKE_FRAMES[frame % CAKE_FRAME_COUNT]);
    if (text) {
        tft.setFreeFont(&rainyhearts16px);
        tft.setTextColor(COLOR_DARK_PINK);  // no bg color -> transparent over image
        tft.setTextDatum(MC_DATUM);
        tft.setTextSize(textSize);
        tft.drawString(text, 64, textY);
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
void countdown() {
    const char *nums[] = {"3", "2", "1"};
    for (uint8_t i = 0; i < 3; i++) {
        drawCake(i, nums[i], 3, 36);  // 16px font x3 = chunky 48px digits
        tone(PIN_BUZZER, 880, 80);
        delay(700);
    }
    drawCake(3, "happy birthday!");
}

void setup() {
    Serial.begin(115200);

    pinMode(PIN_BUTTON, INPUT_PULLUP);
    pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
    pinMode(PIN_BUZZER, OUTPUT);

    tft.init();
    tft.setRotation(0);
    tft.setSwapBytes(true);  // image data is big-endian RGB565
    // Horizontal mirror: clear MADCTL MX bit. Rotation-0 BLACKTAB is
    // MX|MY|BGR (0xC8); clearing MX -> MY (0x80). This clone also flips its
    // subpixel order when mirrored, so use RGB (drop the 0x08 BGR bit).
    tft.writecommand(0x36);  // MADCTL
    tft.writedata(0x80);
    drawCake(0);
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