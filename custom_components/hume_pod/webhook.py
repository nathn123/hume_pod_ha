"""Optional per-person webhook delivery of weigh-in results.

Each person's profile may carry a *Webhook URL*. When it does, every weigh-in
assigned to that person is POSTed there as JSON — the same payload the
integration fires locally as the ``hume_pod_measurement`` event. The full
structure is documented in the README's Webhook section. An optional token is
sent as an ``Authorization: Bearer`` header.

Delivery is fire-and-forget: a single attempt, no retries. Failures are logged
as warnings and never affect the weigh-in itself. Leaving the URL empty (the
default) disables webhooks for that person.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import WEBHOOK_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_send_weigh_in(
    hass: HomeAssistant, url: str, payload: dict[str, Any], token: str | None = None
) -> None:
    """POST a weigh-in payload to the person's webhook. Never raises."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        session = async_get_clientsession(hass)
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT),
        ) as resp:
            body = await resp.text()
        if resp.status >= 400:
            _LOGGER.warning(
                "Webhook for %s replied %s: %s",
                payload.get("person") or "unassigned weigh-in",
                resp.status,
                body[:200],
            )
        else:
            _LOGGER.debug(
                "Webhook for %s accepted (status %s)",
                payload.get("person") or "unassigned weigh-in",
                resp.status,
            )
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.warning(
            "Webhook for %s failed: %s",
            payload.get("person") or "unassigned weigh-in",
            err,
        )
