"""AiSEG2 to MQTT Integration for Home Assistant."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from lxml import html

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Regex for number extraction
_NUM = re.compile(r'([0-9]+(?:\.[0-9]+)?)')

def _to_float(s: Optional[str]) -> float:
    """Convert string to float, handling Japanese characters."""
    if not s: 
        return 0.0
    t = s.replace('，', ',').replace('．', '.').replace(',', '')
    m = _NUM.search(t)
    return float(m.group(1)) if m else 0.0


@dataclass
class AiSeg2Config:
    """Configuration for AiSEG2 client."""
    host: str
    user: str = "aiseg"
    password: str = ""
    timeout: float = 10.0


class AiSeg2Client:
    """Async client for AiSEG2 pages (Digest auth)."""
    
    def __init__(self, cfg: AiSeg2Config):
        """Initialize the client."""
        self._cfg = cfg
        self._client = httpx.AsyncClient(
            base_url=f"http://{cfg.host}",
            timeout=cfg.timeout,
            auth=httpx.DigestAuth(cfg.user, cfg.password),
            headers={"User-Agent": "aiseg2/ha-integration"}
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def _get_html_texts(self, path: str, xpath: str) -> List[str]:
        """Fetch HTML and extract text using XPath."""
        r = await self._client.get(path)
        r.raise_for_status()
        root = html.fromstring(r.content)
        return [t for t in root.xpath(xpath) if isinstance(t, str)]

    async def fetch_totals(self) -> Dict[str, float]:
        """Fetch today's total energy values (kWh)."""
        return {
            "total_use_kwh": _to_float((await self._get_html_texts("/page/graph/52111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/52111", '//span[@id="val_kwh"]/text()')) else None),
            "buy_kwh":       _to_float((await self._get_html_texts("/page/graph/53111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/53111", '//span[@id="val_kwh"]/text()')) else None),
            "sell_kwh":      _to_float((await self._get_html_texts("/page/graph/54111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/54111", '//span[@id="val_kwh"]/text()')) else None),
            "gen_kwh":       _to_float((await self._get_html_texts("/page/graph/51111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/51111", '//span[@id="val_kwh"]/text()')) else None),
        }

    async def fetch_circuit_catalog(self) -> List[Dict[str, str]]:
        """Fetch list of available circuits."""
        r = await self._client.get("/page/setting/installation/734")
        r.raise_for_status()
        root = html.fromstring(r.content)
        scripts = root.xpath('//script[contains(text(), "window.onload")]')
        if not scripts: 
            return []
        text = scripts[0].text or ""
        l, rpos = text.find('('), text.rfind(')')
        if l < 0 or rpos <= l: 
            return []
        data = json.loads(text[l+1:rpos].strip())
        out: List[Dict[str,str]] = []
        for c in data.get('arrayCircuitNameList', []):
            if c.get('strBtnType') == "1":
                cid = str(c.get('strId'))
                name = str(c.get('strCircuit') or f"Circuit {cid}")
                out.append({"id": cid, "name": name})
        return out

    async def fetch_circuit_kwh(self, circuit_id: str) -> float:
        """Fetch energy consumption for a specific circuit."""
        params = {"circuitid": str(circuit_id)}
        b64 = base64.b64encode(json.dumps(params).encode()).decode()
        r = await self._client.get(f"/page/graph/584?data={b64}")
        r.raise_for_status()
        root = html.fromstring(r.content)
        vals = root.xpath('//span[@id="val_kwh"]/text()')
        return _to_float(vals[0] if vals else None)


class AiSeg2DataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from AiSEG2."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AiSeg2Client,
        scan_interval: int,
    ) -> None:
        """Initialize the data update coordinator."""
        self.client = client
        self.circuits: List[Dict[str, str]] = []
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from AiSEG2."""
        try:
            # Fetch circuits if not already cached
            if not self.circuits:
                self.circuits = await self.client.fetch_circuit_catalog()
                _LOGGER.debug("Found %d circuits", len(self.circuits))

            # Fetch total energy values
            totals = await self.client.fetch_totals()
            
            # Fetch per-circuit values
            circuit_data = {}
            for circuit in self.circuits:
                circuit_id = circuit["id"]
                circuit_data[circuit_id] = {
                    "name": circuit["name"],
                    "kwh": await self.client.fetch_circuit_kwh(circuit_id),
                }
            
            # Calculate last reset (today at midnight JST)
            jst = timezone(timedelta(hours=9))
            now = datetime.now(jst)
            last_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            return {
                "totals": totals,
                "circuits": circuit_data,
                "last_reset": last_reset.isoformat(),
                "timestamp": now.isoformat(),
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with AiSEG2: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AiSEG2 from a config entry."""
    config = AiSeg2Config(
        host=entry.data["host"],
        user=entry.data["username"],
        password=entry.data["password"],
    )
    
    client = AiSeg2Client(config)
    
    # Test the connection
    try:
        await client.fetch_totals()
    except Exception as ex:
        await client.close()
        raise ConfigEntryNotReady(f"Cannot connect to AiSEG2: {ex}") from ex
    
    # Create the data update coordinator
    coordinator = AiSeg2DataUpdateCoordinator(
        hass,
        client,
        entry.options.get("scan_interval", 300),
    )
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Get coordinator
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # Close the client
        await coordinator.client.close()
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)