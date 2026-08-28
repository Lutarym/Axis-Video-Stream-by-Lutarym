"""Sensor entities exposing the ACAP applications installed on the camera."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisCoordinator
from .const import DOMAIN
from .entity import AxisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one sensor per installed ACAP application.

    The application list was already fetched by the coordinator before this
    platform is set up, so entities reflect what is actually on the camera.
    """
    coordinator: AxisCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data is None or not coordinator.data.applications:
        return

    async_add_entities(
        AcapApplicationSensor(coordinator, entry, application.name)
        for application in coordinator.data.applications
    )


class AcapApplicationSensor(AxisEntity, SensorEntity):
    """Reports the run status of one ACAP application."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:puzzle"

    def __init__(
        self, coordinator: AxisCoordinator, entry: ConfigEntry, app_name: str
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, entry)
        self._app_name = app_name
        self._attr_unique_id = f"{self._base_unique_id}_acap_{app_name}"
        self._attr_name = self._application.nice_name if self._application else app_name

    @property
    def _application(self):
        """Look up the current data for this application."""
        if self.coordinator.data is None:
            return None
        for application in self.coordinator.data.applications:
            if application.name == self._app_name:
                return application
        return None

    @property
    def available(self) -> bool:
        """Unavailable if the app disappeared from the camera."""
        return super().available and self._application is not None

    @property
    def native_value(self) -> str | None:
        """Status as reported by the camera, e.g. Running or Stopped."""
        application = self._application
        return application.status if application else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Everything else the camera reports about this application."""
        application = self._application
        if application is None:
            return {}
        attributes = {
            "name": application.name,
            "vendor": application.vendor,
            "version": application.version,
            "application_id": application.application_id,
            "license": application.license_state,
            "license_name": application.license_name,
        }
        if application.configuration_page:
            attributes["configuration_url"] = (
                f"http://{self.coordinator.client.host}/{application.configuration_page}"
            )
        return {key: value for key, value in attributes.items() if value}
