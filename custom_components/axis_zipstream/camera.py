"""Camera entity for Axis Zipstream."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_web
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisCoordinator
from .const import (
    DEFAULT_COMPRESSION,
    DEFAULT_FPS,
    DEFAULT_RESOLUTION,
    DOMAIN,
    DEFAULT_TRANSPORT,
    OPT_ACTIVE_PROFILE,
    OPT_COMPRESSION,
    OPT_FPS,
    OPT_RESOLUTION,
    OPT_TRANSPORT,
    OWNED_PROFILE_NAME,
)
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

    _attr_name = None

    def __init__(self, coordinator: AxisCoordinator, entry: ConfigEntry) -> None:
        """Initialise."""
        AxisEntity.__init__(self, coordinator, entry)
        Camera.__init__(self)
        self._attr_unique_id = f"{self._base_unique_id}_camera"

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Announce RTSP streaming only while the RTSP path is selected.

        With the feature absent, Home Assistant falls back to the MJPEG
        handler below, which is what delivers the HTTP path.
        """
        if self._transport == "rtsp":
            return CameraEntityFeature.STREAM
        return CameraEntityFeature(0)

    @property
    def _transport(self) -> str:
        """Selected delivery path: rtsp or http."""
        return str(self._entry.options.get(OPT_TRANSPORT, DEFAULT_TRANSPORT))

    @property
    def _active_profile(self) -> str:
        """Profile the user selected, defaulting to the one we own."""
        return self._entry.options.get(OPT_ACTIVE_PROFILE, OWNED_PROFILE_NAME)

    async def stream_source(self) -> str | None:
        """Return the RTSP URL, or nothing when HTTP delivery is selected."""
        if self._transport != "rtsp":
            return None
        return self.coordinator.client.rtsp_url(self._active_profile)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a still image over VAPIX.

        Nothing is stored between calls: every request goes to the camera and
        returns a freshly fetched picture.
        """
        resolution = self._entry.options.get(OPT_RESOLUTION, DEFAULT_RESOLUTION)
        try:
            return await self.coordinator.client.snapshot(resolution)
        except VapixError as err:
            _LOGGER.warning(
                "Snapshot from %s failed: %s",
                self.coordinator.client.host,
                err,
            )
            return None

    def _image_params(self) -> dict[str, str]:
        """Parameters shared by the snapshot and MJPEG endpoints."""
        options = self._entry.options
        return {
            "resolution": str(options.get(OPT_RESOLUTION, DEFAULT_RESOLUTION)),
            "fps": str(options.get(OPT_FPS, DEFAULT_FPS)),
            "compression": str(options.get(OPT_COMPRESSION, DEFAULT_COMPRESSION)),
        }

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Serve the preview from the camera's continuous MJPEG stream.

        One connection stays open and frames arrive as the camera produces
        them. This is what makes the dashboard preview move smoothly instead
        of updating in visible steps.
        """
        stream = self.coordinator.client.open_mjpeg_stream(self._image_params())
        return await async_aiohttp_proxy_web(self.hass, request, stream)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose which profile is in use, for troubleshooting."""
        return {
            "active_profile": self._active_profile,
            "transport": self._transport,
        }
