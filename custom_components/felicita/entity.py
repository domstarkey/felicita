"""Base class for the La Marzocco entities."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .felicitaclient import FelicitaClient
from .const import DOMAIN


@dataclass
class FelicitaEntityDescriptionMixin:
    """Mixin for all LM entities."""

    unique_id_fn: Callable[[FelicitaClient], str]


@dataclass
class FelicitaEntityDescription(EntityDescription, FelicitaEntityDescriptionMixin):
    """Description for all LM entities."""


@dataclass
class FelicitaEntity(CoordinatorEntity):
    """Common elements for all entities."""

    entity_description: FelicitaEntityDescription

    def __init__(self, coordinator, entity_description) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._scale: FelicitaClient = coordinator.data
        self._attr_has_entity_name = True
        self._attr_unique_id = entity_description.unique_id_fn(self._scale)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._scale.mac)},
            name=self._scale.name,
            manufacturer="felicita",
        )
