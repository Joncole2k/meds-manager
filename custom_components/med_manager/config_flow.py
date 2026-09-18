"""
HA Meds Manager - Config Flow (UI Setup + Medication Creator)

===========================================================
PURPOSE
===========================================================
This file defines the Home Assistant UI setup flow.

It is responsible for:
- Initial integration setup in HA UI
- Providing "Add Medication" wizard
- Creating medication entries in storage

===========================================================
ARCHITECTURE ROLE
===========================================================
This is the USER INTERFACE LAYER for setup:

UI → Config Flow → Storage → Engine → Entities

===========================================================
"""

# ---------------------------------------------------------
# HOME ASSISTANT CONFIG FLOW IMPORTS
# ---------------------------------------------------------
import voluptuous as vol  # schema validation for UI forms

import uuid  # used for auto-generating medication IDs

from homeassistant import config_entries  # base config flow system

# ---------------------------------------------------------
# LOCAL INTEGRATION IMPORTS
# ---------------------------------------------------------
from .storage import MedStorage  # shared medication storage layer

# ---------------------------------------------------------
# DOMAIN IDENTIFIER
# ---------------------------------------------------------
DOMAIN = "med_manager"


# =========================================================
# CONFIG FLOW CLASS (MAIN ENTRY POINT FOR UI)
# =========================================================
class MedManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handles UI setup and medication creation wizard.

    This class defines the full onboarding experience for:
    - First-time integration setup
    - Adding medications via UI wizard
    """

    # -----------------------------------------------------
    # VERSION TRACKING
    # -----------------------------------------------------
    VERSION = 1

    # -----------------------------------------------------
    # INITIALIZATION
    # -----------------------------------------------------
    def __init__(self):
        # Storage reference (lazy-initialized)
        self._storage = None

        # Wizard state (used to pass data between steps)
        self._wizard = {}

    # =====================================================
    # STEP 1 - MAIN MENU
    # =====================================================
    async def async_step_user(self, user_input=None):
        """
        First screen shown in Home Assistant UI.

        This acts as the entry menu:
        - Add Medication
        - Exit Setup
        """

        # -------------------------------------------------
        # INIT STORAGE (LAZY LOAD SAFETY)
        # -------------------------------------------------
        if self._storage is None:
            self._storage = MedStorage(self.hass)

        # -------------------------------------------------
        # HANDLE USER INPUT
        # -------------------------------------------------
        if user_input is not None:

            # USER SELECTED: GO DIRECTLY TO MEDICATION FLOW
            return await self.async_step_add_medication()

        # -------------------------------------------------
        # UI FORM DEFINITION (ENTRY SCREEN)
        # -------------------------------------------------
        schema = vol.Schema({
            vol.Required("action", default="add_medication"): vol.In({
                "add_medication": "Add Medication",
                "finish": "Exit Setup"
            })
        })

        # -------------------------------------------------
        # RENDER FORM
        # -------------------------------------------------
        return self.async_show_form(
            step_id="user",
            data_schema=schema
        )

    # =====================================================
    # STEP 2 - ADD MEDICATION FORM
    # =====================================================
    async def async_step_add_medication(self, user_input=None):
        """
        Medication creation wizard.

        This step:
        - collects medication info from UI
        - auto-generates medication ID
        - stores in MedStorage
        - prepares engine + entity consumption
        """

        # -------------------------------------------------
        # HANDLE FORM SUBMISSION
        # -------------------------------------------------
        if user_input is not None:

            # -------------------------------------------------
            # STORAGE INSTANCE (SAFE REFERENCE)
            # -------------------------------------------------
            storage = self._storage or MedStorage(self.hass)

            # -------------------------------------------------
            # REQUIRED USER INPUTS
            # -------------------------------------------------
            common_name = user_input["common_name"]
            person = user_input["person"]
            interval_hours = user_input["interval_hours"]

            # -------------------------------------------------
            # AUTO-GENERATE MEDICATION ID
            # -------------------------------------------------
            safe_name = common_name.lower().replace(" ", "_")[:20]
            short_id = uuid.uuid4().hex[:5]
            med_id = f"med_{person}_{safe_name}_{short_id}"

            # -------------------------------------------------
            # STORE WIZARD CONTEXT
            # -------------------------------------------------
            self._wizard = {
                "med_id": med_id,
                "person": person,
                "common_name": common_name
            }

            # -------------------------------------------------
            # BUILD MEDICATION DATA STRUCTURE
            # -------------------------------------------------
            data = {
                # ---------------------------------------------
                # IDENTITY LAYER
                # ---------------------------------------------
                "common_name": common_name,
                "generic_name": user_input.get("generic_name"),
                "brand_name": user_input.get("brand_name"),
                "person": person,

                # ---------------------------------------------
                # SCHEDULING LAYER
                # ---------------------------------------------
                "interval_hours": interval_hours,
                "last_taken": None,
                "next_due": None,

                # ---------------------------------------------
                # ENGINE STATE
                # ---------------------------------------------
                "status": "not_initialized",
                "should_notify": False,

                # ---------------------------------------------
                # USER STATE
                # ---------------------------------------------
                "snooze_until": None,

                # ---------------------------------------------
                # NOTIFICATION STATE
                # ---------------------------------------------
                "last_notified": None,
                "notification_count": 0,

                # ---------------------------------------------
                # INVENTORY STATE
                # ---------------------------------------------
                "current_count": user_input.get("current_count", 0),
                "low_stock_threshold": user_input.get("low_stock_threshold", 5),
                "refill_required": False,
            }

            # -------------------------------------------------
            # STORE MEDICATION
            # -------------------------------------------------
            # Save the medication both to runtime storage and
            # Home Assistant persistent storage.
            await storage.async_create_medication(med_id, data)

            # -------------------------------------------------
            # FINISH FLOW (CREATE CONFIG ENTRY)
            # -------------------------------------------------
            return self.async_create_entry(
                title=f"{common_name} ({person})",
                data={"med_id": med_id}
            )

        # -------------------------------------------------
        # UI FORM (MEDICATION INPUT)
        # -------------------------------------------------
        schema = vol.Schema({
            # ---------------------------------------------
            # REQUIRED FIELDS
            # ---------------------------------------------
            vol.Required("common_name"): str,
            vol.Required("person"): str,
            vol.Required("interval_hours"): int,

            # ---------------------------------------------
            # OPTIONAL FIELDS
            # ---------------------------------------------
            vol.Optional("generic_name"): str,
            vol.Optional("brand_name"): str,

            vol.Optional("current_count", default=0): int,
            vol.Optional("low_stock_threshold", default=5): int,
        })

        # -------------------------------------------------
        # RENDER FORM
        # -------------------------------------------------
        return self.async_show_form(
            step_id="add_medication",
            data_schema=schema
        )
