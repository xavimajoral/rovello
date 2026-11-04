# Bolet Radar

A single-page map of wild-mushroom hot spots across all of Catalonia. It scores every 2.2 km cell from the last 21 days of rain, soil moisture, temperature and terrain, shows the result as a heatmap on a pannable, zoomable map, and ranks the best spots in whatever area is in view.

No build step: open `index.html` in a browser. The map uses Leaflet (loaded from cdnjs) and online map tiles, so it needs a connection.

## Run locally

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

## Deploy

It is one static file (`refresh.py` is only for updating the data), so GitHub Pages, Netlify or Cloudflare Pages all work. For GitHub Pages: Settings → Pages → deploy from the `main` branch, root folder.

## How it works

Everything lives in `index.html`.

- **Data** (top of the `<script>`): `WXS` is a 20 × 20 weather grid (about 14 km apart) from Open-Meteo with daily rain, min and max temperature for 21 observed days plus a 3-day forecast; `EL` is a 121 × 121 elevation grid (about 2.2 km apart) from AWS Terrain Tiles; `CAT` is the Catalonia boundary used to clip the heatmap and limit the ranking. The grid covers 40.50–42.90° N, 0.14–3.34° E. This is a snapshot taken on 4 Nov 2026 and does not refresh by itself.
- **Model** (between `/*DATA+MODEL*/` and `/*END-MODEL*/`): pure functions with no DOM access. Each weather point's series is summarised into three-day rain bins, recent mean temperature, frost nights, forecast rain and lows. `scoreAll()` combines five factors (rain trigger, soil moisture, temperature, elevation fit, slope aspect) as a weighted geometric mean. Each species in `TARGETS` (the same 8 as [iFong](https://ifongapp.com/bolets/anoia): rovelló pinetell, rovelló pi negre i avet, esclatassangs, cep, ou de reig, camagroc, trompeta de la mort, llenega negra) has its own elevation and temperature range and a habitat note shown under the selector. `topSpots()` picks the best cells inside Catalonia and inside the current view, spaced according to the zoom.
- **UI** (after the model): a Leaflet map (Light, Topographic or Satellite base, with place names drawn above the heatmap), the suitability heatmap as an image overlay drawn in Web Mercator and clipped to the border, ranked spots for the area in view, a spot inspector and an SVG weather chart for the weather point nearest the selected spot.

## Limits

- Woodland type and canopy are not in the data, so the map cannot see where pine or oak woods are, or which land is private or protected.
- Weather is on a 14 km grid and terrain every 2.2 km, so local showers and small valleys are smoothed away.
- The weights are rule-of-thumb and have not been checked against real finds.
- Identify every mushroom with certainty before eating it, and check local picking rules.

## Refreshing the data

```bash
python3 refresh.py             # new weather for the 400 grid points; rewrites WXS and START in index.html
python3 refresh.py --terrain   # also rebuilds EL from AWS Terrain Tiles (terrain rarely needs it)
```

It uses only the Python standard library. Weather comes from the Open-Meteo forecast API (`past_days=21`, `forecast_days=3`) in batches of 50 points. Terrain comes from AWS Terrain Tiles rather than Open-Meteo's elevation API, because 14,641 points go over that API's hourly and daily limits.

## Credits

Weather: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0, free tier for non-commercial use). Elevation: [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) (Mapzen; sources include SRTM and Copernicus). Boundary: Spanish autonomous communities GeoJSON from Code for Germany's click_that_hood. Map: [Leaflet](https://leafletjs.com/), tiles from Esri, OpenTopoMap and OpenStreetMap contributors. Fonts: Bricolage Grotesque, Hanken Grotesk and IBM Plex Mono from Google Fonts.
