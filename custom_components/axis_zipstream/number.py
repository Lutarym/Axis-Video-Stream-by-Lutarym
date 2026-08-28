"""Number entities for Axis Zipstream."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisCoordinator
from .const import (
    COMPRESSION_MAX,
    COMPRESSION_MIN,
    DEFAULT_COMPRESSION,
    DEFAULT_FPS,
    DOMAIN,
    FPS_MAX,
    FPS_MIN,
    OPT_COMPRESSION,
    OPT_FPS,
)
from .entity import AxisProfileOptionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number entities."""
    coordinator: AxisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AxisFpsNumber(coordinator, entry),
            AxisCompressionNumber(coordinator, entry),
        ]
    )


class _ProfileNumber(AxisProfileOptionEntity, NumberEntity):
    """Shared behaviour for numbers that write into the owned profile."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _default: int

    def __init__(
        self, coordinator: AxisCoordinator, entry: ConfigEntry, suffix: str
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_unique_id}_{suffix}"

    @property
    def native_value(self) -> float:
        """Current value from the config entry options."""
        return float(self._entry.options.get(self._option_key, self._default))

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value into the owned profile."""
        await self._async_store_option(int(value))


class AxisFpsNumber(_ProfileNumber):
    """Frame rate requested from the camera."""

    _attr_translation_key = "fps"
    _attr_icon = "mdi:filmstrip"
    _attr_native_unit_of_measurement = "fps"
    _attr_native_min_value = FPS_MIN
    _attr_native_max_value = FPS_MAX
    _option_key = OPT_FPS
    _default = DEFAULT_FPS

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry, "fps")


class AxisCompressionNumber(_ProfileNumber):
    """Compression level. Axis recommends 30, including for Zipstream."""

    _attr_translation_key = "compression"
    _attr_icon = "mdi:archive"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = COMPRESSION_MIN
    _attr_native_max_value = COMPRESSION_MAX
    _option_key = OPT_COMPRESSION
    _default = DEFAULT_COMPRESSION

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator, entry, "compression")
