"""Select entity to choose which stream profile is shown live."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisCoordinator
from .const import DOMAIN, OPT_ACTIVE_PROFILE, OWNED_PROFILE_NAME
from .entity import AxisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the stream profile selector."""
    coordinator: AxisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AxisStreamProfileSelect(coordinator, entry)])


class AxisStreamProfileSelect(AxisEntity, SelectEntity):
    """Lets the user pick any stream profile the camera offers."""

    _attr_translation_key = "stream_profile"
    _attr_icon = "mdi:video-switch"

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_unique_id}_stream_profile"

    @property
    def options(self) -> list[str]:
        """All profile names read from the camera."""
        if self.coordinator.data is None:
            return [OWNED_PROFILE_NAME]
        names = [profile.name for profile in self.coordinator.data.profiles]
        return names or [OWNED_PROFILE_NAME]

    @property
    def current_option(self) -> str | None:
        """The profile currently used for the live view."""
        selected = self._entry.options.get(OPT_ACTIVE_PROFILE, OWNED_PROFILE_NAME)
        return selected if selected in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Store the choice. Nothing is written to the camera."""
        if option not in self.options:
            raise ValueError(f"Unknown stream profile: {option}")
        new_options = dict(self._entry.options)
        new_options[OPT_ACTIVE_PROFILE] = option
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
