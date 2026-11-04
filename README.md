# Bolet Radar

A single-page map of wild-mushroom hot spots in the Anoia comarca (Catalonia). It scores every 0.75 km cell from the last 21 days of weather plus forest, soil and species-range layers, and ranks the best spots for rovelló, llenega negra and ou de reig.

No build step and no dependencies: serve `index.html` over http(s) (the Google Maps panel needs it).

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

It is one static file, so GitHub Pages, Netlify or Cloudflare Pages all work.

## What is in `index.html`

- **Data** (the `DATA` object at the top of the `<script>`):
  - `runs`, `c1`, `c2`, `c3`: the habitat grid, 58 × 58 cells over lon 1.350–1.870, lat 41.420–41.810, only the 1,610 cells inside the comarca. `runs` lists which cells, `c1` holds forest class and siliceous soil, `c2` forest cover and rovelló range, `c3` llenega negra and ou de reig range, all quantised to five levels.
  - `poly`: simplified comarca boundary (OpenStreetMap), used to clip the map.
  - `eln`: 49 × 49 elevation grid in 20 m steps, base-62 encoded.
  - `raw`, `serp`, `sern`, `serx`: weather snapshot from Open-Meteo for 14 Oct – 6 Nov 2026 (a 5 × 5 grid summarised per point, plus the daily series at the centre).
- **Model** (between `/*DATA+MODEL*/` and `/*END-MODEL*/`): pure functions with no DOM access. `scoreAll()` combines six factors (rain trigger, soil moisture, temperature, elevation fit, slope aspect, habitat) as a weighted geometric mean, with a season gate on temperature. `topSpots()` picks the best cells at least 3 km apart.
- **UI** (after the model): hillshaded canvas map with three layers (suitability, forest, species range), ranked spots, a spot inspector, a weather chart and an optional Google Maps panel (`GMAPS_EMBED`).

## Where the habitat layers come from

They were read from the public iFong maps of the comarca (<https://ifongapp.com/bolets/anoia>): forest type, siliceous or calcareous soil, and the range of each species. The images were matched to the OpenStreetMap comarca boundary and averaged into cells. The totals agree with the shares iFong prints (rovelló range 24% against 25.6%, llenega negra 25% against 29.2%, ou de reig 1.2% against 1.3%), but this is a reading of pictures, not their dataset.

Check iFong's terms before making a public repository: the layers are derived from their maps and they may not allow reuse. Cep, camagroc, esclatassangs and trompeta de la mort are left out because iFong maps almost no range for them in Anoia.

## Limits

- No habitat data outside the comarca, so the map stops at its boundary.
- Weather is on a 10 km grid and terrain every 0.9 km, so local showers and small valleys are smoothed away.
- Private land, protected areas and picking limits are not in the data.
- The weights are rule-of-thumb and have not been checked against real finds.
- Identify every mushroom with certainty before eating it, and check local picking rules.

## Refreshing the weather

The weather is a snapshot. To refresh it, fetch the Open-Meteo forecast API (`past_days=21`, `forecast_days=3`, daily `precipitation_sum`, `temperature_2m_min`, `temperature_2m_max`) for the 25 grid points (lat 41.42, 41.5175, 41.615, 41.7125, 41.81 by lon 1.35, 1.48, 1.61, 1.74, 1.87), then rebuild `raw`, `serp`, `sern`, `serx`. Each `raw` row is: model elevation, seven 3-day rain sums (days 0–20), forecast rain (days 21–23), mean temperature over days 11–20, minimum temperature over days 11–20, mean maximum over days 14–20, frost nights in days 0–20, lowest forecast minimum, consecutive dry days up to day 20. Update `START` and `TODAY` in the script to match.

## Credits

Weather and elevation: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0, free tier for non-commercial use). Comarca boundary: © OpenStreetMap contributors (ODbL). Habitat layers: iFong. Fonts: Bricolage Grotesque, Hanken Grotesk and IBM Plex Mono from Google Fonts.
