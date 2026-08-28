"""Camera entity for Axis Zipstream."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisCoordinator
from .const import DEFAULT_RESOLUTION, DOMAIN, OPT_ACTIVE_PROFILE, OWNED_PROFILE_NAME
from .entity import AxisEntity
from .vapix import VapixError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the camera entity."""
    coordinator: AxisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AxisZipstreamCamera(coordinator, entry)])


class AxisZipstreamCamera(AxisEntity, Camera):
    """Live view for the currently selected stream profile."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_name = None

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        AxisEntity.__init__(self, coordinator, entry)
        Camera.__init__(self)
        self._attr_unique_id = f"{self._base_unique_id}_camera"

    @property
    def _active_profile(self) -> str:
        """Profile the user selected, defaulting to the one we own."""
        return self._entry.options.get(OPT_ACTIVE_PROFILE, OWNED_PROFILE_NAME)

    async def stream_source(self) -> str | None:
        """Return the RTSP URL of the active profile."""
        return self.coordinator.client.rtsp_url(self._active_profile)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a still image over VAPIX."""
        resolution = self._entry.options.get("resolution", DEFAULT_RESOLUTION)
        try:
            return await self.coordinator.client.snapshot(resolution)
        except VapixError as err:
            _LOGGER.debug("Snapshot failed: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose which profile is in use, for troubleshooting."""
        return {"active_profile": self._active_profile}
