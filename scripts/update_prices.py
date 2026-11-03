#!/usr/bin/env python3
"""Atualiza prices.json com os preços de venda de salvage publicados pela API do UEX.

Não grava nada se a resposta parecer incompleta ou fora do padrão, e o site
mantém os preços anteriores.
"""
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://api.uexcorp.uk/2.0/commodities_prices"
COMMODITIES = {"rmc": "recycled-material-composite", "cm": "construction-materials"}
OUT = Path(__file__).resolve().parent.parent / "prices.json"
BRT = timezone(timedelta(hours=-3))
SYSTEMS = {"Stanton", "Pyro", "Nyx"}
MIN_ROWS = 15
MAX_MEDIAN_CHANGE = 0.40


def fetch(slug):
    url = BASE + "?" + urllib.parse.urlencode({"commodity_slug": slug})
    headers = {"Accept": "application/json", "User-Agent": "wiki-citizen-prices"}
    token = os.environ.get("UEX_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
        body = json.load(resp)
    if body.get("status") != "ok" or not isinstance(body.get("data"), list):
        raise ValueError(f"resposta inesperada para {slug}: status={body.get('status')!r}")
    return body["data"]


def to_row(raw):
    price = raw.get("price_sell") or 0
    system = raw.get("star_system_name")
    name = raw.get("terminal_name")
    if price <= 0 or system not in SYSTEMS or not name or raw.get("terminal_is_player_owned"):
        return None
    where = next(
        (raw.get(k) for k in ("moon_name", "planet_name", "orbit_name", "space_station_name", "city_name", "outpost_name") if raw.get(k)),
        system,
    )
    updated = datetime.fromtimestamp(raw.get("date_modified") or raw.get("date_added") or 0, BRT)
    return {"n": name, "w": where, "s": system, "m": round(price), "u": updated.strftime("%d/%m")}


def validate(key, rows, old):
    if len(rows) < MIN_ROWS:
        raise ValueError(f"{key}: só {len(rows)} compradores, mínimo {MIN_ROWS}")
    previous = [r["m"] for r in old.get(key, [])]
    if previous:
        before, now = statistics.median(previous), statistics.median(r["m"] for r in rows)
        if abs(now - before) / before > MAX_MEDIAN_CHANGE:
            raise ValueError(f"{key}: mediana mudou de {before} para {now}; revise antes de publicar")


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    new = {"updated": datetime.now(BRT).strftime("%Y-%m-%d"), "gameVersion": old.get("gameVersion", "")}
    versions = []
    for key, slug in COMMODITIES.items():
        raw = fetch(slug)
        rows = sorted(filter(None, map(to_row, raw)), key=lambda r: (-r["m"], r["n"]))
        validate(key, rows, old)
        new[key] = rows
        versions += [r["game_version"] for r in raw if r.get("game_version")]
    if versions:
        new["gameVersion"] = max(set(versions), key=versions.count)
    OUT.write_text(json.dumps(new, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"prices.json: {len(new['rmc'])} RMC, {len(new['cm'])} CM, versão {new['gameVersion']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"Preços não atualizados: {err}", file=sys.stderr)
        sys.exit(1)
