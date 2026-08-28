"""Shared entity base for Axis Zipstream."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AxisCoordinator
from .const import DOMAIN


class AxisEntity(CoordinatorEntity[AxisCoordinator]):
    """Base class that attaches every entity to the same device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._entry = entry
        device = coordinator.device
        self._base_unique_id = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._base_unique_id)},
            manufacturer=device.get("manufacturer") or "Axis Communications",
            model=device.get("model") or None,
            name=device.get("full_name") or None,
            serial_number=device.get("serial") or None,
            configuration_url=f"http://{coordinator.client.host}/",
        )


class AxisProfileOptionEntity(AxisEntity):
    """Base for entities that change one setting of the owned stream profile.

    Writing goes through the config entry options. The update listener in
    __init__.py then writes the whole Parameters string into the profile that
    this integration owns. Global camera parameters are never touched, and no
    other stream profile is modified.
    """

    _option_key: str
    _attr_entity_category = EntityCategory.CONFIG

    async def _async_store_option(self, value: object) -> None:
        """Persist a new value for this entity's option key."""
        options = dict(self._entry.options)
        options[self._option_key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=options)
