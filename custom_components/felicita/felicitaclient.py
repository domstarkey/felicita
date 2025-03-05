import asyncio
import logging
from time import time
from typing import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_address_present,
    async_register_callback,
    BluetoothScanningMode
)
from homeassistant.const import CONF_MAC
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    MIN_BATTERY_LEVEL,
    MAX_BATTERY_LEVEL,
)

FELICITA_SERVICE_UUID = "FFE0"
FELICITA_CHAR_UUID = "FFE1"

CMD_START_TIMER = 0x52
CMD_STOP_TIMER = 0x53
CMD_RESET_TIMER = 0x43
CMD_TARE = 0x54
CMD_TOGGLE_UNIT = 0x55

_LOGGER = logging.getLogger(__name__)
CONNECT_TIMEOUT = 10
MAX_RETRIES = 3


class FelicitaClient:
    """Client for Felicita scale."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, notify_callback: Callable) -> None:
        """Initialize client."""
        self._hass = hass
        self._entry = entry
        self._notify_callback = notify_callback
        self._client: BleakClient | None = None
        self._device: BLEDevice | None = None
        self._weight: float = 0
        self._battery: int = 0
        self._unit: str = "g"
        self._is_connected: bool = False
        self._mac = entry.data[CONF_MAC]
        self._last_weight: float = 0
        self._last_weight_time: float = 0
        self._flow_rate: float = 0
        self._ema_alpha = 0.1  # Smoothing factor for EMA
        self._connection_lock = asyncio.Lock()
        self._disconnect_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._connecting: bool = False  # Prevent duplicate attempts

        _LOGGER.debug("Registering BLE device detection callback for MAC: %s", self._mac)
        async_register_callback(
            hass,
            self._device_detected,
            {"address": self._mac},
            BluetoothScanningMode.PASSIVE
        )

    @property
    def weight(self) -> float:
        """Return current weight."""
        return self._weight

    @property
    def battery(self) -> int:
        """Return battery level."""
        return self._battery

    @property
    def unit(self) -> str:
        """Return weight unit."""
        return self._unit

    @property
    def is_connected(self) -> bool:
        """Return connection state."""
        return self._is_connected

    @property
    def mac(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._entry.data.get("name", "Felicita Scale")

    @property
    def flow_rate(self) -> float:
        """Return current flow rate in g/s."""
        return self._flow_rate

    async def async_run(self) -> None:
        """Maintain a persistent connection until stopped."""
        while not self._stop_event.is_set():
            await self.async_connect()
            # Remain connected until a disconnect occurs
            await self._disconnect_event.wait()
            _LOGGER.debug("Disconnected; will attempt to reconnect shortly.")
            self._disconnect_event.clear()
            self._is_connected = False
            await asyncio.sleep(1)  # Brief pause before reconnecting

    async def async_stop(self) -> None:
        """Stop the persistent connection loop and disconnect."""
        self._stop_event.set()
        await self.async_disconnect()

    async def async_connect(self) -> None:
        """Attempt connection with retries."""
        async with self._connection_lock:
            if self._is_connected or self._connecting:
                return
            self._connecting = True

        retries = 0
        while retries < MAX_RETRIES and not self._is_connected:
            try:
                # Wait for device discovery
                device = None
                for _ in range(5):
                    device = async_ble_device_from_address(self._hass, self._mac)
                    if device:
                        break
                    await asyncio.sleep(1)
                if not device:
                    raise Exception(f"Device {self._mac} not found")

                self._device = device

                # Disconnect any previous client
                if self._client:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass

                _LOGGER.debug("Attempting to connect to device %s", self._mac)
                client = BleakClient(device, disconnected_callback=self._disconnected_callback, timeout=CONNECT_TIMEOUT)
                await client.connect()
                self._client = client

                # Start notifications to receive data from the scale
                await client.start_notify(FELICITA_CHAR_UUID, self._notification_callback)
                self._is_connected = True
                _LOGGER.debug("Successfully connected to device %s", self._mac)
            except Exception as error:
                retries += 1
                _LOGGER.warning("Connection attempt %s failed: %s", retries, str(error))
                await asyncio.sleep(2 ** retries)

        async with self._connection_lock:
            self._connecting = False

    def _device_detected(self, device, advertisement_data) -> None:
        """Handle device detection and initiate connection if not active."""
        if not self._is_connected and not self._connecting and device.address == self._mac:
            _LOGGER.debug("Device %s detected! Initiating connection...", self._mac)
            self._hass.async_create_task(self.async_connect())

    def _disconnected_callback(self, _: BleakClient) -> None:
        """Handle disconnection."""
        _LOGGER.debug("Device %s disconnected.", self._mac)
        self._is_connected = False
        self._client = None
        # Signal the run loop that a disconnect occurred.
        self._disconnect_event.set()
        self._notify_callback()

    def _notification_callback(self, _: int, data: bytearray) -> None:
        """Process notifications from the scale."""
        try:
            if len(data) != 18:
                _LOGGER.info("Received invalid data length: %s", len(data))
                return

            # Parse weight from bytes 3-9.
            try:
                raw_weight = data[3:9].decode("utf-8").strip()
                if not raw_weight:
                    raise ValueError("Empty weight data")
                sign = -1 if raw_weight[0] == "-" else 1
                weight_digits = raw_weight[1:] if sign == -1 else raw_weight
                if len(weight_digits) < 3:
                    raise ValueError("Insufficient digits in weight data")
                weight_str = weight_digits[:-2] + "." + weight_digits[-2:]
                self._weight = sign * float(weight_str)
            except Exception as e:
                _LOGGER.warning("Failed to parse weight: %s", e)
                return

            # Parse battery (byte 15) with bounds checking.
            battery_raw = data[15]
            battery_percentage = ((battery_raw - MIN_BATTERY_LEVEL) / 
                                  (MAX_BATTERY_LEVEL - MIN_BATTERY_LEVEL)) * 100
            if abs(battery_percentage - self._battery) > 5:
                self._battery = max(0, min(100, round(battery_percentage)))

            # Parse unit from bytes 9-11.
            try:
                unit = data[9:11].decode("utf-8").strip()
                if unit in ["g", "oz"]:
                    self._unit = unit
            except UnicodeDecodeError as e:
                _LOGGER.warning("Failed to decode unit: %s", e)

            # Calculate flow rate (g/s).
            current_time = time()
            if self._last_weight_time > 0:
                time_diff = current_time - self._last_weight_time
                weight_diff = self._weight - self._last_weight
                if time_diff > 0:
                    new_flow_rate = weight_diff / time_diff
                    self._flow_rate = round(
                        self._ema_alpha * new_flow_rate + (1 - self._ema_alpha) * self._flow_rate,
                        1
                    )
            self._last_weight = self._weight
            self._last_weight_time = current_time

            self._notify_callback()
        except Exception as e:
            _LOGGER.error("Error processing notification: %s", e)

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._connection_lock:
            if self._client:
                await self._client.disconnect()
            self._is_connected = False
            self._client = None

    async def async_update(self) -> None:
        """Periodically check if the device is still available."""
        device_available = async_address_present(self._hass, self._mac, connectable=True)
        if not device_available:
            self._is_connected = False
            _LOGGER.debug("Device with MAC %s not available", self._mac)
            self._notify_callback()

    async def async_tare(self) -> None:
        """Tare the scale."""
        if self._client and self._is_connected:
            await self._client.write_gatt_char(FELICITA_CHAR_UUID, bytes([CMD_TARE]))

    async def async_start_timer(self) -> None:
        """Start the timer."""
        if self._client and self._is_connected:
            await self._client.write_gatt_char(FELICITA_CHAR_UUID, bytes([CMD_START_TIMER]))

    async def async_stop_timer(self) -> None:
        """Stop the timer."""
        if self._client and self._is_connected:
            await self._client.write_gatt_char(FELICITA_CHAR_UUID, bytes([CMD_STOP_TIMER]))

    async def async_reset_timer(self) -> None:
        """Reset the timer."""
        if self._client and self._is_connected:
            await self._client.write_gatt_char(FELICITA_CHAR_UUID, bytes([CMD_RESET_TIMER]))

    async def async_toggle_unit(self) -> None:
        """Toggle between grams and ounces."""
        if self._client and self._is_connected:
            await self._client.write_gatt_char(FELICITA_CHAR_UUID, bytes([CMD_TOGGLE_UNIT]))
