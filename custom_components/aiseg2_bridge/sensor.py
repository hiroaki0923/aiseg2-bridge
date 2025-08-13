from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

JST = timezone(timedelta(hours=9))

TOTAL_KEYS = [
    ("total_use_kwh", "Total Energy Today"),
    ("buy_kwh", "Purchased Energy Today"),
    ("sell_kwh", "Sold Energy Today"),
    ("gen_kwh", "Generated Energy Today"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data["host"]

    ents = []
    # 合計系
    for key, name in TOTAL_KEYS:
        ents.append(TotalEnergySensor(coordinator, entry, host, key, name))

    # 回路系
    if coordinator.data:
        circuits = coordinator.data.get("circuits", {})
        for cid, cdata in circuits.items():
            ents.append(CircuitEnergySensor(coordinator, entry, host, cid, cdata["name"]))

    async_add_entities(ents)


class _Base(CoordinatorEntity, SensorEntity):
    _attr_device_class = "energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = "total"  # デイリーでリセットされる累積
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, host: str):
        super().__init__(coordinator)
        self._host = host
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}-{self._host}")},
            "name": f"AiSEG2 ({self._host})",
            "manufacturer": "Panasonic",
            "model": "AiSEG2",
        }

    @property
    def last_reset(self) -> datetime:
        now = datetime.now(JST)
        return now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=JST)


class TotalEnergySensor(_Base):
    def __init__(self, coordinator, entry: ConfigEntry, host: str, key: str, disp_name: str):
        super().__init__(coordinator, entry, host)
        self._key = key
        self._attr_name = disp_name
        self._attr_unique_id = f"{DOMAIN}-{host}-{key}"
        # Set explicit entity_id (use underscore format of key)
        self.entity_id = f"sensor.aiseg2_bridge_{key.replace('_kwh', '')}"

    @property
    def native_value(self) -> Optional[float]:
        totals = self.coordinator.data.get("totals", {})
        v = totals.get(self._key)
        return float(v) if v is not None else None


class CircuitEnergySensor(_Base):
    def __init__(self, coordinator, entry: ConfigEntry, host: str, cid: str, cname: str):
        super().__init__(coordinator, entry, host)
        self._cid = str(cid)
        self._cname = cname
        self._attr_name = cname
        self._attr_unique_id = f"{DOMAIN}-{host}-c{self._cid}"
        # Set explicit entity_id
        self.entity_id = f"sensor.aiseg2_bridge_c{self._cid}"

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        circuits = self.coordinator.data.get("circuits", {})
        circuit_data = circuits.get(self._cid)
        if circuit_data:
            return float(circuit_data.get("kwh", 0))
        return None
