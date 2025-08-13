# This script downloads all Material Symbols codepoints from Google's repo
# and generates a Python dictionary mapping icon names to Unicode escapes.
#
# Usage:
#   python build_material_symbols_dict.py
#
# Output:
#   material_symbols.py containing the dictionary

import re
import requests
from pathlib import Path

RAW_BASE = "https://raw.githubusercontent.com/google/material-design-icons/master/variablefont"


FILES = [
    "MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints",
    "MaterialSymbolsRounded[FILL,GRAD,opsz,wght].codepoints",
    "MaterialSymbolsSharp[FILL,GRAD,opsz,wght].codepoints",
]

def fetch_codepoints(url: str) -> str:
    print(f"Downloading: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.text

def parse_codepoints(text: str) -> dict:
    out = {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split()
        if len(parts) != 2:
            continue
        name, hexcode = parts
        hexcode = hexcode.strip().lstrip("uU+").upper()
        if not re.fullmatch(r"[0-9A-F]{4,6}", hexcode):
            continue
        if len(hexcode) <= 4:
            esc = f"\\u{hexcode.zfill(4)}"
        else:
            esc = f"\\U{hexcode.zfill(8)}"
        out[name] = esc
    return out

def main():
    merged = {}
    for fname in FILES:
        url = f"{RAW_BASE}/{fname}"
        try:
            txt = fetch_codepoints(url)
        except Exception as e:
            print(f"WARNING: Could not fetch {url}: {e}")
            continue
        parsed = parse_codepoints(txt)
        for k, v in parsed.items():
            merged.setdefault(k, v)

    if not merged:
        print("ERROR: No codepoints fetched.")
        return

    items = sorted(merged.items(), key=lambda kv: kv[0])

    out_path = Path("material_symbols.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("material_symbols = {\n")
        for name, esc in items:
            f.write(f'    "{name}": "{esc}",\n')
        f.write("}\n")

    print(f"Wrote {out_path.resolve()} with {len(items)} entries.")

if __name__ == "__main__":
    main()
