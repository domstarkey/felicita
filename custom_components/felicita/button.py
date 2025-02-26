"""Button platform for Felicita integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FelicitaCoordinator
from .entity import FelicitaEntity


@dataclass
class FelicitaButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable


@dataclass
class FelicitaButtonDescription(ButtonEntityDescription, FelicitaButtonDescriptionMixin):
    """Class describing Felicita button entities."""


BUTTONS = [
    FelicitaButtonDescription(
        key="tare",
        name="Tare",
        press_action=lambda client: client.async_tare(),
    ),
    FelicitaButtonDescription(
        key="start_timer",
        name="Start Timer",
        press_action=lambda client: client.async_start_timer(),
    ),
    FelicitaButtonDescription(
        key="stop_timer",
        name="Stop Timer",
        press_action=lambda client: client.async_stop_timer(),
    ),
    FelicitaButtonDescription(
        key="reset_timer",
        name="Reset Timer",
        press_action=lambda client: client.async_reset_timer(),
    ),
    FelicitaButtonDescription(
        key="toggle_unit",
        name="Toggle Unit",
        press_action=lambda client: client.async_toggle_unit(),
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Felicita buttons."""
    coordinator: FelicitaCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FelicitaButton(coordinator, description) for description in BUTTONS
    )


class FelicitaButton(FelicitaEntity, ButtonEntity):
    """Representation of a Felicita button."""

    entity_description: FelicitaButtonDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_action(self.coordinator.data) 