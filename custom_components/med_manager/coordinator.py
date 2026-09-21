"""Scheduling engine for Meds Manager.

CGPT-STAMP: 2026-09-21 reliable-lifecycle
The engine owns schedule evaluation, durable derived state, notifications, and
one dispatcher signal consumed by the sensor platform.
"""

import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .storage import MedStorage

DOMAIN = "med_manager"
SIGNAL_UPDATE = "med_manager_update"


class MedEngine:
    """Evaluate every medication on startup and at a short regular interval."""

    def __init__(self, hass: HomeAssistant, storage: MedStorage) -> None:
        self.hass = hass
        self.storage = storage
        self._task: asyncio.Task | None = None
        self._running = False

    async def async_start(self) -> None:
        """Evaluate immediately, then start the periodic loop."""
        self._running = True
        await self.async_tick()
        self._task = self.hass.async_create_task(self._async_run_loop())

    async def async_stop(self) -> None:
        """Cancel the loop cleanly when the config entry unloads."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _async_run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(30)
            if self._running:
                await self.async_tick()

    async def async_tick(self) -> None:
        """Recalculate all records and persist their derived state.

        CGPT-STAMP: The single save at the end makes engine-generated state
        (next due, status, refill warning, notification history) restart-safe.
        """
        now = datetime.now(timezone.utc)
        changed_ids: list[str] = []

        for med_id, med in self.storage.get_all().items():
            state = self._evaluate(med, now)
            med["status"] = state["status"]
            med["next_due"] = state["next_due"]
            med["refill_required"] = state["refill_required"]

            if state["should_notify"]:
                await self._async_notify(med_id, med, state["status"])
                med["last_notified"] = now.timestamp()
                med["notification_count"] = med.get("notification_count", 0) + 1

            self.storage.update_med(med_id, med)
            self._emit_event(med_id, state)
            changed_ids.append(med_id)

        if changed_ids:
            await self.storage.async_save()
            # No event bus bridge: re-firing identical event names caused recursion.
            async_dispatcher_send(self.hass, SIGNAL_UPDATE, None)

    def _evaluate(self, med: dict, now: datetime) -> dict:
        """Calculate state using the actual last-taken timestamp."""
        result = {
            "status": "not_initialized",
            "next_due": None,
            "should_notify": False,
            "refill_required": False,
        }
        last_taken = med.get("last_taken")
        interval_hours = med.get("interval_hours")
        if not last_taken or not interval_hours:
            return result

        result["refill_required"] = (
            int(med.get("current_count", 0))
            <= int(med.get("low_stock_threshold", 0))
        )
        next_due = last_taken + (int(interval_hours) * 3600)
        result["next_due"] = next_due

        if med.get("snooze_until") and now.timestamp() < med["snooze_until"]:
            result["status"] = "snoozed"
            return result

        seconds_to_due = next_due - now.timestamp()
        if seconds_to_due < -3600:
            result["status"] = "overdue"
        elif seconds_to_due <= 0:
            result["status"] = "due"
        elif seconds_to_due <= 3600:
            result["status"] = "due_soon"
        else:
            result["status"] = "not_due"

        last_notified = med.get("last_notified")
        result["should_notify"] = (
            result["status"] in {"due_soon", "due", "overdue"}
            and (not last_notified or now.timestamp() - last_notified > 900)
        )
        return result

    async def _async_notify(self, med_id: str, med: dict, status: str) -> None:
        """Create a durable Home Assistant notification without blocking the loop."""
        name = med.get("common_name") or med_id
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Medication Reminder",
                "message": f"Medication '{name}' is {status}.",
            },
            blocking=False,
        )

    def _emit_event(self, med_id: str, state: dict) -> None:
        """Emit an automation event once; never listen and re-fire it."""
        self.hass.bus.async_fire(
            f"{DOMAIN}_{state['status']}",
            {
                "med_id": med_id,
                "status": state["status"],
                "next_due": state["next_due"],
                "refill_required": state["refill_required"],
            },
        )
