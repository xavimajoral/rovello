# Bolet Radar

A single-page map of wild-mushroom hot spots across all of Catalonia. It scores every 2.2 km cell from the last 21 days of rain, soil moisture, temperature and terrain, plus the trees and bedrock in the cell, shows the result as a heatmap on a pannable, zoomable map, and ranks the best spots in whatever area is in view.

No build step: open `index.html` in a browser. The map uses Leaflet (loaded from cdnjs) and online map tiles, so it needs a connection.

## Run locally

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

## Deploy

It is one static file (`refresh.py` is only for updating the data), so GitHub Pages, Netlify or Cloudflare Pages all work. For GitHub Pages: Settings → Pages → deploy from the `main` branch, root folder.

## How it works

Everything lives in `index.html`.

- **Data** (top of the `<script>`): `WXS` is a 20 × 20 weather grid (about 14 km apart) from Open-Meteo with daily rain, min and max temperature for 21 observed days plus a 3-day forecast; `EL` is a 121 × 121 elevation grid (about 2.2 km apart) from AWS Terrain Tiles; `HAB` holds, for every cell, the tree canopy share of 12 host groups (six pines, fir, beech, holm oak, other oaks, cork oak, chestnut), the total tree canopy and how calcareous the bedrock is (built by `habitat.py`); `CAT` is the Catalonia boundary used to clip the heatmap and limit the ranking. The grid covers 40.50–42.90° N, 0.14–3.34° E. This is a snapshot taken on 4 Nov 2026 and does not refresh by itself.
- **Model** (between `/*DATA+MODEL*/` and `/*END-MODEL*/`): pure functions with no DOM access. Each weather point's series is summarised into three-day rain bins, recent mean temperature, frost nights, forecast rain and lows. `scoreAll()` combines six factors (rain trigger, soil moisture, temperature, elevation fit, slope aspect, forest and soil) as a weighted geometric mean, so a cell without the right trees scores near zero whatever the weather. Each species in `TARGETS` (the same 8 as [iFong](https://ifongapp.com/bolets/anoia): rovelló pinetell, rovelló pi negre i avet, esclatassangs, cep, ou de reig, camagroc, trompeta de la mort, llenega negra) has its own elevation and temperature range, a habitat note shown under the selector, and `host`: the tree groups it grows with, each optionally tied to calcareous (`:c`) or siliceous (`:s`) rock, following that note. `habitat()` turns that into a 0–1 score per cell. `topSpots()` picks the best cells inside Catalonia and inside the current view, spaced according to the zoom.
- **UI** (after the model): a Leaflet map (Light, Topographic or Satellite base, with place names drawn above the heatmap), the suitability heatmap as an image overlay drawn in Web Mercator and clipped to the border, ranked spots for the area in view, a spot inspector (with the forest mix and rock type of the cell) and an SVG weather chart for the weather point nearest the selected spot.

## Limits

- Forest and rock are summarised per 2.2 km cell, so the map says a cell has pine wood, not where in the cell it is. The forest map is from 2021 and misses later felling and fires; bedrock is only a stand-in for soil. Private and protected land is not in the data.
- Weather is on a 14 km grid and terrain every 2.2 km, so local showers and small valleys are smoothed away.
- The weights are rule-of-thumb and have not been checked against real finds.
- Identify every mushroom with certainty before eating it, and check local picking rules.

## Refreshing the data

```bash
python3 refresh.py             # new weather for the 400 grid points; rewrites WXS and START in index.html
python3 refresh.py --terrain   # also rebuilds EL from AWS Terrain Tiles (terrain rarely needs it)
```

It uses only the Python standard library. Weather comes from the Open-Meteo forecast API (`past_days=21`, `forecast_days=3`) in batches of 50 points. Terrain comes from AWS Terrain Tiles rather than Open-Meteo's elevation API, because 14,641 points go over that API's hourly and daily limits.

## Rebuilding the forest and soil layers

```bash
pip install numpy pyshp pyproj rasterio
python3 habitat.py path/to/MFE_51.shp path/to/mgl250mv01p_etrs89.shp   # rewrites HAB in index.html
```

Both inputs are downloaded by hand, because the download pages use a captcha or a viewer:

- [Mapa Forestal de España MFE25, Catalonia](https://www.miteco.gob.es/ca/cartografia-y-sig/ide/descargas/biodiversidad/mfe_catalunia.html) (MITECO, shapefile, 363 MB, free use): forest patches with up to three tree species, their share and the canopy cover.
- [Mapa de grups litològics de Catalunya 1:250.000](https://www.icgc.cat/en/Geoinformation-and-Maps/Data-and-products/Geologic-and-geophysical-geoinformation/Geological-cartography/Map-lithological-groups-Catalonia-1250000) (ICGC, CC BY 4.0): 39 rock groups, each given a calcareous score in `CALC` inside `habitat.py`.

The script draws both maps onto a grid ten times finer than the page grid (about 220 m) and averages each cell. Its canopy totals match the MFE attribute table to within 1% (for example pi blanc 1,972 km², alzina 1,720 km², pi roig 1,483 km²). The maps change rarely, so this is a one-off; `refresh.py` keeps the `HAB` line.

## Credits

Weather: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0, free tier for non-commercial use). Elevation: [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) (Mapzen; sources include SRTM and Copernicus). Forest: [Mapa Forestal de España MFE25](https://www.miteco.gob.es/ca/biodiversidad/temas/inventarios-nacionales/mapa-forestal-espana/mfe_25.html) (MITECO). Bedrock: map of lithological groups of Catalonia 1:250,000, [ICGC](https://www.icgc.cat/) (CC BY 4.0). Boundary: Spanish autonomous communities GeoJSON from Code for Germany's click_that_hood. Map: [Leaflet](https://leafletjs.com/), tiles from Esri, OpenTopoMap and OpenStreetMap contributors. Fonts: Bricolage Grotesque, Hanken Grotesk and IBM Plex Mono from Google Fonts.
