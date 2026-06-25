"""Light platform for MeRGBW BLE."""

from __future__ import annotations

import logging
from typing import Any

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import control
from .const import DEFAULT_NAME, DOMAIN, WRITE_CHARACTERISTIC_UUID

_LOGGER = logging.getLogger(__name__)

# Effect name -> scene id. IDs are PROVISIONAL (reverse-engineered); the MeRGBW
# app actually uses a 2-byte scene + speed scheme. Refine with a capture that
# cycles through each named effect. See docs/protocol.md.
EFFECTS: dict[str, int] = {
    "Fantasy": 0x80,
    "Green Prairie": 0x81,
    "Forest": 0x82,
    "Sunrise": 0x83,
    "Ghost": 0x84,
    "Midsummer": 0x85,
    "Tropical Twilight": 0x86,
    "Disco": 0x87,
    "Alarm": 0x88,
    "Aurora": 0x89,
    "Savanah": 0x8B,
    "Lake Placid": 0x8C,
    "Neon": 0x8D,
    "Sundowner": 0x8E,
    "Blue Star": 0x8F,
    "Red Rose": 0x90,
    "Autumn": 0x93,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a MeRGBW light from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.title or DEFAULT_NAME
    async_add_entities([MeRGBWLight(hass, address, name)])


class MeRGBWLight(LightEntity):
    """A MeRGBW BLE light. State is optimistic (the device is write-only)."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECTS)

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialise the light."""
        self.hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None
        self._attr_unique_id = address
        self._attr_is_on = None
        self._attr_brightness = 255
        self._attr_hs_color = (0.0, 0.0)
        self._attr_effect = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, address)},
            "connections": {("bluetooth", address)},
            "name": name,
            "manufacturer": "MeRGBW",
        }

    @property
    def available(self) -> bool:
        """Available when the device is in range of a Bluetooth adapter/proxy."""
        return (
            bluetooth.async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
            is not None
        )

    async def _ensure_client(self) -> BleakClientWithServiceCache:
        """Connect (through any HA Bluetooth adapter or ESPHome proxy)."""
        if self._client and self._client.is_connected:
            return self._client
        device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if not device:
            raise RuntimeError(f"MeRGBW device {self._address} not in range")
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            self._address,
            disconnected_callback=self._on_disconnect,
        )
        return self._client

    def _on_disconnect(self, _client: Any) -> None:
        self._client = None

    async def _write(self, packet: bytes) -> None:
        client = await self._ensure_client()
        # The app uses Write Request (with response); mirror that.
        await client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, packet, response=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, applying any colour/brightness/effect."""
        await self._write(control.power(True))
        self._attr_is_on = True

        if ATTR_HS_COLOR in kwargs:
            hue, sat = kwargs[ATTR_HS_COLOR]
            await self._write(control.hs_color(hue, sat))
            self._attr_hs_color = (hue, sat)
            self._attr_effect = None

        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in EFFECTS:
            await self._write(control.scene(EFFECTS[kwargs[ATTR_EFFECT]]))
            self._attr_effect = kwargs[ATTR_EFFECT]

        if ATTR_BRIGHTNESS in kwargs:
            await self._write(control.brightness(kwargs[ATTR_BRIGHTNESS]))
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._write(control.power(False))
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect on removal."""
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
