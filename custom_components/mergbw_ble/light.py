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
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import voluptuous as vol

from . import control
from .const import DEFAULT_NAME, DOMAIN, WRITE_CHARACTERISTIC_UUID

_LOGGER = logging.getLogger(__name__)

# Default scene animation speed (0-100) sent after selecting a scene.
DEFAULT_SCENE_SPEED = 50

# Curated scene effects (the app's "Scenes" + "Festival" tabs) -> scene id.
# Verified from a PacketLogger capture (see docs/protocol.md). These are
# friendly aliases over the device's ~109 raw patterns; the full raw set is
# reachable via the `set_scene_id` service (1-117) to avoid a 140-item dropdown.
SCENE_EFFECTS: dict[str, int] = {
    # Scenes
    "Symphony": 2, "Energy": 3, "Jump": 4, "Vitality": 7, "Accumulation": 16,
    "Chase": 23, "Space-time": 45, "Ephemeral": 35, "Flow": 55, "Forest": 13,
    "Neon Lights": 48, "Green Jade": 71, "Running": 91, "Pink Light": 109,
    "Alarm": 113, "Aurora": 59, "Rainbow": 26, "Melody": 32,
    # Festival
    "Christmas": 8, "Halloween": 11, "Valentines Day": 5, "New Year": 116,
    "Candlelight": 3, "Birthday": 111, "Ghost": 6, "Party": 8, "Carnival": 4,
    "Disco": 102, "Sweet": 12, "Romantic": 11, "Dating": 29, "Ball": 26,
    "Game": 1,
}

# Music-reactive modes (cmd 0x07).
MUSIC_EFFECTS: dict[str, int] = {
    "Music Spectrum 1": 2, "Music Spectrum 2": 5, "Music Spectrum 3": 6,
    "Flowing": 3, "Rolling": 1, "Rhythm": 4,
}

EFFECT_LIST = list(SCENE_EFFECTS) + list(MUSIC_EFFECTS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a MeRGBW light from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.title or DEFAULT_NAME
    async_add_entities([MeRGBWLight(hass, address, name)])

    # Services for the raw scenes (the ~109 "Other" patterns) + music sensitivity.
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_scene_id",
        {
            vol.Required("scene_id"): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
            vol.Optional("speed", default=DEFAULT_SCENE_SPEED): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        },
        "async_set_scene_id",
    )
    platform.async_register_entity_service(
        "set_music_sensitivity",
        {vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))},
        "async_set_music_sensitivity",
    )


class MeRGBWLight(LightEntity):
    """A MeRGBW BLE light. State is optimistic (the device is write-only)."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECT_LIST

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

        if ATTR_EFFECT in kwargs:
            eff = kwargs[ATTR_EFFECT]
            if eff in SCENE_EFFECTS:
                await self._write(control.scene(SCENE_EFFECTS[eff]))
                await self._write(control.scene_speed(DEFAULT_SCENE_SPEED))
                self._attr_effect = eff
            elif eff in MUSIC_EFFECTS:
                await self._write(control.music_mode(MUSIC_EFFECTS[eff]))
                self._attr_effect = eff

        if ATTR_BRIGHTNESS in kwargs:
            await self._write(control.brightness(kwargs[ATTR_BRIGHTNESS]))
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._write(control.power(False))
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_scene_id(
        self, scene_id: int, speed: int = DEFAULT_SCENE_SPEED
    ) -> None:
        """Fire any raw scene id (1-117) — the full 'Other' pattern set."""
        await self._write(control.power(True))
        await self._write(control.scene(scene_id))
        await self._write(control.scene_speed(speed))
        self._attr_is_on = True
        self._attr_effect = None  # not a named effect
        self.async_write_ha_state()

    async def async_set_music_sensitivity(self, level: int) -> None:
        """Set music-reactive sensitivity (0-100)."""
        await self._write(control.music_sensitivity(level))

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect on removal."""
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
