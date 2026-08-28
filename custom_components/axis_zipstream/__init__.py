"""The Axis Zipstream integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PORT,
    DEFAULT_COMPRESSION,
    DEFAULT_FPS,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DOMAIN,
    MIN_EMBEDDED_DEVELOPMENT_VERSION,
    OPT_COMPRESSION,
    OPT_FPS,
    OPT_RESOLUTION,
    OPT_ZFPSMODE,
    OPT_ZGOPMODE,
    OPT_ZSTRENGTH,
    OWNED_PROFILE_DESCRIPTION,
    OWNED_PROFILE_NAME,
    ZSTRENGTH_FALLBACK,
)
from .vapix import (
    AcapApplication,
    StreamProfile,
    VapixAuthError,
    VapixClient,
    VapixConnectionError,
    VapixError,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CAMERA, Platform.SELECT, Platform.SENSOR]
UPDATE_INTERVAL = timedelta(minutes=5)


@dataclass
class AxisData:
    """Everything read from the camera, refreshed by the coordinator."""

    profiles: list[StreamProfile] = field(default_factory=list)
    mpeg_parameters: dict[str, str] = field(default_factory=dict)
    allowed_zstrength: list[str] = field(default_factory=list)
    applications: list[AcapApplication] = field(default_factory=list)


class AxisCoordinator(DataUpdateCoordinator[AxisData]):
    """Reads camera state. Entities are only created after the first refresh."""

    def __init__(self, hass: HomeAssistant, client: VapixClient) -> None:
        """Initialise."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.device: dict[str, str] = {}
        self.owned_profile_id: str | None = None
        self.supports_applications = False

    async def _async_update_data(self) -> AxisData:
        try:
            profiles = await self.client.get_stream_profiles()
            mpeg = await self.client.list_parameters("Image.I0.MPEG")
        except VapixAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except VapixError as err:
            raise UpdateFailed(str(err)) from err

        allowed = await self.client.list_allowed_values("Image.I0.MPEG.ZStrength")
        if not allowed:
            _LOGGER.debug(
                "Camera did not report allowed ZStrength values, using fallback list"
            )
            allowed = list(ZSTRENGTH_FALLBACK)

        # ACAP listing is optional. A camera without embedded development
        # support must not break the rest of the integration.
        applications: list[AcapApplication] = []
        if self.supports_applications:
            try:
                applications = await self.client.list_applications()
            except VapixError as err:
                _LOGGER.debug("Could not read the application list: %s", err)

        for profile in profiles:
            if profile.name == OWNED_PROFILE_NAME:
                self.owned_profile_id = profile.group_id
                break

        return AxisData(
            profiles=profiles,
            mpeg_parameters=mpeg,
            allowed_zstrength=allowed,
            applications=applications,
        )


def build_profile_parameters(entry: ConfigEntry) -> dict[str, str]:
    """Assemble the Parameters string for the profile this integration owns."""
    options = entry.options
    params: dict[str, str] = {
        "videocodec": "h264",
        "resolution": options.get(OPT_RESOLUTION, DEFAULT_RESOLUTION),
        "fps": str(options.get(OPT_FPS, DEFAULT_FPS)),
        "compression": str(options.get(OPT_COMPRESSION, DEFAULT_COMPRESSION)),
    }
    if zstrength := options.get(OPT_ZSTRENGTH):
        params["videozstrength"] = str(zstrength)
    if zfps := options.get(OPT_ZFPSMODE):
        params["videozfpsmode"] = str(zfps)
    if zgop := options.get(OPT_ZGOPMODE):
        params["videozgopmode"] = str(zgop)
    return params


async def _async_supports_applications(client: VapixClient) -> bool:
    """Check whether applications/list.cgi is available on this camera.

    Axis documents the endpoint as supported from
    Properties.EmbeddedDevelopment.Version 1.20 onwards.
    """
    try:
        props = await client.list_parameters("Properties.EmbeddedDevelopment")
    except VapixError as err:
        _LOGGER.debug("Could not read EmbeddedDevelopment properties: %s", err)
        return False

    if props.get("Properties.EmbeddedDevelopment.EmbeddedDevelopment") != "yes":
        return False

    raw = props.get("Properties.EmbeddedDevelopment.Version", "")
    try:
        version = tuple(int(part) for part in raw.split(".")[:2])
    except ValueError:
        _LOGGER.debug("Unreadable EmbeddedDevelopment version %r", raw)
        return False

    return version >= MIN_EMBEDDED_DEVELOPMENT_VERSION


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Axis Zipstream from a config entry."""
    session = async_get_clientsession(hass)
    client = VapixClient(
        session=session,
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )

    coordinator = AxisCoordinator(hass, client)

    try:
        coordinator.device = await client.device_info()
    except VapixAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except VapixConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator.supports_applications = await _async_supports_applications(client)

    # Parameters are read here, before any platform is forwarded, so entities
    # are built from real camera data rather than assumptions.
    await coordinator.async_config_entry_first_refresh()

    # Ensure the profile this integration owns exists. Nothing else on the
    # camera is written: other profiles and global parameters are untouched.
    if coordinator.owned_profile_id is None:
        try:
            group_id = await client.add_stream_profile(
                OWNED_PROFILE_NAME,
                OWNED_PROFILE_DESCRIPTION,
                build_profile_parameters(entry),
            )
        except VapixError as err:
            raise ConfigEntryNotReady(
                f"Could not create the {OWNED_PROFILE_NAME} stream profile: {err}"
            ) from err
        coordinator.owned_profile_id = group_id
        await coordinator.async_request_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Write changed options into the owned profile, then reload."""
    coordinator: AxisCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.owned_profile_id:
        try:
            await coordinator.client.update_stream_profile(
                coordinator.owned_profile_id, build_profile_parameters(entry)
            )
        except VapixError as err:
            _LOGGER.error("Could not write stream profile: %s", err)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
