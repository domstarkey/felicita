"""Coordinator for Felicita integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .felicitaclient import FelicitaClient

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

class FelicitaCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the Felicita scale."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Felicita scale coordinator",
            update_interval=None,  # Disable periodic updates
        )

        self._felicita_client: FelicitaClient = FelicitaClient(
            hass=hass,
            entry=config_entry,
            notify_callback=self.async_update_listeners,
        )
        self.data = self._felicita_client

    async def _async_update_data(self) -> FelicitaClient:
        """Fetch data."""
        # This method can be simplified or removed if not needed
        try:
            await self._felicita_client.async_update()
        except Exception as ex:
            raise UpdateFailed(f"Error: {ex}") from ex

        return self._felicita_client 