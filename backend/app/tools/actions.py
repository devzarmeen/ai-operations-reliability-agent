"""Controlled high-impact actions. Execution is blocked without DB approval."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.safety.enforcement import HIGH_IMPACT_ACTIONS


async def execute_controlled_action(action_type: str) -> dict[str, Any]:
    normalized = action_type.lower()
    if normalized not in HIGH_IMPACT_ACTIONS:
        return {
            "ok": False,
            "error": "unsupported_or_unsafe_action",
            "action": normalized,
        }

    path_map = {
        "restart": "/admin/restart",
        "rollback": "/admin/rollback",
        "scale": "/admin/scale",
    }
    path = path_map.get(normalized)
    if path is None:
        return {
            "ok": False,
            "error": "action_not_implemented_for_simulated_environment",
            "action": normalized,
        }

    url = f"{settings.simulated_api_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"source": "approval_enforced"})
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:300]}
        return {
            "ok": response.status_code == 200,
            "action": normalized,
            "status_code": response.status_code,
            "result": body,
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "action": normalized,
            "error": str(exc),
        }
