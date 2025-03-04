import asyncio
import logging
from time import time
from typing import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_address_present,
    async_register_callback,
    BluetoothScanningMode
)
from homeassistant.const import CONF_MAC
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

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
        self._mac = entry.data[CONF_MAC]
        self._last_weight: float = 0
        self._last_weight_time: float = 0
        self._flow_rate: float = 0
        self._ema_alpha = 0.1  # Smoothing factor for EMA (lower = smoother)
        self._connection_lock = asyncio.Lock()  # Add connection lock
        self._disconnect_event = asyncio.Event()  # Add disconnect event

        # Register BLE device detection callback without immediate connection attempt
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

    async def async_connect(self) -> None:
        """Connect to the scale with retry mechanism."""
        async with self._connection_lock:  # Ensure only one connection attempt at a time
            if self._is_connected:
                return

            while self._connect_retries < MAX_RETRIES:
                try:
                    # Clear any previous disconnect event
                    self._disconnect_event.clear()
                    
                    device = async_ble_device_from_address(self._hass, self._mac)
                    if not device:
                        self._is_connected = False
                        _LOGGER.error("Could not find device with address %s", self._mac)
                        return  # Early return if device not found

                    self._device = device
                    
                    # Disconnect any existing client
                    if self._client:
                        try:
                            await self._client.disconnect()
                        except Exception:
                            pass
                    
                    async with BleakClient(
                        device, 
                        disconnected_callback=self._disconnected_callback,
                        timeout=CONNECT_TIMEOUT
                    ) as client:
                        self._client = client

                        # Verify services are available
                        #if not client.services:
                            #raise BleakError("Failed to retrieve services from the device")

                        #services = client.services
                        #if not any(service.uuid.startswith(FELICITA_SERVICE_UUID) for service in services):
                            #raise BleakError("Felicita service not found")

                        # Start notifications only after successful connection and service discovery
                        await client.start_notify(
                            FELICITA_CHAR_UUID, self._notification_callback
                        )

                        self._is_connected = True
                        self._connect_retries = 0  # Reset counter on successful connection
                        _LOGGER.debug("Successfully connected to device %s", self._mac)
                        return  # Early return after successful connection

                except Exception as error:
                    _LOGGER.warning(
                        "Connection attempt %s failed: %s", 
                        self._connect_retries + 1, 
                        str(error)
                    )
                    if self._client:
                        try:
                            await self._client.disconnect()
                        except Exception:
                            pass
                    self._client = None
                    self._is_connected = False
                    self._connect_retries += 1
                    
                    if self._connect_retries >= MAX_RETRIES:
                        _LOGGER.error("Failed to connect after %s attempts", MAX_RETRIES)
                        return
                    
                    # Exponential backoff between retries
                    await asyncio.sleep(2 ** self._connect_retries)

    def _device_detected(self, device, advertisement_data):
        """Handle device detection and initiate connection."""
        if not self._is_connected and device.address == self._mac:
            _LOGGER.debug("Device %s detected! Connecting...", self._mac)
            asyncio.create_task(self.async_connect())

    def _disconnected_callback(self, _: BleakClient) -> None:
        """Handle disconnection."""
        self._is_connected = False
        self._client = None
        self._connect_retries = 0
        self._disconnect_event.set()
        self._notify_callback()

    def _notification_callback(self, _: int, data: bytearray) -> None:
        """Handle notification from scale."""
        try:
            if len(data) != 18:
                _LOGGER.info("Received invalid data length: %s", len(data))
                return

            # Parse weight - bytes 3-9 contain weight digits
            weight_bytes = data[3:9]
            try:
                # Convert ASCII values to actual digits (ASCII 48 = '0')
                digits = [b - 48 for b in weight_bytes]
                # Join all digits and convert to float, moving decimal point 2 places from right
                weight_str = ''.join(str(d) for d in digits[:-2]) + '.' + ''.join(str(d) for d in digits[-2:])
                self._weight = float(weight_str)
                
                # If the first digit is negative (after subtracting 48), 
                # this indicates a negative value from the scale
                if digits[0] < 0:
                    self._weight = -self._weight
                    
            except ValueError as e:
                _LOGGER.warning("Failed to parse weight: %s", e)
                return

            # Parse battery with bounds checking
            battery_raw = data[15]
            battery_percentage = ((battery_raw - MIN_BATTERY_LEVEL) / 
                                (MAX_BATTERY_LEVEL - MIN_BATTERY_LEVEL)) * 100
            if abs(battery_percentage - self._battery) > 5:  # Only update if change is significant
                self._battery = max(0, min(100, round(battery_percentage)))

            # Parse unit (bytes 9-11)
            try:
                unit = data[9:11].decode('utf-8').strip()
                if unit in ['g', 'oz']:  # Add valid units here
                    self._unit = unit
            except UnicodeDecodeError as e:
                _LOGGER.warning("Failed to decode unit: %s", e)

            # Calculate flow rate (g/s)
            current_time = time()
            if self._last_weight_time > 0:
                time_diff = current_time - self._last_weight_time
                weight_diff = self._weight - self._last_weight
                if time_diff > 0:
                    # Calculate new flow rate with exponential moving average
                    new_flow_rate = weight_diff / time_diff
                    self._flow_rate = round(
                        (self._ema_alpha * new_flow_rate + 
                         (1 - self._ema_alpha) * self._flow_rate),
                        1  # Round to 1 decimal place
                    )
            
            self._last_weight = self._weight
            self._last_weight_time = current_time

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
        # Only check if device is present, don't force connection
        device_available = async_address_present(
            self._hass, self._mac, connectable=True
        )
        
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
