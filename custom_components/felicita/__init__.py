"""Initialize the Felicita component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import FelicitaCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["button", "sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Felicita as config entry."""
    
    # Remove existing instance if already exists (prevents multiple instances on reload)
    if config_entry.entry_id in hass.data.get(DOMAIN, {}):
        await async_unload_entry(hass, config_entry)

    coordinator = FelicitaCoordinator(hass, config_entry)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register a reload service
    async def reload_service(call):
        """Reload the integration."""
        await async_unload_entry(hass, config_entry)
        await async_setup_entry(hass, config_entry)

    if not hass.services.has_service(DOMAIN, "reload"):
        hass.services.async_register(DOMAIN, "reload", reload_service)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    # Properly unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unload_ok:
        # Ensure the coordinator is properly removed
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
    
    return unload_ok
