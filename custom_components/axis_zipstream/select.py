"""Select entities for Axis Zipstream."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisCoordinator
from .const import (
    DEFAULT_RESOLUTION,
    DOMAIN,
    OPT_ACTIVE_PROFILE,
    OPT_RESOLUTION,
    OPT_ZFPSMODE,
    OPT_ZGOPMODE,
    OPT_ZSTRENGTH,
    OWNED_PROFILE_NAME,
    ZFPS_MODES,
    ZGOP_MODES,
    ZSTRENGTH_FALLBACK,
)
from .entity import AxisEntity, AxisProfileOptionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select entities."""
    coordinator: AxisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AxisStreamProfileSelect(coordinator, entry),
            AxisResolutionSelect(coordinator, entry),
            AxisZipstreamStrengthSelect(coordinator, entry),
            AxisFpsModeSelect(coordinator, entry),
            AxisGopModeSelect(coordinator, entry),
        ]
    )


class AxisStreamProfileSelect(AxisEntity, SelectEntity):
    """Picks which stream profile the live view uses."""

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


class _ProfileSelect(AxisProfileOptionEntity, SelectEntity):
    """Shared behaviour for selects that write into the owned profile."""

    _default: str = ""

    def __init__(
        self, coordinator: AxisCoordinator, entry: ConfigEntry, suffix: str
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_unique_id}_{suffix}"

    @property
    def current_option(self) -> str | None:
        """Current value, falling back to the default."""
        value = str(self._entry.options.get(self._option_key, self._default))
        return value if value in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Write the new value into the owned profile."""
        if option not in self.options:
            raise ValueError(f"Unsupported value: {option}")
        await self._async_store_option(option)


class AxisResolutionSelect(_ProfileSelect):
    """Stream resolution, limited to what the camera reports as supported."""

    _attr_translation_key = "resolution"
    _attr_icon = "mdi:aspect-ratio"
    _option_key = OPT_RESOLUTION
    _default = DEFAULT_RESOLUTION

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry, "resolution")

    @property
    def options(self) -> list[str]:
        """Resolutions read from Properties.Image.Resolution."""
        if self.coordinator.data and self.coordinator.data.resolutions:
            return self.coordinator.data.resolutions
        return [DEFAULT_RESOLUTION]


class AxisZipstreamStrengthSelect(_ProfileSelect):
    """Zipstream strength, using the values the camera reports."""

    _attr_translation_key = "zipstream_strength"
    _attr_icon = "mdi:zip-box"
    _option_key = OPT_ZSTRENGTH

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry, "zipstream_strength")
        self._default = self.options[0]

    @property
    def options(self) -> list[str]:
        """Allowed strengths, read via listdefinitions where possible."""
        if self.coordinator.data and self.coordinator.data.allowed_zstrength:
            return self.coordinator.data.allowed_zstrength
        return list(ZSTRENGTH_FALLBACK)


class AxisFpsModeSelect(_ProfileSelect):
    """Zipstream dynamic FPS mode."""

    _attr_translation_key = "zipstream_fps_mode"
    _attr_icon = "mdi:motion-play"
    _option_key = OPT_ZFPSMODE
    _default = "fixed"

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry, "zipstream_fps_mode")

    @property
    def options(self) -> list[str]:
        """Documented by Axis as fixed or dynamic."""
        return list(ZFPS_MODES)


class AxisGopModeSelect(_ProfileSelect):
    """Zipstream GOP mode."""

    _attr_translation_key = "zipstream_gop_mode"
    _attr_icon = "mdi:key-variant"
    _option_key = OPT_ZGOPMODE
    _default = "fixed"

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry, "zipstream_gop_mode")

    @property
    def options(self) -> list[str]:
        """Documented by Axis as fixed or dynamic."""
        return list(ZGOP_MODES)
