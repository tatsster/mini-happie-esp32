# happy-birthday-esp32

An interactive birthday-themed embedded electronics project built around an
ESP32. A small SPI TFT display shows animated "happy birthday" graphics and
pixel-style visuals, a passive piezo buzzer plays the happy birthday melody,
and a push button triggers the animation and sound sequence.

The project is first prototyped on a breadboard, then converted into a
custom-designed PCB, a themed carrier board for the ESP32 dev
board and connected modules with decorative silkscreen artwork.

## Features
- ESP32-based control system
- 1.8" SPI TFT color display (ST7735, 128 x 160)
- Passive buzzer for melody playback
- Custom PCB layout and artwork
- USB powered

## Hardware

| Component       | ESP32 pin | Notes                              |
|-----------------|-----------|------------------------------------|
| TFT CS          | GPIO5     | SPI chip select                    |
| TFT DC          | GPIO16    | data/command                       |
| TFT RST         | GPIO17    |                                    |
| TFT SCK         | GPIO18    | hardware SPI clock                 |
| TFT MOSI        | GPIO23    | hardware SPI MOSI                  |
| TFT VCC         | 3V3       | 3.3V logic                         |
| TFT BLK         | 3V3       | backlight                          |
| Buzzer +        | GPIO25    | passive piezo                      |
| Button          | GPIO14    | to GND, INPUT_PULLUP               |

All grounds tied together.

## Bill of materials

| Qty | Part | Notes |
|-----|------|-------|
| 1 | ESP32 DevKit V1 (30-pin) | Pin labels are `Dxx` = `GPIOxx` |
| 1 | 1.8" SPI TFT, ST7735, 128x160 | BLACKTAB variant here; pins: GND VCC SCL SDA RST(DST) DC CS BLK |
| 1 | Passive piezo buzzer | Must be **passive** (plays tones), not active (one fixed beep) |
| 1 | Momentary push button | Optional — onboard BOOT works for testing |
| — | Breadboard + jumper wires | Use the power rails to fan out 3V3 / GND |
| 1 | USB **data** cable | Charge-only cables cause upload failures |

## Recreate from scratch (step by step)

### 1. Install tooling
- [PlatformIO](https://platformio.org/) (VS Code extension or `pip install platformio`).
- Python 3 with Pillow for the asset converters: `pip3 install pillow`.

### 2. Get the code
```
git clone https://github.com/codedbycupidity/happy-birthday-esp32.git
cd happy-birthday-esp32
```
The `TFT_eSPI` library and all display pin/variant settings are declared in
`platformio.ini` as `build_flags` — PlatformIO installs it on the first build.
No manual `User_Setup.h` editing is needed.

### 3. Wire it (breadboard)
Follow the **Hardware** table above. Tips learned the hard way:
- The ESP32 has only one **3V3** pin. Jumper it to the breadboard **+ rail**,
  then feed TFT `VCC` and `BLK` from that rail. Do the same for **GND** → **− rail**
  (TFT GND + buzzer + button all share it).
- On the DevKit, GPIO16/17 are silkscreened **RX2/TX2** — they still work as
  DC/RST. CS is **D5**.
- Seat the TFT firmly. A loose/cold joint shows as a **white screen that flickers
  when wiggled** — push pins fully in or solder them.
- The passive buzzer has **no polarity**: either leg to D25, the other to GND.

### 4. Prepare art and fonts
- Make pixel art at exactly **128 x 160** (PNG, transparency OK — it's composited
  onto black). Drop frames in `assets/`.
- Drop a `.ttf` in `assets/` (this project uses Rainy Hearts, a pixel font).
- Convert to C headers (see **Asset pipeline** below). The repo already ships the
  generated `include/*.h`, so this is only needed if you change the art/font.

### 5. Build and flash
```
pio run -t upload
```
If it fails to connect, see **Manual download mode** below (this board needs it).

### 6. Tune the display (if your panel differs)
These are the knobs we actually had to turn for this hardware:
- **Wrong/garbled colors on images** → `tft.setSwapBytes(true)` (already set) —
  the generated arrays are big-endian.
- **Shifted pixels / off colors on init** → wrong tab variant. Change
  `-DST7735_BLACKTAB` in `platformio.ini` to `GREENTAB`, `GREENTAB2/3`, or `REDTAB`.
- **Mirror the whole display L↔R** → write MADCTL directly after `init()`:
  `tft.writecommand(0x36); tft.writedata(0x80);` (rotation-0 BLACKTAB is `0xC8`;
  clearing the MX bit flips it). Some clones also flip subpixel order when
  mirrored — if red/blue swap, drop the `0x08` BGR bit (use `0x80` not `0x88`).

### 7. Use it
Press **BOOT** (or the D14 button): 3‑2‑1 countdown (one cake expression per
step) → "happy birthday!" → the buzzer plays the melody → back to the idle
cake. Idle shows a static smiling cake.

## Build

PlatformIO:

```
pio run                 # build
pio run -t upload       # flash
pio device monitor      # open serial
```

Notes:
- `upload_speed` is 460800 — this board's serial chip fails at 921600.
- The display is an ST7735 **BLACKTAB** variant (`-DST7735_BLACKTAB` in
  `platformio.ini`). If a different module shows shifted pixels or wrong
  colors, try `GREENTAB`, `GREENTAB2/3`, or `REDTAB` instead.
- The onboard BOOT button (GPIO0) triggers the sequence too, so no external
  button is needed for testing.

### Manual download mode (if upload fails to connect)

This board's auto-reset is unreliable — uploads often fail with
`Failed to connect to ESP32: No serial data received`. Force download mode by
hand:

```
pio run -t upload       # start it, then do the button sequence below
```

1. **Press and hold BOOT.**
2. Run the upload (or have it already running at "Connecting……").
3. Keep holding BOOT through the whole "Connecting……" phase.
4. Release BOOT once "Writing at 0x..." percentages appear.

Alternatively, park the board in download mode first, then upload: hold BOOT →
tap EN → release BOOT, then run `pio run -t upload`. If it still won't connect,
swap the USB cable (charge-only cables are a common culprit) or try another port.

## Asset pipeline

Pixel art and fonts are converted to C headers at dev time (no filesystem
upload needed). Requires Python 3 with Pillow (`pip3 install pillow`).

### Converting image pixels to the screen mapping

`scripts/png_to_rgb565.py` reads a PNG, composites any transparency onto black,
and emits one `uint16_t` per pixel in **RGB565** (the TFT's native 16-bit
format: 5 bits red, 6 green, 5 blue) as a `PROGMEM` C array, row-major
(left→right, top→bottom). That array is exactly what `tft.pushImage()` streams
to the panel, so the C array index maps 1:1 to screen pixels.

```
python3 scripts/png_to_rgb565.py <in.png> <out_header.h> <array_name>
```

The exact commands used to build this project's animated cake (four 128x160
expression frames):

