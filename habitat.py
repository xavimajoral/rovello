#!/usr/bin/env python3
"""Build the forest and soil layers (`const HAB=`) inside index.html.

    python3 habitat.py MFE_51.shp mgl250mv01p_etrs89.shp

Inputs, both downloaded by hand (the download pages have a captcha or a viewer):
  * Mapa Forestal de España MFE25, Catalonia (MITECO, free use):
    https://www.miteco.gob.es/ca/cartografia-y-sig/ide/descargas/biodiversidad/mfe_catalunia.html
  * Mapa de grups litològics de Catalunya 1:250.000 (ICGC, CC BY 4.0):
    https://www.icgc.cat/en/Geoinformation-and-Maps/Data-and-products/Geologic-and-geophysical-geoinformation/Geological-cartography/Map-lithological-groups-Catalonia-1250000

Needs numpy, pyshp, pyproj and rasterio (pip install numpy pyshp pyproj rasterio). Only this script needs them;
the page and refresh.py do not. The source maps change rarely, so this is a one-off.

Each source map is drawn onto a grid ten times finer than the page grid (about 220 m) and averaged per cell:
  * for each host group below, the share of the cell under that tree's canopy (MFE canopy cover x species share),
    counted over the part of the cell the MFE covers, so border and coast cells are not diluted;
  * total tree canopy;
  * how calcareous the bedrock is, 0 (siliceous) to 1 (limestone), from the ICGC lithological group.
Values are stored as one base64url character each (cover as a square root, so small shares keep detail),
with runs of zeros written as "~" plus a two-character count.
"""
import re, sys
from pathlib import Path
import numpy as np
import shapefile
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin

LAT0, LAT1, LON0, LON1, N = 40.50, 42.90, 0.14, 3.34, 121  # must match index.html
SUB = 10
HTML = Path(__file__).with_name("index.html")

# host groups, in the order index.html reads them (HG in the page)
GROUPS = {
    "blanc": ["Pinus halepensis"],
    "roig": ["Pinus sylvestris"],
    "pinastre": ["Pinus pinaster"],
    "negre": ["Pinus uncinata"],
    "pinassa": ["Pinus nigra"],
    "pinyer": ["Pinus pinea"],
    "avet": ["Abies alba"],
    "faig": ["Fagus sylvatica"],
    "alzina": ["Quercus ilex"],
    "roure": ["Quercus humilis (Q. Pubescens)", "Quercus faginea", "Quercus petraea", "Quercus robur", "Quercus pyrenaica"],
    "surera": ["Quercus suber"],
    "castanyer": ["Castanea sativa"],
}
SP2G = {sp: g for g, (_, sps) in enumerate(GROUPS.items()) for sp in sps}

# how calcareous each ICGC lithological group is: 1 limestone/dolomite, 0 granite/slate/gneiss/sandstone,
# in between for marls, mixed sediments, gypsum and conglomerates with carbonate cement
CALC = {
    "C-Ca": 1, "C-Ca/Do": 1, "C-Do": 1, "CO-Ca/Mo": .9, "CDh-Ca/Mx": .85, "CDf-Pl": .8, "CDf-Ca/Si": .8, "E-Su": .8,
    "CDg-Ca/Si": .7, "CDm-Pl": .7, "DfCE-Mx/Ca/Su": .7, "DmC-Mx/Ca": .65, "DgC-Mx/Ca": .65, "DhC-Mx/Ca": .65,
    "DfE-Mx/Su": .65, "DfC-Si/Ca": .6, "DhC-Pl": .5, "DhCO-Pl/Mo": .5, "Df-Mx": .5, "Dh-Mx": .5, "DhNc-Mx": .5,
    "Dg-Mx": .5, "Dm-Mx": .5, "DmNc-Mx": .5, "DfONc-Mx/Mo": .5, "E-Cl": .5, "DfO-Mx/Mo": .4, "M-Pl": .3,
    "V-Si": .2, "P-Si": .2, "Df-Si/Q": 0, "G-Q/Si": 0, "Dg-Q/Si": 0, "V-Q/Si": 0, "P-Q/Si": 0, "P-Si/Q": 0,
    "Dh-Q/Si": 0, "Dm-Q/Si": 0,
}

DLON, DLAT = (LON1 - LON0) / (N - 1), (LAT1 - LAT0) / (N - 1)
TRANSFORM = from_origin(LON0 - DLON / 2, LAT1 + DLAT / 2, DLON / SUB, DLAT / SUB)
SHAPE = (N * SUB, N * SUB)


