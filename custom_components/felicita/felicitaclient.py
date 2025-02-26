"""Client for Felicita scales."""
from typing import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
)
from homeassistant.const import CONF_MAC
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from asyncio import TimeoutError
import logging

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

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, notify_callback: Callable
    ) -> None:
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
        self._connect_retries = 0

        super().__init__(
            mac=entry.data[CONF_MAC],
            notify_callback=notify_callback,
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

    async def async_connect(self) -> None:
        """Connect to the scale with retry mechanism."""
        while self._connect_retries < MAX_RETRIES:
            try:
                device = async_ble_device_from_address(self._hass, self._mac)
                if not device:
                    raise ConfigEntryNotReady(f"Could not find device with address {self._mac}")

                self._device = device
                self._client = BleakClient(
                    device, 
                    disconnected_callback=self._disconnected_callback,
                    timeout=CONNECT_TIMEOUT
                )

                await self._client.connect()
                self._is_connected = True
                await self._client.start_notify(
                    FELICITA_CHAR_UUID, self._notification_callback
                )
                self._connect_retries = 0  # Reset counter on successful connection
                return
            except (BleakError, TimeoutError) as error:
                self._connect_retries += 1
                if self._connect_retries >= MAX_RETRIES:
                    self._is_connected = False
                    raise ConfigEntryNotReady(f"Failed to connect after {MAX_RETRIES} attempts: {error}")
                _LOGGER.warning("Connection attempt %s failed, retrying...", self._connect_retries)

    def _disconnected_callback(self, _: BleakClient) -> None:
        """Handle disconnection."""
        self._is_connected = False
        self._notify_callback()

    def _notification_callback(self, _: int, data: bytearray) -> None:
        """Handle notification from scale."""
        try:
            if len(data) != 18:
                _LOGGER.warning("Received invalid data length: %s", len(data))
                return

            # Parse weight - bytes 3-9 contain weight digits
            weight_bytes = data[3:9]
            try:
                self._weight = float(''.join([str(b - 48) for b in weight_bytes])) / 100
            except ValueError as e:
                _LOGGER.warning("Failed to parse weight: %s", e)
                return

            # Parse battery with bounds checking
            battery_raw = data[15]
            battery_percentage = ((battery_raw - MIN_BATTERY_LEVEL) / 
                                (MAX_BATTERY_LEVEL - MIN_BATTERY_LEVEL)) * 100
            self._battery = max(0, min(100, round(battery_percentage)))

            # Parse unit with validation
            try:
                unit = data[9:11].decode('utf-8').strip()
                if unit in ['g', 'oz']:  # Add valid units here
                    self._unit = unit
            except UnicodeDecodeError as e:
                _LOGGER.warning("Failed to decode unit: %s", e)

            self._notify_callback()
        except Exception as e:
            _LOGGER.error("Error processing notification: %s", e)

    async def async_disconnect(self) -> None:
        """Disconnect from device."""
        if self._client:
            await self._client.disconnect()
        self._is_connected = False

    async def async_update(self) -> None:
        """Update data from device."""
        if not self._is_connected:
            await self.async_connect()

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
