"""Constants for the MeRGBW BLE integration."""

DOMAIN = "mergbw_ble"

# Characteristic the device accepts commands on. On the Hexagon Light this
# resolves to handle 0x000e (verified via PacketLogger capture).
WRITE_CHARACTERISTIC_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

# GATT control service exposed after connecting.
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"

# Service UUID the device *advertises* (used for Bluetooth auto-discovery).
ADVERTISED_SERVICE_UUID = "00003519-0000-1000-8000-00805f9b34fb"

DEFAULT_NAME = "MeRGBW Light"
