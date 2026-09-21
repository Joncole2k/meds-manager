# Meds Manager

Meds Manager is a Home Assistant integration for interval-based medication
tracking. It uses the time a dose was actually taken to calculate the next due
time, so late doses safely shift the rolling schedule instead of following a
fixed daily clock.

> **Beta / safety note:** This project is for reminder and record-keeping
> assistance. Validate it in your own Home Assistant instance before relying on
> it, and do not treat it as medical advice or a substitute for professional
> guidance.

## What it provides

- A Home Assistant setup flow for the first medication.
- Dynamic medication sensors with states such as `not_due`, `due_soon`,
  `due`, `overdue`, and `snoozed`.
- Durable take, snooze, refill, create, and delete actions.
- Inventory tracking and low-stock status.
- Persistent Home Assistant notifications and automation events.
- Medication data that survives restarts.

## Installation and testing

Install this repository through HACS as a custom integration, restart Home
Assistant, and add **Meds Manager** from **Settings → Devices & services**.
The first setup screen creates the integration and its first medication.
Additional medications can be created with the `med_manager.create_medication`
action. See [the testing checklist](docs/TESTING.md) before using it regularly.

## Development notes

CGPT-STAMP comments identify the 2026-09-21 reliability changes: persistent
mutations, lifecycle cleanup, dynamic sensor management, complete services, and
the removal of the recursive event bridge.
