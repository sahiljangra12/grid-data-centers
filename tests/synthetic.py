"""Small synthetic EIA-930-shaped dataset with known answers, for testing the analysis."""
import numpy as np
import pandas as pd

ZONES = ["DOM", "AEP", "CE", "PS", "PE", "BC", "PL", "DUQ", "ATSI", "DPL"]
BAS = ["PJM", "ERCO", "MISO"]
TRUE_MEF = 0.60          # t CO2 per MWh planted in the synthetic grid
TRUE_EXTRA_GROWTH = 0.10  # extra yearly log growth in DOM after 2023


def make(seed: int = 7, end: str = "2025-12-31 23:00"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", end, freq="h")
    n = len(idx)
    years = np.asarray((idx - pd.Timestamp("2023-01-01")).days / 365.25)
    season = 0.12 * np.cos(2 * np.pi * (idx.dayofyear.values - 20) / 365.25)
    daily = 0.10 * np.sin(2 * np.pi * (idx.hour.values - 9) / 24)
    weather = pd.Series(rng.normal(0, 0.03, n)).rolling(72, min_periods=1).mean().values

    zones = []
    for i, z in enumerate(ZONES):
        mix = 0.6 + 0.08 * i
        log_d = (np.log(5000 + 900 * i) + mix * season + daily + weather
                 + 0.005 * (years + 4) + rng.normal(0, 0.01, n))
        if z == "DOM":
            log_d = log_d + TRUE_EXTRA_GROWTH * np.clip(years, 0, None)
        zones.append(pd.DataFrame({"zone": z, "utc": idx, "local": idx,
                                   "demand": np.exp(log_d).astype("float32")}))
    sub = pd.concat(zones, ignore_index=True)

    bals = []
    for j, ba in enumerate(BAS):
        demand = (60000 + 20000 * j) * np.exp(season + daily + weather + 0.01 * (years + 4)
                                             + rng.normal(0, 0.005, n))
        nuclear = np.full(n, 0.30 * demand.mean())
        wind = 0.08 * demand.mean() * (1 + 0.5 * np.sin(np.arange(n) / 37.0)) + rng.normal(0, 50, n)
        fossil = demand - nuclear - wind
        # Coal share of fossil output is fixed, so the marginal factor is constant and known.
        coal_share = (TRUE_MEF - 0.437) / (1.050 - 0.437)
        df = pd.DataFrame({
            "ba": ba, "utc": idx, "local": idx,
            "demand": demand, "net_generation": demand,
            "gen_coal": fossil * coal_share + rng.normal(0, 5, n),
            "gen_natural_gas": fossil * (1 - coal_share) + rng.normal(0, 5, n),
            "gen_nuclear": nuclear, "gen_wind": wind,
            "gen_solar": np.clip(np.sin(2 * np.pi * (idx.hour.values - 6) / 24), 0, None) * 10,
            "gen_all_petroleum_products": 0.0,
            "gen_hydropower_and_pumped_storage": 100.0,
        })
        # A few bad values, as in the real feed.
        bad = rng.choice(n, 30, replace=False)
        df.loc[bad[:10], "demand"] = 0.0
        df.loc[bad[10:20], "demand"] *= 40
        df.loc[bad[20:], "demand"] = np.nan
        bals.append(df)
    bal = pd.concat(bals, ignore_index=True)
    for c in bal.columns:
        if c not in ("ba", "utc", "local"):
            bal[c] = bal[c].astype("float32")
    return bal, sub
