"""HA Meds Manager - Entity Layer (FINAL)

This file exposes medications as Home Assistant entities.

===========================================================
PURPOSE
===========================================================
Transforms stored medication data into:
- sensor.med_* entities
- UI-visible attributes
- real-time state updates

===========================================================
UI OUTPUT
===========================================================
Each medication becomes a sensor with:
- state = medication status
- attributes = full medication metadata

===========================================================
ACTION MODEL
===========================================================
Actions are NOT handled here directly.
They are routed through:
- services in __init__.py
- engine in coordinator.py
"""

from homeassistant.components.sensor import SensorEntity  # HA sensor base class
from homeassistant.core import HomeAssistant, callback  # HA system reference + callback support
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # HA entity registration
from homeassistant.config_entries import ConfigEntry  # HA config entry reference
from homeassistant.helpers.dispatcher import async_dispatcher_connect  # Real-time update support

from .storage import MedStorage  # shared data layer


# ---------------------------------------------------------
# DOMAIN IDENTIFIER
# ---------------------------------------------------------
DOMAIN = "med_manager"


# ---------------------------------------------------------
# DISPATCHER SIGNAL
# ---------------------------------------------------------
# This signal is sent whenever medication data changes.
# The engine/services will use this signal to tell entities
# that they need to refresh their state.
SIGNAL_UPDATE = "med_manager_update"


# ---------------------------------------------------------
# ENTITY PLATFORM SETUP
# ---------------------------------------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """
    Creates sensor entities for all medications.

    This runs when the Meds Manager config entry is loaded
    and builds the initial entity list from storage.
    """

    # ---------------------------------------------------------
    # STORAGE INITIALIZATION
    # ---------------------------------------------------------
    storage = MedStorage(hass)

    # ---------------------------------------------------------
    # LOAD ALL MEDICATIONS
    # ---------------------------------------------------------
    meds = storage.get_all()

    # ---------------------------------------------------------
    # ENTITY LIST BUILD
    # ---------------------------------------------------------
    entities = []

    for med_id, med in meds.items():
        entities.append(MedSensor(hass, storage, med_id, med))

    # ---------------------------------------------------------
    # REGISTER ENTITIES
    # ---------------------------------------------------------
    async_add_entities(entities, True)

    # ---------------------------------------------------------
    # DISPATCHER UPDATE SUPPORT
    # ---------------------------------------------------------
    # Listen for medication changes from the engine/services.
    # When received, refresh every existing medication entity.
    @callback
    def _handle_update(*_):
        """Refresh all medication entities after a data change."""

        for entity in entities:
            entity._refresh()
            entity.async_write_ha_state()

    # ---------------------------------------------------------
    # REGISTER DISPATCHER LISTENER
    # ---------------------------------------------------------
    # Home Assistant automatically removes this listener when
    # the config entry is unloaded.
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_UPDATE,
            _handle_update,
        )
    )


# ---------------------------------------------------------
# MEDICATION SENSOR ENTITY
# ---------------------------------------------------------
class MedSensor(SensorEntity):
    """
    Represents a single medication as a Home Assistant sensor.

    State:
        - due
        - due_soon
        - overdue
        - not_due
        - snoozed
        - not_initialized

    Attributes:
        - full medication metadata
        - scheduling data
        - inventory data
    """

    def __init__(self, hass, storage, med_id, data):
        # ---------------------------------------------------------
        # CORE REFERENCES
        # ---------------------------------------------------------
        self._hass = hass
        self._storage = storage
        self._med_id = med_id
        self._data = data

    # ---------------------------------------------------------
    # ENTITY IDENTITY
    # ---------------------------------------------------------

    @property
    def name(self):
        # Medication IDs already contain the unique medication
        # identifier, so do not add another "med_" prefix here.
        return self._med_id

    @property
    def unique_id(self):
        # Unique ID remains stable for the lifetime of the medication.
        return f"med_manager_{self._med_id}"

    # ---------------------------------------------------------
    # STATE VALUE
    # ---------------------------------------------------------

    @property
    def state(self):
        return self._data.get("status", "unknown")

    # ---------------------------------------------------------
    # ATTRIBUTES (FULL DATA EXPOSURE)
    # ---------------------------------------------------------

    @property
    def extra_state_attributes(self):
        return {
            # -------------------------------------------------
            # IDENTITY
            # -------------------------------------------------
            "common_name": self._data.get("common_name"),
            "generic_name": self._data.get("generic_name"),
            "brand_name": self._data.get("brand_name"),
            "person": self._data.get("person"),

            # -------------------------------------------------
            # SCHEDULING
            # -------------------------------------------------
            "interval_hours": self._data.get("interval_hours"),
            "last_taken": self._data.get("last_taken"),
            "next_due": self._data.get("next_due"),

            # -------------------------------------------------
            # USER STATE
            # -------------------------------------------------
            "snooze_until": self._data.get("snooze_until"),

            # -------------------------------------------------
            # NOTIFICATIONS
            # -------------------------------------------------
            "last_notified": self._data.get("last_notified"),

            # -------------------------------------------------
            # INVENTORY
            # -------------------------------------------------
            "current_count": self._data.get("current_count"),
            "low_stock_threshold": self._data.get("low_stock_threshold"),
            "refill_required": self._data.get("refill_required"),

            # -------------------------------------------------
            # UI / ENGINE DEBUG
            # -------------------------------------------------
            "entity_id": self._med_id,
        }

    # ---------------------------------------------------------
    # AUTO REFRESH SUPPORT
    # ---------------------------------------------------------

    def _refresh(self):
        """
        Pull the latest medication state from storage.
        """

        # ---------------------------------------------------------
        # REFRESH LOCAL STATE
        # ---------------------------------------------------------
        latest_data = self._storage.get_med(self._med_id)

        # ---------------------------------------------------------
        # UPDATE LOCAL DATA
        # ---------------------------------------------------------
        if latest_data is not None:
            self._data = latest_data
