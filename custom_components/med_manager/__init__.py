"""Home Assistant setup and services for Meds Manager.

CGPT-STAMP: 2026-09-21 reliable-lifecycle
There is one integration config entry, one shared store, and one engine. Services
make durable state changes, then immediately refresh scheduling and sensors.
"""

from datetime import datetime, timezone

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .coordinator import MedEngine, SIGNAL_UPDATE
from .storage import MedStorage

DOMAIN = "med_manager"
PLATFORMS = [Platform.SENSOR]


def _require_medication(storage: MedStorage, med_id: str) -> None:
    """Raise a clear action error instead of silently ignoring an unknown ID."""
    if not med_id or storage.get_med(med_id) is None:
        raise HomeAssistantError(f"Unknown medication ID: {med_id}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the sole integration entry and initialize all runtime components."""
    hass.data.setdefault(DOMAIN, {})

    storage = MedStorage(hass)
    await storage.async_load()
    engine = MedEngine(hass, storage)
    hass.data[DOMAIN].update({"storage": storage, "engine": engine})

    async def handle_take(call: ServiceCall) -> None:
        """Persist a taken dose, then refresh schedule and entities immediately."""
        med_id = call.data["med_id"]
        _require_medication(storage, med_id)
        quantity = call.data.get("quantity", 1)
        await storage.async_mark_taken(
            med_id, datetime.now(timezone.utc).timestamp(), quantity
        )
        await engine.async_tick()
        async_dispatcher_send(hass, SIGNAL_UPDATE, med_id)

    async def handle_snooze(call: ServiceCall) -> None:
        """Persist a snooze interval, then refresh the visible status."""
        med_id = call.data["med_id"]
        _require_medication(storage, med_id)
        until = datetime.now(timezone.utc).timestamp() + call.data["minutes"] * 60
        await storage.async_snooze(med_id, until)
        await engine.async_tick()
        async_dispatcher_send(hass, SIGNAL_UPDATE, med_id)

    async def handle_refill(call: ServiceCall) -> None:
        """Persist inventory replacement, then refresh refill status."""
        med_id = call.data["med_id"]
        _require_medication(storage, med_id)
        await storage.async_refill(med_id, call.data["amount"])
        await engine.async_tick()
        async_dispatcher_send(hass, SIGNAL_UPDATE, med_id)

    async def handle_create_medication(call: ServiceCall) -> None:
        """Create a medication through automations or dashboard actions.

        CGPT-STAMP: A targeted dispatcher message lets sensor.py add the new
        entity without a Home Assistant restart or config-entry reload.
        """
        med_id = call.data["med_id"]
        if storage.get_med(med_id) is not None:
            raise HomeAssistantError(f"Medication ID already exists: {med_id}")
        await storage.async_create_medication(
            med_id,
            {
                "common_name": call.data["common_name"],
                "generic_name": call.data.get("generic_name"),
                "brand_name": call.data.get("brand_name"),
                "person": call.data["person"],
                "interval_hours": call.data["interval_hours"],
                "last_taken": None,
                "next_due": None,
                "status": "not_initialized",
                "snooze_until": None,
                "last_notified": None,
                "notification_count": 0,
                "current_count": call.data.get("current_count", 0),
                "low_stock_threshold": call.data.get("low_stock_threshold", 5),
                "refill_required": False,
            },
        )
        await engine.async_tick()
        async_dispatcher_send(hass, SIGNAL_UPDATE, med_id)

    async def handle_delete_medication(call: ServiceCall) -> None:
        """Permanently remove a medication and its dynamic sensor."""
        med_id = call.data["med_id"]
        _require_medication(storage, med_id)
        await storage.async_delete_medication(med_id)
        async_dispatcher_send(hass, SIGNAL_UPDATE, med_id)

    # CGPT-STAMP: schemas validate inputs at the service boundary.
    hass.services.async_register(
        DOMAIN, "take", handle_take,
        schema=vol.Schema({vol.Required("med_id"): str, vol.Optional("quantity", default=1): vol.All(int, vol.Range(min=1))}),
    )
    hass.services.async_register(
        DOMAIN, "snooze", handle_snooze,
        schema=vol.Schema({vol.Required("med_id"): str, vol.Required("minutes"): vol.All(int, vol.Range(min=1, max=1440))}),
    )
    hass.services.async_register(
        DOMAIN, "refill", handle_refill,
        schema=vol.Schema({vol.Required("med_id"): str, vol.Required("amount"): vol.All(int, vol.Range(min=0))}),
    )
    hass.services.async_register(
        DOMAIN, "create_medication", handle_create_medication,
        schema=vol.Schema({
            vol.Required("med_id"): str, vol.Required("common_name"): str,
            vol.Required("person"): str, vol.Required("interval_hours"): vol.All(int, vol.Range(min=1)),
            vol.Optional("generic_name"): str, vol.Optional("brand_name"): str,
            vol.Optional("current_count", default=0): vol.All(int, vol.Range(min=0)),
            vol.Optional("low_stock_threshold", default=5): vol.All(int, vol.Range(min=0)),
        }),
    )
    hass.services.async_register(
        DOMAIN, "delete_medication", handle_delete_medication,
        schema=vol.Schema({vol.Required("med_id"): str}),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await engine.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload cleanly so reloads cannot leave duplicate loops or services."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    engine = hass.data.get(DOMAIN, {}).get("engine")
    if engine is not None:
        await engine.async_stop()

    # One config entry is enforced by config_flow. Remove handlers on unload.
    for service in ("take", "snooze", "refill", "create_medication", "delete_medication"):
        hass.services.async_remove(DOMAIN, service)
    hass.data.pop(DOMAIN, None)
    return unload_ok
