# Meds Manager beta testing checklist

<!-- CGPT-STAMP: 2026-09-21 reliable-lifecycle -->

Run these checks on a non-production Home Assistant instance before relying on
the integration.

1. Install or update through HACS, restart Home Assistant, then add **Meds
   Manager** from **Settings → Devices & services**. Confirm the first
   medication sensor appears.
2. Restart Home Assistant once more. Confirm the medication and its attributes
   are still present.
3. Run `med_manager.take` with its `med_id`. Confirm its state changes
   immediately, `last_taken` is updated, and inventory drops by the requested
   `quantity`.
4. Restart again. Confirm the taken time, next due time, status, and inventory
   persist.
5. Run `med_manager.snooze` and confirm the state becomes `snoozed`.
   Restart and confirm the snooze remains. After it expires, confirm normal
   due-state evaluation resumes.
6. Run `med_manager.refill`; verify inventory and the refill warning update
   immediately and survive restart.
7. Run `med_manager.create_medication`. Confirm its sensor is created
   without restarting Home Assistant. Run `med_manager.delete_medication`
   and confirm the sensor disappears.
8. Reload the integration from its configuration page. Confirm there is one
   set of services, one sensor per medication, and no repeating errors in
   **Settings → System → Logs**.
9. When a test medicine becomes due, verify one persistent notification appears
   and that repeated notifications follow the intended 15-minute cooldown.

Record any unexpected logs, duplicated entities, lost state, or missed
notifications before using the integration for regular reminders.
