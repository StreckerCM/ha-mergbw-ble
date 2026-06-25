# MeRGBW BLE — Home Assistant integration

Control **MeRGBW** Bluetooth LED devices (the app formerly branded "Magic
Home") from Home Assistant. Built and verified against a "Hexagon Light" panel
(`TG6090`), but should work with other MeRGBW BLE lights that speak the same
protocol.

> This is the **Bluetooth** family. The built-in [Magic Home / `flux_led`]
> integration is for the **Wi-Fi** Zengge controllers and will not control
> these.

## Features

- On / off
- **Colour** via HS (the device is natively HSV — accurate colours, unlike
  generic RGB integrations)
- **Brightness** (16-bit 0–1000 scale, mapped from HA's 0–255)
- Effects / scenes (names are **provisional** — see
  [`docs/protocol.md`](docs/protocol.md))
- **Bluetooth auto-discovery** — no MAC typing required
- Works through **ESPHome Bluetooth proxies**

## Requirements

- Home Assistant 2024.4 or newer
- A Bluetooth adapter or an ESPHome Bluetooth proxy in range of the light

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/StreckerCM/ha-mergbw-ble`, category **Integration**
3. Download **MeRGBW BLE**, then **restart Home Assistant**

Or copy `custom_components/mergbw_ble/` into your HA `config/custom_components/`
and restart.

## Setup

1. **Close the MeRGBW phone app** (the light allows only one connection at a
   time).
2. Home Assistant should **auto-discover** the light (Settings → Devices &
   Services → "Discovered"). If not, add **MeRGBW BLE** manually and pick the
   device / enter its Bluetooth address.

## Status / limitations

- State is **optimistic** — the device is write-only, so HA doesn't read back
  on/off, colour, or brightness.
- **Effect names are approximate.** Contributions welcome — see
  [`docs/protocol.md`](docs/protocol.md) for how to capture and map them.

## Protocol

The BLE protocol was reverse-engineered from a PacketLogger capture and is
documented in [`docs/protocol.md`](docs/protocol.md).

## Credits

Inspired by King1704G's
[sunset_light integration](https://github.com/King1704G/custom_components-sunset_light_cheapass_amazon_light),
which provided the original framing hints. The HSV colour / 0–1000 brightness
protocol, checksum, HS colour mode, and Bluetooth discovery here were
independently reverse-engineered and rewritten.

## License

[MIT](LICENSE)
