"""
HA Meds Manager - Final Integration Bootstrap

This file is the MAIN ENTRY POINT for Home Assistant.

===========================================================
CORE SYSTEM BOOTSTRAP
===========================================================
- initializes storage layer
- initializes engine layer
- wires runtime dependencies

===========================================================
SERVICE LAYER (USER ACTIONS)
===========================================================
- mark medication as taken
- snooze medication alerts
- refill medication inventory

===========================================================
EVENT SYSTEM BINDING
===========================================================
- listens to engine events
- bridges engine → Home Assistant event bus

===========================================================
FUTURE UI / ENTITY SYSTEM SUPPORT
===========================================================
- prepares structure for sensor.med_*
- ensures compatibility with Lovelace dashboards
"""

from datetime import datetime, timezone

from homeassistant.core import HomeAssistant, ServiceCall

from .storage import MedStorage
from .coordinator import MedEngine


# ---------------------------------------------------------
# DOMAIN IDENTIFIER
# ---------------------------------------------------------
DOMAIN = "med_manager"


# ---------------------------------------------------------
# INTEGRATION SETUP ENTRYPOINT
# ---------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry):
    """Initialize Meds Manager from UI (HACS install path)."""

    # ---------------------------------------------------------
    # CORE NAMESPACE INITIALIZATION
    # ---------------------------------------------------------
    hass.data.setdefault(DOMAIN, {})

    # ---------------------------------------------------------
    # STORAGE INITIALIZATION
    # ---------------------------------------------------------
    storage = MedStorage(hass)

    # ---------------------------------------------------------
    # LOAD PERSISTENT MEDICATION DATA
    # ---------------------------------------------------------
    # Load medications from Home Assistant persistent storage
    # before starting the engine or creating entities.
    await storage.async_load()

    hass.data[DOMAIN]["storage"] = storage

    # ---------------------------------------------------------
    # ENGINE INITIALIZATION
    # ---------------------------------------------------------
    engine = MedEngine(hass)
    hass.data[DOMAIN]["engine"] = engine

    await engine.async_start()

    # ---------------------------------------------------------
    # SERVICE: TAKE MEDICATION
    # ---------------------------------------------------------
    async def handle_take(call: ServiceCall):
        """Mark medication as taken."""

        med_id = call.data.get("med_id")
        now = datetime.now(timezone.utc).timestamp()

        storage.mark_taken(med_id, now)

        # ---------------------------------------------------------
        # IMMEDIATE ENGINE RE-EVALUATION
        # ---------------------------------------------------------
        # Normally the engine evaluates medications every 30 seconds.
        # Running a cycle here immediately updates the medication
        # status and sends the entity update signal.
        engine._tick()

        print(f"[MED SERVICE] TAKE -> {med_id}")

    # ---------------------------------------------------------
    # SERVICE: SNOOZE MEDICATION
    # ---------------------------------------------------------
    async def handle_snooze(call: ServiceCall):
        """Snooze medication reminders."""

        med_id = call.data.get("med_id")
        minutes = call.data.get("minutes", 0)

        snooze_until = datetime.now(timezone.utc).timestamp() + (minutes * 60)

        storage.snooze(med_id, snooze_until)

        print(f"[MED SERVICE] SNOOZE -> {med_id} ({minutes} min)")

    # ---------------------------------------------------------
    # SERVICE: REFILL MEDICATION
    # ---------------------------------------------------------
    async def handle_refill(call: ServiceCall):
        """Refill medication inventory."""

        med_id = call.data.get("med_id")
        amount = call.data.get("amount", 0)

        storage.refill(med_id, amount)

        print(f"[MED SERVICE] REFILL -> {med_id} ({amount})")

    # ---------------------------------------------------------
    # REGISTER SERVICES
    # ---------------------------------------------------------
    hass.services.async_register(DOMAIN, "take", handle_take)
    hass.services.async_register(DOMAIN, "snooze", handle_snooze)
    hass.services.async_register(DOMAIN, "refill", handle_refill)

    # ---------------------------------------------------------
    # EVENT BRIDGE
    # ---------------------------------------------------------

    def _event_listener(event):
        """Bridge engine events into HA event bus."""

        event_type = getattr(event, "event_type", None)
        data = getattr(event, "data", None)

        if not event_type:
            return

        print(f"[MED EVENT] {event_type} -> {data}")

        hass.bus.fire(event_type, data)

    # Listen to engine events
    hass.bus.async_listen("med_manager_due", _event_listener)
    hass.bus.async_listen("med_manager_due_soon", _event_listener)
    hass.bus.async_listen("med_manager_overdue", _event_listener)
    hass.bus.async_listen("med_manager_snoozed", _event_listener)

    # ---------------------------------------------------------
    # CRITICAL: FORWARD TO SENSOR PLATFORM
    # ---------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor"]
    )

    # ---------------------------------------------------------
    # FINAL STARTUP CONFIRMATION
    # ---------------------------------------------------------
    print("[MED MANAGER] Integration fully initialized and running")

    return True
