"""Config and options flow for Axis Zipstream."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_PORT,
    DEFAULT_COMPRESSION,
    DEFAULT_FPS,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DOMAIN,
    OPT_COMPRESSION,
    OPT_FPS,
    OPT_RESOLUTION,
    OPT_ZFPSMODE,
    OPT_ZGOPMODE,
    OPT_ZSTRENGTH,
    ZFPS_MODES,
    ZGOP_MODES,
    ZSTRENGTH_FALLBACK,
)
from .vapix import VapixAuthError, VapixClient, VapixConnectionError, VapixError

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="root"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)


class AxisZipstreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for connection details and verify them against the camera."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = VapixClient(
                session=async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
            )
            try:
                info = await client.device_info()
            except VapixAuthError:
                errors["base"] = "invalid_auth"
            except VapixConnectionError:
                errors["base"] = "cannot_connect"
            except VapixError:
                _LOGGER.exception("Unexpected error talking to the camera")
                errors["base"] = "unknown"
            else:
                serial = info.get("serial") or user_input[CONF_HOST]
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                title = info.get("full_name") or f"Axis {user_input[CONF_HOST]}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AxisZipstreamOptionsFlow:
        """Return the options flow so settings can be changed later."""
        return AxisZipstreamOptionsFlow()


class AxisZipstreamOptionsFlow(OptionsFlow):
    """Change the settings of the stream profile this integration owns."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        allowed_zstrength = list(ZSTRENGTH_FALLBACK)
        if coordinator is not None and coordinator.data is not None:
            if coordinator.data.allowed_zstrength:
                allowed_zstrength = coordinator.data.allowed_zstrength

        schema = vol.Schema(
            {
                vol.Required(OPT_RESOLUTION, default=DEFAULT_RESOLUTION): str,
                vol.Required(OPT_FPS, default=DEFAULT_FPS): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    OPT_COMPRESSION, default=DEFAULT_COMPRESSION
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER
                    )
                ),
                vol.Required(
                    OPT_ZSTRENGTH, default=allowed_zstrength[0]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=allowed_zstrength, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(OPT_ZFPSMODE, default="fixed"): SelectSelector(
                    SelectSelectorConfig(
                        options=ZFPS_MODES, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(OPT_ZGOPMODE, default="fixed"): SelectSelector(
                    SelectSelectorConfig(
                        options=ZGOP_MODES, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )
