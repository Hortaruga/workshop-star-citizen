#!/usr/bin/env python3
"""Atualiza item-prices.json com o menor preço de compra de cada item no UEX."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://api.uexcorp.uk/2.0/items_prices_all"
OUT = Path(__file__).resolve().parent.parent / "item-prices.json"
BRT = timezone(timedelta(hours=-3))
MIN_ITEMS = 300


def fetch():
    headers = {"Accept": "application/json", "User-Agent": "wiki-citizen-prices"}
    token = os.environ.get("UEX_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(URL, headers=headers), timeout=120) as resp:
        body = json.load(resp)
    if body.get("status") != "ok" or not isinstance(body.get("data"), list):
        raise ValueError(f"resposta inesperada: status={body.get('status')!r}")
    return body["data"]


def build(rows):
    items = {}
    for row in rows:
        name = row.get("item_name")
        terminal = row.get("terminal_name")
        buy = row.get("price_buy") or 0
        sell = row.get("price_sell") or 0
        if not name or not terminal:
            continue
        entry = items.setdefault(name, {})
        if buy > 0 and ("b" not in entry or buy < entry["b"]):
            entry["b"], entry["t"] = round(buy), terminal
        if sell > 0 and sell > entry.get("s", 0):
            entry["s"], entry["st"] = round(sell), terminal
    return {name: entry for name, entry in items.items() if entry}


def main():
    items = build(fetch())
    if len(items) < MIN_ITEMS:
        raise ValueError(f"só {len(items)} itens, mínimo {MIN_ITEMS}")
    data = {"updated": datetime.now(BRT).strftime("%Y-%m-%d"), "items": items}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"item-prices.json: {len(items)} itens")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"Preços de itens não atualizados: {err}", file=sys.stderr)
        sys.exit(1)
