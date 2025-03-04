"""Initialize the Felicita component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.const import SERVICE_RELOAD

from .const import DOMAIN
from .coordinator import FelicitaCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["button", "sensor", "binary_sensor"]


async def _reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Felicita as config entry."""
    hass.data.setdefault(DOMAIN, {})[
        config_entry.entry_id
    ] = coordinator = FelicitaCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    # Load platforms using async_forward_entry_setups instead of individual tasks
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register reload service
    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_RELOAD,
        lambda _: _reload_entry(hass, config_entry)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms without the package path
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    
    return unload_ok

