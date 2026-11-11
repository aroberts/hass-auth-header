"""End-to-end login flow tests against a real Home Assistant core."""

import base64
import hashlib
import inspect
import secrets

from homeassistant.components import frontend
from homeassistant.components.auth import login_flow as ha_login_flow
from homeassistant.setup import async_setup_component

CLIENT_ID = "http://127.0.0.1:8123/"
DEFAULT_HEADER = "X-Forwarded-Preferred-Username"
STORE_TOKEN_URL = "/auth_header/store-token.js"

# Core accepts PKCE on /auth/login_flow from 2026.10.
CORE_PKCE = "code_challenge" in inspect.getsource(ha_login_flow.LoginFlowIndexView.post)


def _stub_frontend(hass):
    """Satisfy the frontend dependency without loading its integration closure.

    add_extra_js_url only needs the extra-module-url collection to exist.
    """
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, set())
    hass.config.components.add("frontend")


async def _setup(hass, auth_header_config=None, trusted_proxies=("127.0.0.1/32",)):
    http_config = {"use_x_forwarded_for": True, "trusted_proxies": list(trusted_proxies)}
    assert await async_setup_component(hass, "http", {"http": http_config})
    assert await async_setup_component(hass, "auth", {})
    _stub_frontend(hass)
    assert await async_setup_component(hass, "auth_header", {"auth_header": auth_header_config})
    await hass.async_block_till_done()


def _pkce_pair():
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def _start_flow(client, headers, **extra):
    payload = {
        "client_id": CLIENT_ID,
        "handler": ["auth_header", None],
        "redirect_uri": CLIENT_ID,
        **extra,
    }
    return await client.post("/auth/login_flow", json=payload, headers=headers)


async def test_bypass_login_issues_token(hass, hass_client_no_auth):
    await _setup(hass)
    await hass.auth.async_create_user("alice")
    client = await hass_client_no_auth()

    verifier, challenge = _pkce_pair()
    pkce = {"code_challenge": challenge, "code_challenge_method": "S256"} if CORE_PKCE else {}
    resp = await _start_flow(client, {DEFAULT_HEADER: "Alice"}, **pkce)
    body = await resp.json()
    assert resp.status == 200, body
    assert body["type"] == "create_entry", body

    # Exchanging the code proves the PKCE context survived the flow.
    token_req = {"grant_type": "authorization_code", "client_id": CLIENT_ID, "code": body["result"]}
    if CORE_PKCE:
        token_req["code_verifier"] = verifier
    resp = await client.post("/auth/token", data=token_req)
    assert resp.status == 200, await resp.text()
    assert "access_token" in await resp.json()


async def test_missing_header_aborts(hass, hass_client_no_auth):
    await _setup(hass)
    await hass.auth.async_create_user("alice")
    client = await hass_client_no_auth()

    body = await (await _start_flow(client, {})).json()
    assert body["type"] == "abort" and body["reason"] == "not_allowed", body


async def test_unknown_user_aborts(hass, hass_client_no_auth):
    await _setup(hass)
    await hass.auth.async_create_user("alice")
    client = await hass_client_no_auth()

    body = await (await _start_flow(client, {DEFAULT_HEADER: "mallory"})).json()
    assert body["type"] == "abort", body


async def test_untrusted_proxy_aborts(hass, hass_client_no_auth):
    await _setup(hass, trusted_proxies=("10.9.9.9/32",))
    await hass.auth.async_create_user("alice")
    client = await hass_client_no_auth()

    body = await (await _start_flow(client, {DEFAULT_HEADER: "alice"})).json()
    assert body["type"] == "abort", body


async def test_no_bypass_requires_submit(hass, hass_client_no_auth):
    await _setup(hass, {"allow_bypass_login": False, "username_header": "X-User"})
    await hass.auth.async_create_user("alice")
    client = await hass_client_no_auth()

    body = await (await _start_flow(client, {"X-User": "alice"})).json()
    assert body["type"] == "form", body
    resp = await client.post(
        f"/auth/login_flow/{body['flow_id']}",
        json={"client_id": CLIENT_ID},
        headers={"X-User": "alice"},
    )
    body = await resp.json()
    assert body["type"] == "create_entry", body


async def test_store_token_js_served(hass, hass_client_no_auth):
    await _setup(hass)
    assert STORE_TOKEN_URL in hass.data[frontend.DATA_EXTRA_MODULE_URL]
    client = await hass_client_no_auth()

    resp = await client.get(STORE_TOKEN_URL)
    assert resp.status == 200
    assert "hassTokens" in await resp.text()


async def test_invalid_config_rejected(hass):
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "auth", {})
    _stub_frontend(hass)
    config = {"auth_header": {"debug": "not-a-bool"}}
    assert not await async_setup_component(hass, "auth_header", config)


async def test_provider_injected_first(hass):
    await _setup(hass)
    providers = [provider.type for provider in hass.auth.auth_providers]
    assert providers[0] == "auth_header", providers
