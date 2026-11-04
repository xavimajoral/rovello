#!/usr/bin/env python3
"""Refresh the data snapshot inside index.html from Open-Meteo.

    python3 refresh.py              # weather only (terrain does not change)
    python3 refresh.py --terrain    # also rebuild the 121 x 121 elevation grid from AWS Terrain Tiles

Rewrites the `const START=`, `const WXS=` and (with --terrain) `const EL=` lines in index.html.
The grid constants must match the ones at the top of the <script> in index.html.
"""
import json, math, re, struct, sys, time, zlib, datetime, urllib.request, urllib.error
from pathlib import Path

LAT0, LAT1, LON0, LON1 = 40.50, 42.90, 0.14, 3.34
N, NW = 121, 20
HTML = Path(__file__).with_name("index.html")


def get(url):
    for _ in range(10):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            print("HTTP", e.code, "- retrying", file=sys.stderr)
            time.sleep(65 if e.code == 429 else 5)
        except Exception as e:  # network hiccup
            print("error", e, "- retrying", file=sys.stderr)
            time.sleep(5)
    raise SystemExit("giving up on " + url[:120])


def q(pts, k):
    return ",".join(f"{p[k]:.4f}" for p in pts)


def weather():
    pts = [(LAT0 + i / (NW - 1) * (LAT1 - LAT0), LON0 + j / (NW - 1) * (LON1 - LON0)) for i in range(NW) for j in range(NW)]
    out = []
    for b in range(0, len(pts), 50):
        ch = pts[b:b + 50]
        r = get("https://api.open-meteo.com/v1/forecast?latitude=" + q(ch, 0) + "&longitude=" + q(ch, 1)
                + "&daily=precipitation_sum,temperature_2m_min,temperature_2m_max&past_days=21&forecast_days=3&timezone=Europe%2FMadrid")
        out += r if isinstance(r, list) else [r]
        print(f"weather {len(out)}/{len(pts)}", file=sys.stderr)
        time.sleep(3)
    return out


def png_rgb(data):
    """Minimal decoder for 8-bit RGB/RGBA non-interlaced PNGs (enough for terrain tiles)."""
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ctype in (2, 6), "unsupported PNG"
            bpp = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    return w, bpp, rows


def terrain(z=9):
    """Sample the N x N grid from AWS Terrain Tiles (Terrarium encoding, ~300 m pixels at zoom 9)."""
    n = 2 ** z
    tx = lambda lon: (lon + 180) / 360 * n * 256
    ty = lambda lat: (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * 256
    tiles = {}

    def px(x, y):
        key = (int(x // 256), int(y // 256))
        if key not in tiles:
            with urllib.request.urlopen(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{key[0]}/{key[1]}.png", timeout=60) as r:
                tiles[key] = png_rgb(r.read())
            print(f"terrain tile {len(tiles)}", file=sys.stderr)
        _, bpp, rows = tiles[key]
        row, o = rows[int(y) % 256], (int(x) % 256) * bpp
        return row[o] * 256 + row[o + 1] + row[o + 2] / 256 - 32768

    el = []
    for i in range(N):
        for j in range(N):
            x, y = tx(LON0 + j / (N - 1) * (LON1 - LON0)) - .5, ty(LAT0 + i / (N - 1) * (LAT1 - LAT0)) - .5
            x0, y0, fx, fy = math.floor(x), math.floor(y), x - math.floor(x), y - math.floor(y)
            el.append(px(x0, y0) * (1 - fx) * (1 - fy) + px(x0 + 1, y0) * fx * (1 - fy) + px(x0, y0 + 1) * (1 - fx) * fy + px(x0 + 1, y0 + 1) * fx * fy)
    return el


def fmt(v):
    return f"{v:g}" if v is not None else "0"


def inject(wx, el=None, html=HTML):
    s = html.read_text()
    d0 = datetime.date.fromisoformat(wx[0]["daily"]["time"][0])
    s = re.sub(r"^const START=.*$", f"const START=Date.UTC({d0.year},{d0.month - 1},{d0.day});", s, count=1, flags=re.M)
    rows = []
    for x in wx:
        d = x["daily"]
        rows.append("|".join([fmt(round(x["elevation"]))] + [",".join(fmt(v) for v in d[k]) for k in
                                                            ("precipitation_sum", "temperature_2m_min", "temperature_2m_max")]))
    s = re.sub(r'^const WXS=.*$', lambda _: 'const WXS="' + ";".join(rows) + '";', s, count=1, flags=re.M)
    if el is not None:
        s = re.sub(r"^const EL=.*$", lambda _: "const EL=[" + ",".join(str(max(0, round(v))) for v in el) + "];", s, count=1, flags=re.M)
    html.write_text(s)
    print("updated", html, "from", d0, file=sys.stderr)


if __name__ == "__main__":
    inject(weather(), terrain() if "--terrain" in sys.argv else None)
