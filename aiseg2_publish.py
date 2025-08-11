#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AISEG2 → MQTT Discovery (per-circuit daily kWh)
- ブログ記載コードと等価のスクレイピング手順
  * 各リクエストごとに HTTPDigestAuth を付与
  * 総量: /page/graph/52111, 53111, 54111, 51111 の <span id="val_kwh"> 先頭
  * 回路一覧: /page/setting/installation/734 の window.onload JSON(arrayCircuitNameList, strBtnType=="1")
  * 回路kWh: /page/graph/584?data=base64({"circuitid":"NN"}) の <span id="val_kwh"> 先頭
- MQTT:
  * Discovery/config は retain=True
  * state も retain=True（初回/再起動時に確実に値付与）
  * 送信は publish → wait_for_publish() でACK待ち（sleep不要）
- エンティティID: object_id で回路番号固定（sensor.c{ID}）
- 単発実行想定（定期実行は HA Automation / cron 推奨）
"""

import os
import sys
import json
import base64
import re
import datetime as dt
from typing import Dict, List, Any
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPDigestAuth
from lxml import html
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ----- .env -----
load_dotenv(dotenv_path=os.getenv("AISEG2_ENV_FILE", ".env"))

# ----- Settings -----
AISEG_HOST = os.getenv("AISEG_HOST", "192.168.0.216")
AISEG_USER = os.getenv("AISEG_USER", "aiseg")
AISEG_PASS = os.getenv("AISEG_PASS", "")

MQTT_HOST   = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER   = os.getenv("MQTT_USER", "")
MQTT_PASS   = os.getenv("MQTT_PASS", "")
MQTT_PREFIX = os.getenv("MQTT_PREFIX", "homeassistant")

DEVICE_ID    = os.getenv("DEVICE_ID", "aiseg2-scrape")
DEVICE_NAME  = os.getenv("DEVICE_NAME", "AISEG2 (Scraped)")
MANUFACTURER = os.getenv("MANUFACTURER", "Panasonic")
MODEL        = os.getenv("MODEL", "AISEG2")

AISEG_TIMEOUT = int(os.getenv("AISEG_TIMEOUT", "10"))
SCAN_TERM     = os.getenv("SCAN_TERM", "day")  # day固定想定

# ----- HTTP / Parse -----
def _auth() -> HTTPDigestAuth:
    return HTTPDigestAuth(AISEG_USER, AISEG_PASS)

_num_re = re.compile(r'([0-9]+(?:\.[0-9]+)?)')
def _to_float(txt: str) -> float:
    if not txt:
        return 0.0
    t = txt.replace('，', ',').replace('．', '.')
    m = _num_re.search(t.replace(',', ''))
    return float(m.group(1)) if m else 0.0

def _get_val_kwh(path: str) -> float:
    url = f"http://{AISEG_HOST}{path}"
    r = requests.get(url, auth=_auth(), timeout=AISEG_TIMEOUT)
    r.raise_for_status()
    root = html.fromstring(r.content)
    vals = root.xpath('//span[@id="val_kwh"]/text()')
    return _to_float(vals[0]) if vals else 0.0

def fetch_totals() -> Dict[str, float]:
    return {
        "total_use_kwh": _get_val_kwh("/page/graph/52111"),
        "buy_kwh":       _get_val_kwh("/page/graph/53111"),
        "sell_kwh":      _get_val_kwh("/page/graph/54111"),
        "gen_kwh":       _get_val_kwh("/page/graph/51111"),
    }

def fetch_circuit_catalog() -> List[Dict[str, str]]:
    url = f"http://{AISEG_HOST}/page/setting/installation/734"
    r = requests.get(url, auth=_auth(), timeout=AISEG_TIMEOUT)
    r.raise_for_status()
    root = html.fromstring(r.content)
    scripts = root.xpath('//script[contains(text(), "window.onload")]')
    if not scripts:
        return []
    text = scripts[0].text or ""
    l = text.find('('); rpos = text.rfind(')')
    if l < 0 or rpos <= l:
        return []
    data = json.loads(text[l+1:rpos].strip())

    out: List[Dict[str, str]] = []
    for c in data.get('arrayCircuitNameList', []):
        if c.get('strBtnType') == "1":
            cid = str(c.get('strId'))
            name = str(c.get('strCircuit') or f"Circuit {cid}")
            out.append({"id": cid, "name": name})
    return out

def fetch_circuit_kwh(circuit_id: str) -> float:
    params = {"circuitid": str(circuit_id)}
    b64 = base64.b64encode(json.dumps(params).encode()).decode()
    url = f"http://{AISEG_HOST}/page/graph/584?data={b64}"
    r = requests.get(url, auth=_auth(), timeout=AISEG_TIMEOUT)
    r.raise_for_status()
    root = html.fromstring(r.content)
    vals = root.xpath('//span[@id="val_kwh"]/text()')
    return _to_float(vals[0]) if vals else 0.0

# ----- MQTT -----
def mqtt_client() -> mqtt.Client:
    mc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="", protocol=mqtt.MQTTv311)
    if MQTT_USER:
        mc.username_pw_set(MQTT_USER, MQTT_PASS)
    mc.max_inflight_messages_set(100)
    mc.connect(MQTT_HOST, MQTT_PORT, 10)
    mc.loop_start()  # 送受信ループ開始（ACK処理のため必須）
    return mc

def publish_and_wait(mc: mqtt.Client, topic: str, payload: str, qos: int = 1, retain: bool = True) -> None:
    """PublishしてACKを待つ（sleep不要）"""
    info = mc.publish(topic, payload, qos=qos, retain=retain)
    info.wait_for_publish()

def disconnect_gracefully(mc: mqtt.Client) -> None:
    mc.loop_stop()
    mc.disconnect()

def availability_topic(uid: str) -> str:
    return f"{MQTT_PREFIX}/aiseg2/{uid}/availability"

def meta_topic(uid: str) -> str:
    return f"{MQTT_PREFIX}/aiseg2/{uid}/meta"

def energy_state_topic(uid: str, key: str) -> str:
    return f"{MQTT_PREFIX}/aiseg2/{uid}/{key}/state"

def circuit_state_topic(uid: str, cid: str) -> str:
    return f"{MQTT_PREFIX}/aiseg2/{uid}/c{cid}/kwh/state"

def publish_discovery_energy(mc: mqtt.Client, uid: str, key: str, name: str, object_id: str, avty_t: str, attr_t: str) -> str:
    uniq = f"{uid}_{key}"
    cfg_t = f"{MQTT_PREFIX}/sensor/{uniq}/config"
    st_t  = energy_state_topic(uid, key)
    # 日本時間の今日の0時を計算
    jst = ZoneInfo("Asia/Tokyo")
    now_jst = dt.datetime.now(jst)
    today_midnight_jst = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    
    payload = {
        "name": name,
        "object_id": f"aiseg2mqtt_{object_id}",   # ← prefix追加
        "uniq_id": uniq,
        "dev": {"ids":[uid], "name": DEVICE_NAME, "mf": MANUFACTURER, "mdl": MODEL, "sw": "web-scrape"},
        "stat_t": st_t, "avty_t": avty_t,
        "dev_cla": "energy",
        "stat_cla": "total",
        "unit_of_meas": "kWh",
        "val_tpl": "{{ value_json.kwh }}",
        "json_attr_t": attr_t,
        "last_reset": today_midnight_jst.isoformat(),
    }
    publish_and_wait(mc, cfg_t, json.dumps(payload, ensure_ascii=False))
    return st_t

def publish_discovery_circuit(mc: mqtt.Client, uid: str, cid: str, cname: str, avty_t: str) -> str:
    uniq = f"{uid}_c{cid}_kwh"
    cfg_t = f"{MQTT_PREFIX}/sensor/{uniq}/config"
    st_t  = circuit_state_topic(uid, cid)
    # 日本時間の今日の0時を計算
    jst = ZoneInfo("Asia/Tokyo")
    now_jst = dt.datetime.now(jst)
    today_midnight_jst = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    
    payload = {
        "name": cname,
        "object_id": f"aiseg2mqtt_c{cid}",   # ← prefix追加
        "uniq_id": uniq,
        "dev": {"ids":[uid], "name": DEVICE_NAME, "mf": MANUFACTURER, "mdl": MODEL, "sw": "web-scrape"},
        "stat_t": st_t, "avty_t": avty_t,
        "dev_cla": "energy",
        "stat_cla": "total",
        "unit_of_meas": "kWh",
        "val_tpl": "{{ value_json.kwh }}",
        "json_attr_t": st_t,
        "last_reset": today_midnight_jst.isoformat(),
    }
    publish_and_wait(mc, cfg_t, json.dumps(payload, ensure_ascii=False))
    return st_t


# ----- Main -----
def main() -> None:
    uid = DEVICE_ID

    # 1) データ取得
    circuits = fetch_circuit_catalog()
    totals   = fetch_totals()
    per: List[Dict[str, Any]] = [{"id": c["id"], "name": c["name"], "kwh": fetch_circuit_kwh(c["id"])} for c in circuits]

    # 2) MQTT接続
    mc = mqtt_client()

    # 3) Availability / Meta（retain）
    avty_t = availability_topic(uid)
    publish_and_wait(mc, avty_t, "online")

    meta_t = meta_topic(uid)
    meta = {"term": SCAN_TERM, "circuit_count": len(per), "ts": dt.datetime.now().isoformat()}
    publish_and_wait(mc, meta_t, json.dumps(meta, ensure_ascii=False))

    # 4) Discovery（config retained）
    total_map = [
        ("total_use_kwh","Total Energy Today","total_today"),
        ("buy_kwh",      "Purchased Energy Today","buy_today"),
        ("sell_kwh",     "Sold Energy Today","sell_today"),
        ("gen_kwh",      "Generated Energy Today","gen_today"),
    ]
    total_state_topics: Dict[str, str] = {}
    for key, disp, obj in total_map:
        st = publish_discovery_energy(mc, uid, key, disp, obj, avty_t, meta_t)
        total_state_topics[key] = st

    circuit_state_topics: List[Dict[str, str]] = []
    for c in per:
        st = publish_discovery_circuit(mc, uid, c["id"], c["name"], avty_t)
        circuit_state_topics.append({"topic": st, "id": c["id"]})

    # 5) state（retained, ACK待ち）
    for key, st in total_state_topics.items():
        publish_and_wait(mc, st, json.dumps({"kwh": totals.get(key, 0.0)}))

    for c in per:
        st = circuit_state_topic(uid, c["id"])
        payload = {"kwh": c["kwh"], "name": c["name"], "circuit_id": c["id"], "term": SCAN_TERM}
        publish_and_wait(mc, st, json.dumps(payload, ensure_ascii=False))

    # 6) 切断
    disconnect_gracefully(mc)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失敗時は availability=offline を残す（ACK待ちで確実に送る）
        try:
            mc = mqtt_client()
            publish_and_wait(mc, availability_topic(DEVICE_ID), "offline")
            disconnect_gracefully(mc)
        except Exception:
            pass
        print(f"[ERROR] {e}", file=sys.stderr)
        raise
