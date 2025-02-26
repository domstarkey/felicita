"""Initialize the Felicita component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_MAC_ADDRESS, DOMAIN
from .coordinator import FelicitaCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["button", "sensor", "binary_sensor"]

# Add this manifest constant
PLATFORMS_PACKAGE = "custom_components.felicita"

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Felicita as config entry."""

    hass.data.setdefault(DOMAIN, {})[
        config_entry.entry_id
    ] = coordinator = FelicitaCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    # Update this line to use the package path
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry, f"{PLATFORMS_PACKAGE}.{platform}"
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    
    # Always clean up the domain data, even if unload fails
    hass.data[DOMAIN].pop(config_entry.entry_id, None)
    
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    if config_entry.version > 2:
        return False
        
    if config_entry.version == 1:
        new = {**config_entry.data}
        new[CONF_MAC] = new[CONF_MAC_ADDRESS]
        
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)
    
    return True
