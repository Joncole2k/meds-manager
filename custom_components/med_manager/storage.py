"""
HA Meds Manager - Storage Layer (FINAL PRODUCT MODEL)

This file defines the COMPLETE medication data structure used across:
- Engine (scheduling + evaluation)
- Services (take / snooze / refill / create / delete)
- Notifications
- Future entities (sensor.med_*)
- Future UI dashboards (Lovelace cards)

This is the SINGLE SOURCE OF TRUTH for all medication state.
"""

from datetime import datetime, timezone  # Timestamp handling

from homeassistant.core import HomeAssistant  # Home Assistant access
from homeassistant.helpers.storage import Store  # Home Assistant persistent storage


# ---------------------------------------------------------
# DOMAIN IDENTIFIER
# ---------------------------------------------------------
DOMAIN = "med_manager"

# ---------------------------------------------------------
# STORAGE VERSION
# ---------------------------------------------------------
STORAGE_VERSION = 1

# ---------------------------------------------------------
# STORAGE KEY
# ---------------------------------------------------------
STORAGE_KEY = "medications"


class MedStorage:
    """
    Central medication storage system.

    This class handles:
    - persistence via Home Assistant storage
    - full medication schema storage
    - state tracking for engine + UI + entities
    """

    def __init__(self, hass: HomeAssistant):
        # Store Home Assistant instance
        self.hass = hass

        # ---------------------------------------------------------
        # PERSISTENT STORAGE
        # ---------------------------------------------------------
        # Home Assistant stores this data in its .storage directory.
        # The data survives Home Assistant restarts.
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{STORAGE_KEY}",
        )

        # ---------------------------------------------------------
        # INTEGRATION NAMESPACE
        # ---------------------------------------------------------
        # Runtime references are still kept in hass.data so the
        # engine, services, and entities can access the same data.
        self.hass.data.setdefault(DOMAIN, {})

        # ---------------------------------------------------------
        # MEDICATION STORE
        # ---------------------------------------------------------
        # This is populated by async_load() during integration startup.
        self.hass.data[DOMAIN].setdefault("medications", {})

    # ---------------------------------------------------------
    # PERSISTENCE INITIALIZATION
    # ---------------------------------------------------------

    async def async_load(self):
        """
        Load medication data from Home Assistant persistent storage.

        This must be called once during integration startup before
        the medication engine or entities begin using the data.
        """

        # ---------------------------------------------------------
        # LOAD PERSISTED DATA
        # ---------------------------------------------------------
        stored_data = await self._store.async_load()

        # ---------------------------------------------------------
        # VALIDATE STORED DATA
        # ---------------------------------------------------------
        if isinstance(stored_data, dict):
            medications = stored_data.get("medications", {})

            if isinstance(medications, dict):
                self.hass.data[DOMAIN]["medications"] = medications
                return

        # ---------------------------------------------------------
        # INITIAL EMPTY STATE
        # ---------------------------------------------------------
        # No medication data exists yet.
        #
        # IMPORTANT:
        # We intentionally do NOT create demo medication here.
        # A new installation should start empty and only contain
        # medications that the user actually creates.
        self.hass.data[DOMAIN]["medications"] = {}

        await self.async_save()

    # ---------------------------------------------------------
    # PERSISTENT SAVE
    # ---------------------------------------------------------

    async def async_save(self):
        """
        Save the current medication database to persistent storage.
        """

        # ---------------------------------------------------------
        # BUILD STORAGE DATA
        # ---------------------------------------------------------
        data = {
            "medications": self.hass.data[DOMAIN]["medications"]
        }

        # ---------------------------------------------------------
        # WRITE STORAGE
        # ---------------------------------------------------------
        await self._store.async_save(data)

    # ---------------------------------------------------------
    # CORE ACCESS METHODS
    # ---------------------------------------------------------

    def get_all(self):
        """Return all medication records."""
        return self.hass.data[DOMAIN]["medications"]

    def get_med(self, med_id):
        """Get single medication record."""
        return self.hass.data[DOMAIN]["medications"].get(med_id)

    def update_med(self, med_id, data):
        """Update full medication record."""
        self.hass.data[DOMAIN]["medications"][med_id] = data

    # ---------------------------------------------------------
    # USER ACTION METHODS (SERVICES)
    # ---------------------------------------------------------

    def mark_taken(self, med_id, timestamp):
        """User action: medication taken."""
        med = self.get_med(med_id)
        if not med:
            return

        med["last_taken"] = timestamp
        med["snooze_until"] = None

        self.update_med(med_id, med)

    # ---------------------------------------------------------
    # USER ACTION PERSISTENCE
    # ---------------------------------------------------------

    async def async_mark_taken(self, med_id, timestamp):
        """User action: medication taken with persistent storage."""
        self.mark_taken(med_id, timestamp)
        await self.async_save()

    def snooze(self, med_id, until_timestamp):
        """User action: snooze medication alerts."""
        med = self.get_med(med_id)
        if not med:
            return

        med["snooze_until"] = until_timestamp
        self.update_med(med_id, med)

    # ---------------------------------------------------------
    # USER ACTION PERSISTENCE
    # ---------------------------------------------------------

    async def async_snooze(self, med_id, until_timestamp):
        """User action: snooze medication alerts with persistent storage."""
        self.snooze(med_id, until_timestamp)
        await self.async_save()

    def mark_notified(self, med_id, timestamp):
        """Engine action: tracks notifications to prevent spam."""
        med = self.get_med(med_id)
        if not med:
            return

        med["last_notified"] = timestamp
        med["notification_count"] = med.get("notification_count", 0) + 1

        self.update_med(med_id, med)

    # ---------------------------------------------------------
    # ENGINE PERSISTENCE
    # ---------------------------------------------------------

    async def async_mark_notified(self, med_id, timestamp):
        """Engine action: notification tracking with persistent storage."""
        self.mark_notified(med_id, timestamp)
        await self.async_save()

    # ---------------------------------------------------------
    # INVENTORY / REFILL SYSTEM
    # ---------------------------------------------------------

    def refill(self, med_id, amount):
        """Update medication inventory after refill."""
        med = self.get_med(med_id)
        if not med:
            return

        med["current_count"] = amount
        med["refill_required"] = False

        self.update_med(med_id, med)

    # ---------------------------------------------------------
    # INVENTORY PERSISTENCE
    # ---------------------------------------------------------

    async def async_refill(self, med_id, amount):
        """Update medication inventory with persistent storage."""
        self.refill(med_id, amount)
        await self.async_save()

    # ---------------------------------------------------------
    # CREATE / DELETE MEDICATION
    # ---------------------------------------------------------

    def create_medication(self, med_id, data):
        """Create a new medication entry."""
        self.hass.data[DOMAIN]["medications"][med_id] = data

    # ---------------------------------------------------------
    # CREATE PERSISTENCE
    # ---------------------------------------------------------

    async def async_create_medication(self, med_id, data):
        """Create a new medication entry with persistent storage."""
        self.create_medication(med_id, data)
        await self.async_save()

    def delete_medication(self, med_id):
        """Delete medication entry."""
        if med_id in self.hass.data[DOMAIN]["medications"]:
            del self.hass.data[DOMAIN]["medications"][med_id]

    # ---------------------------------------------------------
    # DELETE PERSISTENCE
    # ---------------------------------------------------------

    async def async_delete_medication(self, med_id):
        """Delete medication entry with persistent storage."""
        self.delete_medication(med_id)
        await self.async_save()
