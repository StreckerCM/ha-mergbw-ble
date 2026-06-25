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

| cmd  | meaning     | payload                                                        |
|------|-------------|---------------------------------------------------------------|
| 0x01 | power       | 1 byte: `00`=off, `01`=on                                      |
| 0x03 | colour      | `hue` (u16 BE, 0–360) + `saturation` (u16 BE, 0–1000)          |
| 0x05 | brightness  | u16 BE, 0–1000                                                 |
| 0x06 | scene/effect| 1 byte scene id (app uses 2 bytes — see "Open items")          |
| 0x0F | effect speed| u16 (seen alongside 0x06 in captures)                          |

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

* **Effect mapping is provisional.** The app selects effects with a 2-byte
  `0x06` id plus a `0x0F` speed value (captured ids `0x3b`, `0x71`), not the
  `0x80`-range single bytes currently mapped in `light.py`. Capture the app
  cycling through each *named* effect to map them precisely.
* White / colour-temperature command (if any) is not yet captured.
