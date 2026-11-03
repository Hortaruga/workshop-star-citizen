#!/usr/bin/env python3
"""Associa cada nave do catálogo à imagem da sua página na Star Citizen Wiki.

Guarda só o endereço da imagem. Uma página só é aceita se for de veículo e citar
o fabricante da nave, o que evita imagens de itens com o mesmo nome.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ship-images.json"
WIKI = "https://starcitizen.tools/"
UA = "WikiCitizenBot/1.0 (+https://github.com/Hortaruga/workshop-star-citizen)"
MIN_FOUND = 100
PREFIX = re.compile(r"^(Aegis|Anvil|Argo|ARGO|Banu|C\.O\.|Crusader|Drake|Esperia|Gatac|Grey's|Greycat|Kruger|MISC|Mirai|Origin|RSI|Tumbril|Vanduul|Aopoa)\s+")
VARIANT = re.compile(r"\s+(Wikelo\b.*|Teach's Special|PYAM Exec|Alliance|\d{4}\b.*|Best In Show.*|Executive Edition|Emerald|Sharkmouth.*)$")
BASES = re.compile(r"\s+(Mk\s*[IVX]+|[A-Z0-9]{1,3}|Heartseeker.*|Wildfire.*|Renegade|Dunlevy|Pirate|Valiant)$")
OG = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"|<meta[^>]+content="([^"]+)"[^>]+property="og:image"')
cache = {}


def load_ships():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    match = re.search(r"const SHIPS=(\[.*?\]);\n", html, re.S)
    if not match:
        raise ValueError("catálogo de naves não encontrado em index.html")
    return json.loads(match.group(1).replace("<\\/", "</"))


def page(title):
    if title in cache:
        return cache[title]
    url = WIKI + urllib.parse.quote(title.replace(" ", "_"), safe="_-.'()")
    html = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as resp:
            html = resp.read().decode("utf-8", "replace")
            url = resp.geturl()
    except urllib.error.HTTPError as err:
        if err.code in (403, 429, 503):
            raise
    except urllib.error.URLError:
        pass
    time.sleep(0.4)
    cache[title] = (html, url)
    return cache[title]


def candidates(name):
    short = re.sub(r"\s+", " ", PREFIX.sub("", name)).strip()
    out = [short]
    base = VARIANT.sub("", short)
    if base not in out:
        out.append(base)
    plain = re.sub(r"\s+Mk\s*[IVX]+", "", base)
    if plain not in out:
        out.append(plain)
    reduced = base
    for _ in range(3):
        next_name = BASES.sub("", reduced)
        if next_name == reduced or not next_name:
            break
        reduced = next_name
        if reduced not in out:
            out.append(reduced)
    return out


def find(ship):
    maker = ship["m"].split()[0].lower()
    for i, title in enumerate(candidates(ship["n"])):
        html, url = page(title)
        if not html:
            continue
        low = html.lower()
        if maker not in low or not ("spacecraft" in low or "ground vehicle" in low):
            continue
        og = OG.search(html)
        image = og and (og.group(1) or og.group(2))
        if not image or "sitelogo" in image or not image.startswith("https://media.starcitizen.tools/"):
            continue
        return {"u": image.replace("&amp;", "&"), "p": url, **({"b": 1} if i else {})}
    return None


def main():
    ships = load_ships()
    found, missing = {}, []
    for ship in ships:
        result = find(ship)
        if result:
            found[ship["id"]] = result
        else:
            missing.append(ship["n"])
    print(f"Imagens: {len(found)} de {len(ships)}; {sum(1 for x in found.values() if x.get('b'))} usam a nave base.")
    if missing:
        print("Sem imagem: " + "; ".join(missing))
    if len(found) < MIN_FOUND:
        raise ValueError(f"só {len(found)} imagens encontradas, mínimo {MIN_FOUND}")
    OUT.write_text(json.dumps(found, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"Imagens não atualizadas: {err}", file=sys.stderr)
        sys.exit(1)
