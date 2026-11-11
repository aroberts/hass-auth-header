import logging
import os.path
from collections import OrderedDict
from typing import Any

import homeassistant.helpers.config_validation as cv
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

from . import headers

# Build the schema with the library HA's own config_validation uses (probatio from 2026.10,
# voluptuous before), so it matches what cv.string/cv.boolean raise and what config.py
# catches. Checking cv, not importability, keeps an unrelated install of probatio on an older
# HA from switching libraries.
if hasattr(cv, "probatio"):
    schema_lib = cv.probatio
else:
    schema_lib = cv.vol

try:
    from homeassistant.components.http import StaticPathConfig  # 2024.7+
except ImportError:
    StaticPathConfig = None

DOMAIN = "auth_header"
STORE_TOKEN_URL = "/auth_header/store-token.js"
_LOGGER = logging.getLogger(__name__)


def _none_to_empty_dict(value: Any) -> Any:
    """Allow a bare `auth_header:` key with every option commented out."""
    return {} if value is None else value


CONFIG_SCHEMA = schema_lib.Schema(
    {
        DOMAIN: schema_lib.All(
            _none_to_empty_dict,
            {
                schema_lib.Optional(
                    headers.CONF_USERNAME_HEADER, default="X-Forwarded-Preferred-Username"
                ): cv.string,
                schema_lib.Optional(headers.CONF_ALLOW_BYPASS_LOGIN, default=True): cv.boolean,
                schema_lib.Optional(headers.CONF_DEBUG, default=False): cv.boolean,
            },
        )
    },
    extra=schema_lib.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config):
    """Inject the header auth provider ahead of the configured providers."""
    # Load script to store tokens in local storage, else we'll re-auth on every browser refresh.
    await _register_store_token_js(hass)
    add_extra_js_url(hass, STORE_TOKEN_URL)

    provider = headers.HeaderAuthProvider(hass, hass.auth._store, config[DOMAIN])
    providers = OrderedDict()
    providers[(provider.type, provider.id)] = provider
    providers.update(hass.auth._providers)
    hass.auth._providers = providers
    _LOGGER.debug("Injected auth_header provider")
    return True


async def _register_store_token_js(hass: HomeAssistant) -> None:
    path = os.path.join(os.path.dirname(__file__), "store-token.js")
    if StaticPathConfig is not None:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STORE_TOKEN_URL, path, True)]
        )
    else:
        # register_static_path was removed in 2026.1, after StaticPathConfig arrived.
        hass.http.register_static_path(STORE_TOKEN_URL, path, True)
