"""Binary sensor platform for Felicita scales."""
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .felicitaclient import FelicitaClient
from .const import DOMAIN
from .entity import FelicitaEntity, FelicitaEntityDescription


@dataclass
class FelicitaBinarySensorEntityDescriptionMixin:
    """Mixin for Felicita Binary Sensor entities."""

    is_on_fn: Callable[[FelicitaClient], bool]


@dataclass
class FelicitaBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    FelicitaEntityDescription,
    FelicitaBinarySensorEntityDescriptionMixin,
):
    """Description for Felicita Binary Sensor entities."""


BINARY_SENSORS: tuple[FelicitaBinarySensorEntityDescription, ...] = (
    # FelicitaBinarySensorEntityDescription(
    #     key="timer_running",
    #     translation_key="timer_running",
    #     device_class=BinarySensorDeviceClass.RUNNING,
    #     icon="mdi:timer",
    #     unique_id_fn=lambda scale: f"{scale.mac}_timer_running",
    #     is_on_fn=lambda scale: scale.timer_running,
    # ),
    FelicitaBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:bluetooth",
        unique_id_fn=lambda scale: f"{scale.mac}_connected",
        is_on_fn=lambda scale: scale.is_connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [FelicitaSensor(coordinator, description) for description in BINARY_SENSORS]
    )


class FelicitaSensor(FelicitaEntity, BinarySensorEntity):
    """Representation of a Felicita Binary Sensor."""

    entity_description: FelicitaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._scale)