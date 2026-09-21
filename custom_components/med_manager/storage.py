"""Persistent medication storage for Meds Manager.

CGPT-STAMP: 2026-09-21 reliable-lifecycle
This module is the single source of truth. Every public async mutation saves
before it returns, so Home Assistant restarts cannot discard user actions.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

DOMAIN = "med_manager"
STORAGE_VERSION = 1
STORAGE_KEY = "medications"


class MedStorage:
    """Own the in-memory database and its Home Assistant persistent store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{STORAGE_KEY}")
        self.hass.data.setdefault(DOMAIN, {})
        self.hass.data[DOMAIN].setdefault("medications", {})

    async def async_load(self) -> None:
        """Load persisted records once, accepting only the expected mapping."""
        stored_data = await self._store.async_load()
        medications = (
            stored_data.get("medications", {})
            if isinstance(stored_data, dict)
            else {}
        )
        self.hass.data[DOMAIN]["medications"] = (
            medications if isinstance(medications, dict) else {}
        )

    async def async_save(self) -> None:
        """Durably write the complete medication database."""
        await self._store.async_save(
            {"medications": self.hass.data[DOMAIN]["medications"]}
        )

    def get_all(self) -> dict:
        """Return the live medication mapping."""
        return self.hass.data[DOMAIN]["medications"]

    def get_med(self, med_id: str) -> dict | None:
        """Return one medication, or None when the ID is unknown."""
        return self.get_all().get(med_id)

    def update_med(self, med_id: str, data: dict) -> None:
        """Update runtime state; callers must save or use an async helper."""
        self.get_all()[med_id] = data

    async def async_create_medication(self, med_id: str, data: dict) -> None:
        """Create a medication and save it before returning."""
        self.get_all()[med_id] = data
        await self.async_save()

    async def async_delete_medication(self, med_id: str) -> bool:
        """Delete a medication and return whether it existed."""
        if med_id not in self.get_all():
            return False
        del self.get_all()[med_id]
        await self.async_save()
        return True

    async def async_mark_taken(
        self, med_id: str, timestamp: float, quantity: int = 1
    ) -> dict | None:
        """Record a dose, clear a snooze, decrement stock, and save.

        CGPT-STAMP: Taking a dose is intentionally one durable transaction.
        """
        med = self.get_med(med_id)
        if med is None:
            return None
        med["last_taken"] = timestamp
        med["snooze_until"] = None
        if med.get("current_count") is not None:
            med["current_count"] = max(0, int(med["current_count"]) - quantity)
        self.update_med(med_id, med)
        await self.async_save()
        return med

    async def async_snooze(
        self, med_id: str, until_timestamp: float
    ) -> dict | None:
        """Snooze a known medication and save it."""
        med = self.get_med(med_id)
        if med is None:
            return None
        med["snooze_until"] = until_timestamp
        self.update_med(med_id, med)
        await self.async_save()
        return med

    async def async_refill(self, med_id: str, amount: int) -> dict | None:
        """Set the current inventory count and save it."""
        med = self.get_med(med_id)
        if med is None:
            return None
        med["current_count"] = amount
        med["refill_required"] = False
        self.update_med(med_id, med)
        await self.async_save()
        return med
