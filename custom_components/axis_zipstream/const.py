"""Constants for the Axis Zipstream integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "axis_zipstream"

# Config entry keys
CONF_PORT: Final = "port"

# Option keys
OPT_ACTIVE_PROFILE: Final = "active_profile"
OPT_RESOLUTION: Final = "resolution"
OPT_FPS: Final = "fps"
OPT_COMPRESSION: Final = "compression"
OPT_ZSTRENGTH: Final = "videozstrength"
OPT_ZFPSMODE: Final = "videozfpsmode"
OPT_ZGOPMODE: Final = "videozgopmode"
OPT_VIDEOCODEC: Final = "videocodec"

# Name of the stream profile this integration creates and owns.
# The integration writes ONLY to this profile. It never touches other
# profiles and never writes global Image.I*.MPEG.* parameters.
OWNED_PROFILE_NAME: Final = "HomeAssistant"
OWNED_PROFILE_DESCRIPTION: Final = "Managed by the Home Assistant axis_zipstream integration"

DEFAULT_PORT: Final = 80
DEFAULT_RESOLUTION: Final = "1280x720"
DEFAULT_FPS: Final = 15
DEFAULT_COMPRESSION: Final = 30
DEFAULT_VIDEOCODEC: Final = "h264"

# Documented by Axis: fixed or dynamic. Confirmed present on this device via
# root.Image.I0.MPEG.ZFpsMode / ZGopMode.
ZFPS_MODES: Final = ["fixed", "dynamic"]
ZGOP_MODES: Final = ["fixed", "dynamic"]

# Fallback only. The real list is read from the camera at runtime via
# param.cgi?action=listdefinitions. This is used only when that call fails.
ZSTRENGTH_FALLBACK: Final = ["off", "10", "20", "30"]

# VAPIX paths
PATH_PARAM: Final = "/axis-cgi/param.cgi"
PATH_SNAPSHOT: Final = "/axis-cgi/jpg/image.cgi"
PATH_RTSP: Final = "/axis-media/media.amp"
PATH_APPLICATIONS: Final = "/axis-cgi/applications/list.cgi"

# applications/list.cgi requires this property to be 1.20 or later.
MIN_EMBEDDED_DEVELOPMENT_VERSION: Final = (1, 20)

PARAM_GROUP_BRAND: Final = "Brand"
PARAM_GROUP_PROPERTIES: Final = "Properties"
PARAM_GROUP_MPEG: Final = "Image.I0.MPEG"
PARAM_GROUP_STREAMPROFILE: Final = "StreamProfile"
PARAM_RESOLUTIONS: Final = "Properties.Image.Resolution"
PARAM_FORMATS: Final = "Properties.Image.Format"

# Documented valid values of the RTSP videocodec argument. Note that the
# argument value is "jpeg", while Properties.Image.Format reports both
# "jpeg" and "mjpeg". They are not the same namespace.
VIDEOCODECS: Final = ["h264", "mpeg4", "jpeg"]

# Maps entries of Properties.Image.Format onto videocodec argument values.
FORMAT_TO_CODEC: Final = {
    "h264": "h264",
    "mpeg4": "mpeg4",
    "jpeg": "jpeg",
    "mjpeg": "jpeg",
}

# Zipstream is an H.264 technology. For any other codec the videoz*
# arguments are omitted rather than sent and silently ignored.
ZIPSTREAM_CODEC: Final = "h264"

FPS_MIN: Final = 1
FPS_MAX: Final = 30
COMPRESSION_MIN: Final = 0
COMPRESSION_MAX: Final = 100
