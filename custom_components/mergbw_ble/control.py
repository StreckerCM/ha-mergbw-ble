"""Command builder for MeRGBW BLE devices.

Protocol reverse-engineered from the MeRGBW iOS app via a PacketLogger capture
(see ``docs/protocol.md``).

Framing::

    0x55 <cmd> 0xFF <total_len> <payload...> <checksum>

* ``total_len`` = full packet length incl. header + checksum (``5 + len(payload)``)
* ``checksum``  = one's-complement of ``(sum(all preceding bytes) & 0xFF)``

Commands::

    0x01 power        payload: 1 byte    00=off 01=on
    0x03 color        payload: hue(u16 BE, 0-360) + saturation(u16 BE, 0-1000)
    0x05 brightness   payload: u16 BE, 0-1000
    0x06 scene        payload: 1 byte scene id
"""

from __future__ import annotations

import colorsys

CMD_HEAD = 0x55
CMD_SEQUENCE = 0xFF

CMD_POWER = 0x01
CMD_COLOR = 0x03
CMD_BRIGHTNESS = 0x05
CMD_SCENE = 0x06


def build_packet(cmd: int, payload: bytes = b"") -> bytes:
    """Assemble a framed packet with the device's checksum."""
    total_len = 5 + len(payload)
    data = bytearray([CMD_HEAD, cmd, CMD_SEQUENCE, total_len]) + payload
    checksum = (~(sum(data) & 0xFF)) & 0xFF
    return bytes(data) + bytes([checksum])


def power(on: bool) -> bytes:
    """Power on/off."""
    return build_packet(CMD_POWER, bytes([0x01 if on else 0x00]))


def hs_color(hue: float, sat: float) -> bytes:
    """Set colour from HA HS values (hue 0-360, saturation 0-100)."""
    h = int(round(hue)) % 360
    s = max(0, min(1000, int(round(sat * 10))))  # 0-100 -> 0-1000
    return build_packet(CMD_COLOR, h.to_bytes(2, "big") + s.to_bytes(2, "big"))


def rgb_color(r: int, g: int, b: int) -> bytes:
    """Convenience: set colour from RGB (converted to the device's HSV)."""
    hh, ss, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return hs_color(hh * 360.0, ss * 100.0)


def brightness(value: int) -> bytes:
    """Set brightness from HA scale (0-255) -> device scale (0-1000)."""
    level = max(0, min(1000, int(round(value / 255.0 * 1000.0))))
    return build_packet(CMD_BRIGHTNESS, level.to_bytes(2, "big"))


def white() -> bytes:
    """Set white (saturation 0)."""
    return build_packet(CMD_COLOR, (0).to_bytes(2, "big") + (0).to_bytes(2, "big"))


def scene(scene_id: int) -> bytes:
    """Select a built-in scene/effect by id."""
    return build_packet(CMD_SCENE, bytes([scene_id & 0xFF]))
