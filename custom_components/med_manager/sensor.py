"""Dynamic medication sensor platform.

CGPT-STAMP: 2026-09-21 reliable-lifecycle
A dispatcher listener refreshes existing sensors and adds/removes sensors when
medications are created or deleted, without requiring a Home Assistant restart.
"""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SIGNAL_UPDATE
from .storage import DOMAIN, MedStorage


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from storage and maintain them as storage changes."""
    storage: MedStorage = hass.data[DOMAIN]["storage"]
    entities: dict[str, MedSensor] = {}

    def _add_sensor(med_id: str) -> None:
        """Add exactly one new entity; duplicate additions are ignored."""
        if med_id in entities or storage.get_med(med_id) is None:
            return
        entity = MedSensor(storage, med_id)
        entities[med_id] = entity
        async_add_entities([entity], update_before_add=True)

    for med_id in storage.get_all():
        _add_sensor(med_id)

    @callback
    def _handle_update(med_id: str | None = None) -> None:
        """Apply dispatcher updates.

        CGPT-STAMP: This signature deliberately accepts zero or one argument;
        the old required lambda argument made zero-argument updates fail.
        """
        if med_id is not None and med_id not in entities:
            _add_sensor(med_id)

        for existing_id, entity in list(entities.items()):
            if storage.get_med(existing_id) is None:
                # CGPT-STAMP: remove deleted entities rather than leaving stale
                # dashboard state or an orphaned entity-registry record.
                entity.async_remove(force_remove=True)
                del entities[existing_id]
            else:
                entity._refresh()
                entity.async_write_ha_state()

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_UPDATE, _handle_update)
    )


class MedSensor(SensorEntity):
    """Expose a medication state and its complete stored metadata."""

    _attr_has_entity_name = True

    def __init__(self, storage: MedStorage, med_id: str) -> None:
        self._storage = storage
        self._med_id = med_id
        self._data: dict = {}
        self._refresh()

    @property
    def name(self) -> str:
        """Use a readable entity name while retaining a stable unique ID."""
        return self._data.get("common_name") or self._med_id

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._med_id}"

    @property
    def native_value(self) -> str:
        return self._data.get("status", "unknown")

    @property
    def extra_state_attributes(self) -> dict:
        """Expose state data for dashboards and automation conditions."""
        return {**self._data, "med_id": self._med_id}

    def _refresh(self) -> None:
        """Read the current record from the shared source of truth."""
        current = self._storage.get_med(self._med_id)
        if current is not None:
            self._data = current
