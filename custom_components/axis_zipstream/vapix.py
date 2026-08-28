"""Minimal VAPIX client for Axis cameras.

Scope is deliberately narrow: read parameters, read parameter definitions,
manage exactly one stream profile owned by this integration, and fetch
snapshots. It never writes global Image.I*.MPEG.* parameters.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import aiohttp

from .const import PATH_APPLICATIONS, PATH_PARAM, PATH_RTSP, PATH_SNAPSHOT

_LOGGER = logging.getLogger(__name__)

# aiohttp gained DigestAuthMiddleware in 3.12. Older aiohttp cannot do digest.
try:  # pragma: no cover - depends on installed aiohttp
    from aiohttp import DigestAuthMiddleware

    HAS_DIGEST_SUPPORT = True
except ImportError:  # pragma: no cover
    DigestAuthMiddleware = None  # type: ignore[assignment]
    HAS_DIGEST_SUPPORT = False

TIMEOUT = aiohttp.ClientTimeout(total=15)


class VapixError(Exception):
    """Base error."""


class VapixAuthError(VapixError):
    """Authentication failed."""


class VapixConnectionError(VapixError):
    """Could not reach the camera."""


@dataclass(slots=True)
class StreamProfile:
    """A stream profile as stored on the camera."""

    group_id: str  # e.g. "S0"
    name: str
    description: str
    parameters: str  # raw query string, e.g. "resolution=1280x720&fps=15"


@dataclass(slots=True)
class AcapApplication:
    """An installed ACAP application.

    Field names mirror the attributes returned by
    /axis-cgi/applications/list.cgi.
    """

    name: str  # Name, e.g. "vmd"
    nice_name: str  # NiceName, e.g. "AXIS Video Motion Detection"
    vendor: str
    version: str
    application_id: str
    status: str  # Running, Stopped, Idle
    license_state: str  # License
    license_name: str
    configuration_page: str


def encode_profile_parameters(params: dict[str, str]) -> str:
    """Percent-encode a parameter string for StreamProfile.S#.Parameters.

    Axis requires the inner separators to be encoded so the camera does not
    mistake them for CGI arguments: '=' -> %3D, '&' -> %26, ' ' -> %20,
    '%' -> %25.
    """
    raw = "&".join(f"{key}={value}" for key, value in params.items())
    return quote(raw, safe="")


def decode_profile_parameters(raw: str) -> dict[str, str]:
    """Parse a stored Parameters string into a dict. Tolerant by design."""
    result: dict[str, str] = {}
    for chunk in raw.split("&"):
        if "=" in chunk:
            key, _, value = chunk.partition("=")
            result[key.strip()] = value.strip()
    return result


class VapixClient:
    """Talks to one Axis camera over VAPIX."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        port: int = 80,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._base = f"http://{host}:{port}"
        self._basic = aiohttp.BasicAuth(username, password)
        # Set once we learn which scheme the camera actually wants.
        self._use_digest: bool | None = None

    @property
    def host(self) -> str:
        """Camera host."""
        return self._host

    async def _request_text(self, path: str, params: dict[str, str]) -> str:
        raw = await self._request_bytes(path, params)
        return raw.decode("utf-8", errors="replace")

    async def _request_bytes(self, path: str, params: dict[str, str]) -> bytes:
        """Perform a GET, transparently handling basic vs digest auth."""
        url = f"{self._base}{path}"

        if self._use_digest is not True:
            try:
                async with self._session.get(
                    url, params=params, auth=self._basic, timeout=TIMEOUT
                ) as resp:
                    if resp.status != 401:
                        if resp.status >= 400:
                            raise VapixError(f"HTTP {resp.status} for {path}")
                        self._use_digest = False
                        return await resp.read()
            except aiohttp.ClientError as err:
                raise VapixConnectionError(str(err)) from err

        # Basic was rejected (or digest already known to be required).
        if not HAS_DIGEST_SUPPORT:
            raise VapixAuthError(
                "Camera requires digest authentication but the installed "
                "aiohttp is older than 3.12 and cannot perform it."
            )

        digest = DigestAuthMiddleware(login=self._username, password=self._password)
        try:
            async with aiohttp.ClientSession(middlewares=(digest,)) as session:
                async with session.get(url, params=params, timeout=TIMEOUT) as resp:
                    if resp.status == 401:
                        raise VapixAuthError("Username or password rejected")
                    if resp.status >= 400:
                        raise VapixError(f"HTTP {resp.status} for {path}")
                    self._use_digest = True
                    return await resp.read()
        except aiohttp.ClientError as err:
            raise VapixConnectionError(str(err)) from err

    async def list_parameters(self, group: str) -> dict[str, str]:
        """Return a parameter group as a flat dict, without the 'root.' prefix."""
        text = await self._request_text(
            PATH_PARAM, {"action": "list", "group": group}
        )
        result: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or "=" not in line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("root."):
                key = key[5:]
            result[key] = value.strip()
        return result

    async def list_allowed_values(self, parameter: str) -> list[str] | None:
        """Return the values a parameter accepts, or None if undeterminable.

        Uses action=listdefinitions, which Axis documents as returning the
        valid values where applicable. The XML schema is parsed tolerantly:
        we collect the 'value' attribute of every descendant of the matching
        <parameter> element rather than assuming specific child tag names.
        """
        try:
            text = await self._request_text(
                PATH_PARAM,
                {
                    "action": "listdefinitions",
                    "listformat": "xmlschema",
                    "group": parameter,
                },
            )
        except VapixError as err:
            _LOGGER.debug("listdefinitions failed for %s: %s", parameter, err)
            return None

        short_name = parameter.rsplit(".", 1)[-1]
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            _LOGGER.debug("listdefinitions XML unparsable for %s: %s", parameter, err)
            return None

        for element in root.iter():
            if not element.tag.endswith("parameter"):
                continue
            if element.get("name") != short_name:
                continue
            values = [
                value
                for child in element.iter()
                if child is not element and (value := child.get("value"))
            ]
            # Preserve order, drop duplicates.
            seen: dict[str, None] = {}
            for value in values:
                seen.setdefault(value, None)
            return list(seen) or None

        return None

    async def get_stream_profiles(self) -> list[StreamProfile]:
        """Return all stream profiles stored on the camera."""
        params = await self.list_parameters("StreamProfile")
        by_id: dict[str, dict[str, str]] = {}
        for key, value in params.items():
            parts = key.split(".")
            # StreamProfile.S0.Name -> ["StreamProfile", "S0", "Name"]
            if len(parts) != 3 or not parts[1].startswith("S"):
                continue
            by_id.setdefault(parts[1], {})[parts[2]] = value

        profiles: list[StreamProfile] = []
        for group_id, fields in sorted(by_id.items()):
            name = fields.get("Name")
            if not name:
                continue
            profiles.append(
                StreamProfile(
                    group_id=group_id,
                    name=name,
                    description=fields.get("Description", ""),
                    parameters=fields.get("Parameters", ""),
                )
            )
        return profiles

    async def add_stream_profile(
        self, name: str, description: str, parameters: dict[str, str]
    ) -> str:
        """Create a new stream profile and return its group id, e.g. 'S1'."""
        encoded = encode_profile_parameters(parameters)
        # Built manually: the Parameters value is already percent-encoded and
        # must not be encoded a second time by the query builder.
        query = (
            "action=add"
            "&template=streamprofile"
            "&group=StreamProfile"
            f"&StreamProfile.S.Name={quote(name, safe='')}"
            f"&StreamProfile.S.Description={quote(description, safe='')}"
            f"&StreamProfile.S.Parameters={encoded}"
        )
        text = await self._request_text_raw_query(PATH_PARAM, query)
        first = text.strip().splitlines()[0] if text.strip() else ""
        if "OK" not in first.upper():
            raise VapixError(f"Camera rejected profile creation: {text.strip()!r}")
        group_id = first.split()[0]
        return group_id

    async def update_stream_profile(
        self, group_id: str, parameters: dict[str, str]
    ) -> None:
        """Overwrite the Parameters string of an existing profile."""
        encoded = encode_profile_parameters(parameters)
        query = f"action=update&StreamProfile.{group_id}.Parameters={encoded}"
        text = await self._request_text_raw_query(PATH_PARAM, query)
        if "OK" not in text.upper():
            raise VapixError(f"Camera rejected profile update: {text.strip()!r}")

    async def _request_text_raw_query(self, path: str, query: str) -> str:
        """GET with a pre-built query string that must not be re-encoded."""
        raw = await self._request_bytes(f"{path}?{query}", {})
        return raw.decode("utf-8", errors="replace")

    async def list_applications(self) -> list[AcapApplication]:
        """Return the ACAP applications installed on the camera.

        Parses the XML returned by /axis-cgi/applications/list.cgi. The root
        element carries a result attribute; each application is one
        <application> element with attributes.
        """
        text = await self._request_text(PATH_APPLICATIONS, {})
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            raise VapixError(f"Unparsable application list: {err}") from err

        result = root.get("result", "").lower()
        if result and result != "ok":
            raise VapixError(f"Camera returned result={result!r} for application list")

        applications: list[AcapApplication] = []
        for element in root.iter():
            if not element.tag.endswith("application"):
                continue
            name = element.get("Name")
            if not name:
                continue
            applications.append(
                AcapApplication(
                    name=name,
                    nice_name=element.get("NiceName") or name,
                    vendor=element.get("Vendor", ""),
                    version=element.get("Version", ""),
                    application_id=element.get("ApplicationID", ""),
                    status=element.get("Status", ""),
                    license_state=element.get("License", ""),
                    license_name=element.get("LicenseName", ""),
                    configuration_page=element.get("ConfigurationPage", ""),
                )
            )
        return applications

    async def list_formats(self) -> list[str]:
        """Return the image formats this camera reports.

        Read from Properties.Image.Format. These are format names, not RTSP
        videocodec argument values. Callers must map them.
        """
        try:
            props = await self.list_parameters("Properties.Image.Format")
        except VapixError as err:
            _LOGGER.debug("Could not read supported formats: %s", err)
            return []

        raw = props.get("Properties.Image.Format", "")
        return [item.strip().lower() for item in raw.split(",") if item.strip()]

    async def list_resolutions(self) -> list[str]:
        """Return the resolutions this camera supports.

        Read from Properties.Image.Resolution, which Axis documents as the
        way to check supported resolutions. Returns an empty list if the
        camera does not report it, so callers can fall back.
        """
        try:
            props = await self.list_parameters("Properties.Image.Resolution")
        except VapixError as err:
            _LOGGER.debug("Could not read supported resolutions: %s", err)
            return []

        raw = props.get("Properties.Image.Resolution", "")
        resolutions = [item.strip() for item in raw.split(",") if item.strip()]
        return resolutions

    async def snapshot(self, resolution: str | None = None) -> bytes:
        """Fetch a single JPEG image."""
        params: dict[str, str] = {}
        if resolution:
            params["resolution"] = resolution
        return await self._request_bytes(PATH_SNAPSHOT, params)

    def rtsp_url(self, profile_name: str) -> str:
        """Build the RTSP URL for a named stream profile."""
        query = urlencode({"streamprofile": profile_name})
        credentials = f"{quote(self._username, safe='')}:{quote(self._password, safe='')}"
        return f"rtsp://{credentials}@{self._host}:554{PATH_RTSP}?{query}"

    async def device_info(self) -> dict[str, Any]:
        """Return brand and serial information for the device registry."""
        brand = await self.list_parameters("Brand")
        properties = await self.list_parameters("Properties.System")
        return {
            "model": brand.get("Brand.ProdNbr") or brand.get("Brand.ProdShortName", ""),
            "full_name": brand.get("Brand.ProdFullName", ""),
            "manufacturer": brand.get("Brand.Brand", "Axis Communications"),
            "serial": properties.get("Properties.System.SerialNumber", ""),
        }