def burn(path, epsg, value_of, encoding="utf-8", chunk=5000):
    """Rasterize every polygon of a shapefile onto the fine grid as 1 + its record number. Returns (ids, values)."""
    r = shapefile.Reader(str(path), encoding=encoding)
    tr = Transformer.from_crs(epsg, 4258, always_xy=True)
    out = np.zeros(SHAPE, dtype=np.int32)
    vals, batch = [None], []

    def ring(c):
        a = np.asarray(c, dtype=float)
        x, y = tr.transform(a[:, 0], a[:, 1])
        return np.column_stack([x, y]).tolist()

    def flush():
        if batch:
            rasterize(batch, out=out, transform=TRANSFORM)
            batch.clear()

    for n, sr in enumerate(r.iterShapeRecords()):
        vals.append(value_of(sr.record))
        g = sr.shape.__geo_interface__
        if g["type"] == "Polygon":
            g = {"type": "Polygon", "coordinates": [ring(c) for c in g["coordinates"]]}
        elif g["type"] == "MultiPolygon":
            g = {"type": "MultiPolygon", "coordinates": [[ring(c) for c in p] for p in g["coordinates"]]}
        else:
            continue
        batch.append((g, n + 1))
        if len(batch) >= chunk:
            flush()
            print(f"{path.name}: {n + 1} polygons", file=sys.stderr)
    flush()
    return out, vals


def cells(fine):
    """Average SUB x SUB blocks; returns rows south to north, like the page grid."""
    return fine.reshape(N, SUB, N, SUB, *fine.shape[2:]).mean(axis=(1, 3))[::-1]


def mfe_values(rec):
    v = np.zeros(len(GROUPS) + 1, dtype=np.float32)
    tree = (rec["FCCARB"] or 0) / 100
    v[-1] = tree
    for k in "123":
        g = SP2G.get(rec["Especie" + k])
        if g is not None:
            v[g] += tree * (rec["O" + k] or 0) / 100
    return v


B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def encode(q):
    """q: ints 0..63 in page order. Zero runs of 3 or more become '~' + two base64 digits (run length)."""
    out, i, n = [], 0, len(q)
    while i < n:
        if q[i] == 0:
            j = i
            while j < n and q[j] == 0 and j - i < 4095:
                j += 1
            if j - i >= 3:
                out.append("~" + B64[(j - i) >> 6] + B64[(j - i) & 63])
                i = j
                continue
        out.append(B64[q[i]])
        i += 1
    return "".join(out)


def main(mfe, lito):
    ids, vals = burn(Path(mfe), 25830, mfe_values)
    table = np.stack([np.zeros(len(GROUPS) + 1, np.float32)] + vals[1:])
    have = cells((ids > 0).astype(np.float32))
    cover = cells(table[ids]) / np.maximum(have, 1e-9)[..., None]
    cover[have < .05] = 0

    lids, lvals = burn(Path(lito), 25831, lambda rec: CALC.get(rec["EPI_LITO_1"]), encoding="latin-1")
    lv = np.array([np.nan] + [np.nan if v is None else v for v in lvals[1:]], dtype=np.float32)
    lfine = lv[lids]
    known = ~np.isnan(lfine)
    calc = cells(np.where(known, lfine, 0)) / np.maximum(cells(known.astype(np.float32)), 1e-9)
    calc[cells(known.astype(np.float32)) < .05] = .5

    layers = [np.rint(np.sqrt(np.clip(cover[..., g], 0, 1)) * 63).astype(int).ravel() for g in range(cover.shape[-1])]
    layers.append(np.rint(np.clip(calc, 0, 1) * 63).astype(int).ravel())
    hab = "|".join(encode(list(q)) for q in layers)

    s = HTML.read_text()
    line = 'const HAB="' + hab + '";'
    if re.search(r"^const HAB=.*$", s, flags=re.M):
        s = re.sub(r"^const HAB=.*$", lambda _: line, s, count=1, flags=re.M)
    else:
        s = re.sub(r"^(const EL=.*)$", lambda m: m.group(1) + "\n/* forest and soil, N x N per layer (see habitat.py) */\n" + line,
                   s, count=1, flags=re.M)
    HTML.write_text(s)

    km2 = (DLON * 111.32 * np.cos(np.radians(41.7))) * (DLAT * 111.2)
    names = list(GROUPS) + ["bosc"]
    print(f"HAB: {len(hab):,} characters", file=sys.stderr)
    for g, nm in enumerate(names):
        print(f"  {nm:10} {float((cover[..., g] * have).sum() * km2):8.0f} km² of canopy", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
