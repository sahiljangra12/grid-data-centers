# Grid / Data Centers

**Are data centers changing the U.S. power grid, and what does the extra demand cost in carbon?**

A statistical study of every hour of public grid data from January 2019 to today.

**Website:** https://sahiljangra12.github.io/grid-data-centers/

## What it finds

The numbers below are from the run of 22 November 2026. The pipeline reruns every Monday, and the
website always shows the latest.

- **Two PJM zones broke away from the other 17.** Demand in the AEP zone (Ohio and Appalachia) went
  from shrinking 0.8% a year to growing 5.5% a year. Dominion (Virginia) went from 3.6% to 7.2%.
  No other zone sped up by more than 2.5 points.
- **AEP sits 14% (about 2.2 GW) above its synthetic control**, after tracking it within 1% for four
  years. It ranks 1 of 18 zones in the placebo test (p = 0.056, the smallest value possible).
- **Dominion sits 30% above its synthetic control, but that started before 2023.** Measured only as
  speed-up beyond its own earlier trend, the gap is 4.8% (about 750 MW), rank 2 of 18. Suggestive,
  not conclusive.
- **Both zones' share of PJM load changed slope in mid-2024** (sup-F test, p = 0.001 and p = 0.004).
- **In PJM, one extra MWh of demand adds 0.42 t of CO2; the average MWh carries 0.37.**
- **Supplying the roughly 2.9 GW that is new since 2023 emits about 10.9 Mt of CO2 a year**
  (range 10.0 to 12.8) at PJM's marginal rate.
- Baseload growth sped up significantly in 2 of 10 large grid regions (PJM and SPP).

Demand data is by zone, not by customer. The pattern fits data centers in timing, place and load
shape, but the study does not observe them directly.

## Data

U.S. Energy Information Administration, Form EIA-930 (Hourly Electric Grid Monitor): hourly demand
and generation by fuel for 10 balancing authorities, and hourly demand for PJM's zones. Public
domain, no API key needed. About 2.1 million hourly records.

CO2 is estimated from generation with EIA's 2023 national factors (coal 1.050, gas 0.437,
petroleum 1.109 t/MWh).

## Methods

| Question | Method |
|---|---|
| Did growth change after 2022? | Log demand on month effects and a trend allowed to bend in January 2023; Newey-West errors |
| How far is a zone from where it would have been? | Synthetic control from other PJM zones; placebo zones, leave-one-out refits and a placebo start date |
| When did the trend bend? | Sup-F test for a slope change at an unknown date; moving-block bootstrap, 999 draws |
| How dirty is the next MWh? | Hourly first differences of CO2 on demand with wind and solar controls; HAC errors, 24 lags |

Dominion was chosen as the zone of interest in advance. AEP was not: it surfaced from the
zone-by-zone comparison, and is reported as such. Each is kept out of the other's comparison pool.

## Limits

- With 17 comparison zones the smallest possible placebo p-value is 0.056.
- One emission factor per fuel misses differences between efficient and inefficient plants.
- Emissions are counted inside each region; imported power is not traced to its source.
- No temperature data is used; zones are compared with neighbors under the same weather instead.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q          # tests on synthetic data with known answers
python src/fetch_data.py     # downloads about 1 GB from EIA, keeps two parquet files (not committed)
python src/analysis.py       # writes docs/data/results.json
python -m http.server -d docs 8000
```

## Layout

```
src/fetch_data.py    download and reduce the EIA-930 bulk files
src/analysis.py      cleaning, models, results.json
src/config.py        regions, dates, emission factors
tests/               synthetic grid with planted effects; checks the models recover them
docs/                the website (GitHub Pages) and its results file
.github/workflows/   weekly refresh
```

Sahil, MSE Data Science, Johns Hopkins University.