```
python3 scripts/png_to_rgb565.py assets/cake-1.png include/cake_frame_1.h cake_frame_1
python3 scripts/png_to_rgb565.py assets/cake-2.png include/cake_frame_2.h cake_frame_2
python3 scripts/png_to_rgb565.py assets/cake-3.png include/cake_frame_3.h cake_frame_3
python3 scripts/png_to_rgb565.py assets/cake-4.png include/cake_frame_4.h cake_frame_4
```

Each header defines `<name>`, `<NAME>_W`, and `<NAME>_H`; `include/cake_frames.h`
gathers the four into the `CAKE_FRAMES[]` array the firmware animates. The PNG
**must match the display size (128x160)**.

### Converting a font

`scripts/ttf_to_gfx.py` renders a TTF to an Adafruit GFX font header (TFT_eSPI
FreeFont format, 1-bit, no anti-aliasing — suited to pixel fonts):

```
python3 scripts/ttf_to_gfx.py assets/rainyhearts.ttf include/rainyhearts_font.h 16
```

### Notes

After regenerating headers, rebuild and flash with `pio run -t upload`.

Images draw with `tft.pushImage(...)` — `tft.setSwapBytes(true)` is required
because the generated arrays are big-endian RGB565. Text draws over the image
with a transparent background (set only a foreground color).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Upload: `No serial data received` / `chip stopped responding` | Flaky auto-reset, or charge-only USB cable | Manual download mode (hold BOOT); swap cable / USB port |
| Screen totally dark, no glow | No power to VCC/BLK, or broken-middle breadboard rail | Verify VCC+BLK on 3V3 rail, GND on − rail; bridge rail gaps |
| White screen, flickers when wiggled | Loose/cold solder joint or unseated pins | Reseat / reflow the joint; push pins fully in |
| Image colors look like static/garbage | Byte order | `tft.setSwapBytes(true)` for `pushImage` |
| Pixels shifted or colors wrong on boot | Wrong ST7735 tab variant | Try `BLACKTAB` / `GREENTAB*` / `REDTAB` in `platformio.ini` |
| Red & blue swapped after mirroring | Clone flips subpixel order when MX cleared | Use MADCTL `0x80` (RGB) instead of `0x88` (BGR) |
| Buzzer plays one flat tone, not the tune | It's an **active** buzzer | Replace with a **passive** piezo (`tone()` needs passive) |
| Nothing happens on power-up | Sequence is button-triggered by design | Press BOOT or the D14 button |

## Project layout

```
src/             firmware source
include/         generated image/font headers + project headers
lib/             local libraries
assets/          source art (PNG) and fonts (TTF)
scripts/         asset conversion scripts (PNG -> RGB565, TTF -> GFX font)
data/            files for SPIFFS / LittleFS (sprites, etc.)
docs/            wiring diagrams, PCB notes
```
