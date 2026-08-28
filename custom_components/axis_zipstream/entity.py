"""Shared entity base for Axis Zipstream."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
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
