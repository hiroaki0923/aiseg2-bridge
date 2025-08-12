from __future__ import annotations
import base64, json, re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from lxml import html

_NUM = re.compile(r'([0-9]+(?:\.[0-9]+)?)')

def _to_float(s: Optional[str]) -> float:
    if not s: return 0.0
    t = s.replace('，', ',').replace('．', '.').replace(',', '')
    m = _NUM.search(t)
    return float(m.group(1)) if m else 0.0

@dataclass
class AiSeg2Config:
    host: str
    user: str = "aiseg"
    password: str = ""
    timeout: float = 10.0

class AiSeg2Client:
    """Async client for AiSEG2 pages (Digest auth)"""
    def __init__(self, cfg: AiSeg2Config):
        self._cfg = cfg
        self._client = httpx.AsyncClient(
            base_url=f"http://{cfg.host}",
            timeout=cfg.timeout,
            auth=httpx.DigestAuth(cfg.user, cfg.password),
            headers={"User-Agent": "aiseg2/ha-integration"}
        )

    async def close(self):
        await self._client.aclose()

    async def _get_html_texts(self, path: str, xpath: str) -> List[str]:
        r = await self._client.get(path)
        r.raise_for_status()
        root = html.fromstring(r.content)
        return [t for t in root.xpath(xpath) if isinstance(t, str)]

    async def fetch_totals(self) -> Dict[str, float]:
        # 今日の使用/買電/売電/発電 (kWh)
        return {
            "total_use_kwh": _to_float((await self._get_html_texts("/page/graph/52111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/52111", '//span[@id="val_kwh"]/text()')) else None),
            "buy_kwh":       _to_float((await self._get_html_texts("/page/graph/53111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/53111", '//span[@id="val_kwh"]/text()')) else None),
            "sell_kwh":      _to_float((await self._get_html_texts("/page/graph/54111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/54111", '//span[@id="val_kwh"]/text()')) else None),
            "gen_kwh":       _to_float((await self._get_html_texts("/page/graph/51111", '//span[@id="val_kwh"]/text()'))[:1][0] if (await self._get_html_texts("/page/graph/51111", '//span[@id="val_kwh"]/text()')) else None),
        }

    async def fetch_circuit_catalog(self) -> List[Dict[str, str]]:
        r = await self._client.get("/page/setting/installation/734")
        r.raise_for_status()
        root = html.fromstring(r.content)
        scripts = root.xpath('//script[contains(text(), "window.onload")]')
        if not scripts: return []
        text = scripts[0].text or ""
        l, rpos = text.find('('), text.rfind(')')
        if l < 0 or rpos <= l: return []
        data = json.loads(text[l+1:rpos].strip())
        out: List[Dict[str,str]] = []
        for c in data.get('arrayCircuitNameList', []):
            if c.get('strBtnType') == "1":
                cid = str(c.get('strId'))
                name = str(c.get('strCircuit') or f"Circuit {cid}")
                out.append({"id": cid, "name": name})
        return out

    async def fetch_circuit_kwh(self, circuit_id: str) -> float:
        params = {"circuitid": str(circuit_id)}
        b64 = base64.b64encode(json.dumps(params).encode()).decode()
        r = await self._client.get(f"/page/graph/584?data={b64}")
        r.raise_for_status()
        root = html.fromstring(r.content)
        vals = root.xpath('//span[@id="val_kwh"]/text()')
        return _to_float(vals[0] if vals else None)
