# MeRGBW BLE protocol

Reverse-engineered from the **MeRGBW** iOS app (formerly "Magic Home" branding)
via an Apple PacketLogger capture against a "Hexagon Light" panel
(model string `TG6090`).

## Transport

* Connectable BLE (GATT). Works through ESPHome Bluetooth proxies.
* Advertised service UUID: `00003519-0000-1000-8000-00805f9b34fb` (used for
  discovery).
* Control service: `0000fff0-...`; **write** characteristic `0000fff3-...`
  (handle `0x000e` on the captured device). Commands are sent as **Write
  Request** (with response).
* Only **one** GATT connection is allowed at a time — close the MeRGBW phone
  app before using Home Assistant.

## Framing

```
0x55  <cmd>  0xFF  <total_len>  <payload...>  <checksum>
```

* `total_len` = full packet length including the 4-byte header and the
  checksum byte (`5 + len(payload)`).
* `checksum` = one's-complement of `(sum(all preceding bytes) & 0xFF)`.
  (The device appears to *ignore* the checksum, but we send the correct value.)

## Commands

| cmd  | meaning      | payload                                                       |
|------|--------------|--------------------------------------------------------------|
| 0x01 | power        | 1 byte: `00`=off, `01`=on                                     |
| 0x03 | colour       | `hue` (u16 BE, 0–360) + `saturation` (u16 BE, 0–1000)         |
| 0x05 | brightness   | u16 BE, 0–1000                                                |
| 0x06 | scene/effect | **u16 BE scene id** (`00 <id>`); app follows it with 0x0F     |
| 0x0F | scene speed  | `<speed> 00` (speed 0–100)                                    |
| 0x07 | music mode   | 1 byte mode id                                                |
| 0x08 | music sens.  | 1 byte, 0–100                                                 |

### Scenes / effects (verified 2026-06-26 capture)
The device exposes **~109 raw scene patterns** (ids 1–117, gaps at 76–83). The
app's "Scenes" and "Festival" tabs are **friendly aliases** over a subset of
those ids (some ids reused under multiple names, e.g. id 3 = Energy = Candlelight).
A scene is selected as `0x06 00<id>` immediately followed by `0x0F <speed> 00`.

Music: `0x07` selects a reactive mode (Spectrum 1/2/3 = 2/5/6, Flowing=3,
Rolling=1, Rhythm=4); `0x08` sets sensitivity 0–100.

Note: the app's brightness "0%" actually sends `100`/1000 (~10%, its floor);
this integration maps HA 0–255 → 0–1000 directly, so 0 is genuinely dimmer.

### Worked examples (verbatim from the capture)

| bytes                       | meaning                                  |
|-----------------------------|------------------------------------------|
| `55 03 ff 09 0000 03e8 b4`  | colour hue 0° (red), sat 1000            |
| `55 03 ff 09 0078 03e8 3c`  | colour hue 120° (green), sat 1000        |
| `55 03 ff 09 00f0 03e8 c4`  | colour hue 240° (blue), sat 1000         |
| `55 05 ff 07 03e8 b4`       | brightness 1000 (100%)                   |
| `55 05 ff 07 020e 8f`       | brightness 526 (~50%)                    |
| `55 05 ff 07 0080 1f`       | brightness 128 (~13%)                    |
| `55 01 ff 06 00 a4`         | power off                                |
| `55 01 ff 06 01 a3`         | power on                                 |

## Why a generic RGB integration fails

The device's colour command is **HSV**, not RGB. Sending three raw RGB bytes
lands a near-zero saturation → washed-out white. Brightness is a **16-bit
0–1000** value; sending a single 0–255 byte is ignored.

## Open items

* **Effect names mapped** for the curated Scenes + Festival tabs (see
  `light.py SCENE_EFFECTS`). The raw 109 "Other" patterns are reachable by id
  via the `set_scene_id` service rather than cluttering the dropdown.
* The app has a **"DIY"** custom-pattern option not yet captured — a future
  sniff could expose overriding device defaults.
* White / colour-temperature command (if any) is not yet captured.
