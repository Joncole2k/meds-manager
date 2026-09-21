"""Initial one-time configuration flow for Meds Manager.

CGPT-STAMP: 2026-09-21 reliable-lifecycle
The config flow creates one integration entry. Additional medications belong in
the create_medication service, preventing duplicate engines and sensors.
"""

import uuid

import voluptuous as vol
from homeassistant import config_entries

from .storage import MedStorage

DOMAIN = "med_manager"


class MedManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Collect the first medication while creating the one integration entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show first-medication form or refuse a duplicate integration."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            storage = MedStorage(self.hass)
            safe_name = user_input["common_name"].lower().replace(" ", "_")[:20]
            med_id = f"med_{user_input['person']}_{safe_name}_{uuid.uuid4().hex[:5]}"

            # CGPT-STAMP: persist before the entry is created and loaded.
            await storage.async_create_medication(
                med_id,
                {
                    "common_name": user_input["common_name"],
                    "generic_name": user_input.get("generic_name"),
                    "brand_name": user_input.get("brand_name"),
                    "person": user_input["person"],
                    "interval_hours": user_input["interval_hours"],
                    "last_taken": None,
                    "next_due": None,
                    "status": "not_initialized",
                    "snooze_until": None,
                    "last_notified": None,
                    "notification_count": 0,
                    "current_count": user_input.get("current_count", 0),
                    "low_stock_threshold": user_input.get("low_stock_threshold", 5),
                    "refill_required": False,
                },
            )
            return self.async_create_entry(title="Meds Manager", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("common_name"): str,
                vol.Required("person"): str,
                vol.Required("interval_hours"): vol.All(int, vol.Range(min=1)),
                vol.Optional("generic_name"): str,
                vol.Optional("brand_name"): str,
                vol.Optional("current_count", default=0): vol.All(int, vol.Range(min=0)),
                vol.Optional("low_stock_threshold", default=5): vol.All(int, vol.Range(min=0)),
            }),
        )
