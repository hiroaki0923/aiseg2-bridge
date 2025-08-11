#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean MQTT Discovery configs for AISEG2 publisher.
- Home AssistantのMQTT Discoveryで作成済みのセンサーを「削除」するため、
  configトピックへ空メッセージ(retain)をPublishします。
- 対象:
    * 合計系: total_use_kwh / buy_kwh / sell_kwh / gen_kwh
    * 回路系: aiseg2-scrape_c{circuitId}_kwh
- 回路IDはAISEG2の /page/setting/installation/734 から取得（strBtnType=="1"）
  取得できなかった場合は、環境変数 CIRCUIT_MIN, CIRCUIT_MAX の範囲でフォールバックします。
"""

import os
import sys
import json
from typing import List, Dict

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

DEVICE_ID   = os.getenv("DEVICE_ID", "aiseg2-scrape")
AISEG_TIMEOUT = int(os.getenv("AISEG_TIMEOUT", "10"))

# 任意: 回路ID範囲のフォールバック
CIRCUIT_MIN = int(os.getenv("CIRCUIT_MIN", "1"))
CIRCUIT_MAX = int(os.getenv("CIRCUIT_MAX", "64"))

# ----- Helpers -----
def _auth() -> HTTPDigestAuth:
    return HTTPDigestAuth(AISEG_USER, AISEG_PASS)

def fetch_circuit_ids() -> List[str]:
    """
    /page/setting/installation/734 の window.onload = init({...})
    から arrayCircuitNameList を取り出し、strBtnType == "1" のstrIdを返す。
    取得に失敗したらフォールバックでCIRCUIT_MIN..MAXを返す。
    """
    try:
        url = f"http://{AISEG_HOST}/page/setting/installation/734"
        r = requests.get(url, auth=_auth(), timeout=AISEG_TIMEOUT)
        r.raise_for_status()
        root = html.fromstring(r.content)
        scripts = root.xpath('//script[contains(text(), "window.onload")]')
        if not scripts:
            raise RuntimeError("window.onload script not found")
        text = scripts[0].text or ""
        l = text.find('('); rpos = text.rfind(')')
        if l < 0 or rpos <= l:
            raise RuntimeError("json payload not found")
        data = json.loads(text[l+1:rpos].strip())
        out = []
        for c in data.get('arrayCircuitNameList', []):
            if c.get('strBtnType') == "1":
                out.append(str(c.get('strId')))
        if not out:
            raise RuntimeError("empty circuit list")
        return out
    except Exception as e:
        print(f"[WARN] circuit catalog fetch failed: {e}", file=sys.stderr)
        return [str(i) for i in range(CIRCUIT_MIN, CIRCUIT_MAX + 1)]

def mqtt_client() -> mqtt.Client:
    mc = mqtt.Client(protocol=mqtt.MQTTv311)
    if MQTT_USER:
        mc.username_pw_set(MQTT_USER, MQTT_PASS)
    mc.max_inflight_messages_set(100)
    mc.connect(MQTT_HOST, MQTT_PORT, 10)
    mc.loop_start()  # ACK処理のため必須
    return mc

def publish_and_wait(mc: mqtt.Client, topic: str, payload: bytes | str | None, qos: int = 1, retain: bool = True) -> None:
    """PublishしてACKを待つ（sleep不要）"""
    info = mc.publish(topic, payload, qos=qos, retain=retain)
    info.wait_for_publish()

def disconnect_gracefully(mc: mqtt.Client) -> None:
    mc.loop_stop()
    mc.disconnect()

# ----- Main -----
def main() -> None:
    # 削除対象トピックの組み立て
    topics: List[str] = []

    # 合計系
    total_keys = ["total_use_kwh", "buy_kwh", "sell_kwh", "gen_kwh"]
    for key in total_keys:
        uniq = f"{DEVICE_ID}_{key}"
        topics.append(f"{MQTT_PREFIX}/sensor/{uniq}/config")

    # 回路系
    circuit_ids = fetch_circuit_ids()
    for cid in circuit_ids:
        uniq = f"{DEVICE_ID}_c{cid}_kwh"
        topics.append(f"{MQTT_PREFIX}/sensor/{uniq}/config")

    # Publish 空メッセージ（retain）で削除
    mc = mqtt_client()
    try:
        for t in topics:
            print(f"[cleanup] DELETE (retain empty) -> {t}")
            publish_and_wait(mc, t, None, qos=1, retain=True)  # None で空ペイロード
    finally:
        disconnect_gracefully(mc)

    print(f"[done] published {len(topics)} delete messages.")

if __name__ == "__main__":
    main()
