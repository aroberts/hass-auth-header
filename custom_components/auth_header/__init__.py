import logging
import os.path
from collections import OrderedDict
from typing import Any

import homeassistant.helpers.config_validation as cv
import probatio
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from . import headers

DOMAIN = "auth_header"
_LOGGER = logging.getLogger(__name__)


def _none_to_empty_dict(value: Any) -> Any:
    """Allow a bare `auth_header:` key with every option commented out."""
    return {} if value is None else value


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            _none_to_empty_dict,
            {
                probatio.Optional(
                    headers.CONF_USERNAME_HEADER, default="X-Forwarded-Preferred-Username"
                ): cv.string,
                probatio.Optional(headers.CONF_ALLOW_BYPASS_LOGIN, default=True): cv.boolean,
                probatio.Optional(headers.CONF_DEBUG, default=False): cv.boolean,
            },
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config):
    """Inject the header auth provider ahead of the configured providers."""
    # Load script to store tokens in local storage, else we'll re-auth on every browser refresh.
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/auth_header/store-token.js",
                os.path.join(os.path.dirname(__file__), "store-token.js"),
                True,
            )
        ]
    )
    add_extra_js_url(hass, "/auth_header/store-token.js")

    provider = headers.HeaderAuthProvider(hass, hass.auth._store, config[DOMAIN])
    providers = OrderedDict()
    providers[(provider.type, provider.id)] = provider
    providers.update(hass.auth._providers)
    hass.auth._providers = providers
    _LOGGER.debug("Injected auth_header provider")
    return True
