"""Grid and data centers: statistical analysis of EIA-930 hourly data.

Reads the two parquet files written by fetch_data.py and writes docs/data/results.json,
which the website reads. Run:  python src/analysis.py

Methods
  1. Cleaning        rolling-median outlier filter, short-gap interpolation, coverage rules
  2. Baseload trend  piecewise log-linear trend with month effects, Newey-West errors
  3. Structural break  sup-F test for a kink in Dominion's share of PJM load, block bootstrap
  4. Synthetic control  Dominion zone vs. a weighted mix of other PJM zones, placebo inference
  5. Marginal emissions  hourly first-difference regressions with HAC errors, by region and year
  6. Marginal fuel mix   which fuels move when generation moves
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

warnings.filterwarnings("ignore", category=FutureWarning)

T0 = pd.Timestamp(C.TREATMENT_START)
FUEL_GROUPS = ["coal", "gas", "nuclear", "hydro", "wind", "solar", "other"]


# ----------------------------------------------------------------------------- helpers
def r(x, nd=3):
    """Round for JSON; NaN and inf become None."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, nd)


def rl(values, nd=3):
    return [r(v, nd) for v in values]


def month_labels(idx) -> list[str]:
    return [pd.Timestamp(t).strftime("%Y-%m") for t in idx]


def fuel_group(col: str) -> str | None:
    """Map an EIA fuel column (gen_...) to an analysis group."""
    if not col.startswith("gen_"):
        return None
    c = col[4:]
    if "coal" in c:
        return "coal"
    if "natural_gas" in c or c == "gas":
        return "gas"
    if "nuclear" in c:
        return "nuclear"
    if "petroleum" in c or c == "oil":
        return "oil"
    if "solar" in c:
        return "solar"
    if "wind" in c:
        return "wind"
    if "hydro" in c or "pumped" in c:
        return "hydro"
    return "other"


# ----------------------------------------------------------------------------- cleaning
def clean_hourly(wide: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove impossible values and spikes from hourly demand; fill gaps of up to 6 hours."""
    full = pd.date_range(wide.index.min(), wide.index.max(), freq="h")
    wide = wide.reindex(full).astype("float64")
    out, report = {}, {}
    for col in wide.columns:
        s = wide[col].copy()
        n_obs = int(s.notna().sum())
        s[s <= 0] = np.nan
        med = s.rolling(169, center=True, min_periods=48).median()
        ratio = s / med
        s[(ratio > 2.5) | (ratio < 0.4)] = np.nan
        flagged = n_obs - int(s.notna().sum())
        s = s.interpolate(limit=6, limit_area="inside")
        out[col] = s
        report[col] = {"hours_reported": n_obs, "hours_flagged": flagged,
                       "share_flagged_pct": r(100 * flagged / max(n_obs, 1), 3)}
    return pd.DataFrame(out, index=full), report


def monthly_stats(hourly: pd.DataFrame, min_coverage: float = 0.9) -> dict[str, pd.DataFrame]:
    """Monthly mean, 5th percentile (baseload) and peak; months under 90% coverage are blank."""
    g = hourly.groupby(pd.Grouper(freq="MS"))
    hours_in_month = pd.Series(g.size().index.days_in_month * 24, index=g.size().index)
    coverage = g.count().div(hours_in_month, axis=0)
    ok = coverage >= min_coverage
    return {"mean": g.mean().where(ok), "p05": g.quantile(0.05).where(ok),
            "max": g.max().where(ok), "coverage": coverage}


# ----------------------------------------------------------------------------- trends
def piecewise_trend(series: pd.Series) -> dict | None:
    """log(y) = month effects + b1*t + b2*max(t - t0, 0), with Newey-West standard errors.

    b1 is the yearly growth rate before the AI build-out, b1 + b2 after it; the test on b2
    asks whether growth changed.
    """
    s = series.dropna()
    s = s[s > 0]
    if len(s) < 36 or (s.index < T0).sum() < 18 or (s.index >= T0).sum() < 12:
        return None
    t = np.asarray((s.index - T0).days / 365.25, dtype=float)
    X = pd.DataFrame({"t": t, "t_post": np.clip(t, 0, None)}, index=s.index)
    months = pd.get_dummies(s.index.month, prefix="m", drop_first=True, dtype=float)
    months.index = s.index
    X = sm.add_constant(pd.concat([X, months], axis=1))
    fit = sm.OLS(np.log(s.values), X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    b1, b2 = fit.params["t"], fit.params["t_post"]
    cov = fit.cov_params()
    se_post = float(np.sqrt(cov.loc["t", "t"] + cov.loc["t_post", "t_post"] + 2 * cov.loc["t", "t_post"]))
    pct = lambda b: 100 * (np.exp(b) - 1)  # noqa: E731
    return {
        "growth_before_pct": r(pct(b1), 2),
        "growth_before_ci": [r(pct(b1 - 1.96 * fit.bse["t"]), 2), r(pct(b1 + 1.96 * fit.bse["t"]), 2)],
        "growth_after_pct": r(pct(b1 + b2), 2),
        "growth_after_ci": [r(pct(b1 + b2 - 1.96 * se_post), 2), r(pct(b1 + b2 + 1.96 * se_post), 2)],
        "change_pct_points": r(pct(b1 + b2) - pct(b1), 2),
        "change_p_value": r(fit.pvalues["t_post"], 4),
        "n_months": int(len(s)),
    }


def rolling_index(series: pd.Series, base_year: int = 2019) -> pd.Series:
    """12-month rolling mean, scaled so the base-year average equals 100."""
    base = series[series.index.year == base_year].mean()
    roll = series.rolling(12, min_periods=11).mean()
    return 100 * roll / base if np.isfinite(base) and base > 0 else roll * np.nan


# ----------------------------------------------------------------------------- break test
def _sup_f(y: np.ndarray, t: np.ndarray, seas: np.ndarray, candidates: np.ndarray):
    X0 = np.column_stack([np.ones_like(t), t, seas])
    beta0, *_ = np.linalg.lstsq(X0, y, rcond=None)
    rss0 = float(np.sum((y - X0 @ beta0) ** 2))
    best_f, best_k = -np.inf, int(candidates[0])
    for k in candidates:
        X1 = np.column_stack([X0, np.clip(t - t[k], 0, None)])
        beta1, *_ = np.linalg.lstsq(X1, y, rcond=None)
        rss1 = float(np.sum((y - X1 @ beta1) ** 2))
        dof = len(y) - X1.shape[1]
        f = (rss0 - rss1) / (rss1 / dof) if rss1 > 0 and dof > 0 else -np.inf
        if f > best_f:
            best_f, best_k = f, int(k)
    return best_f, best_k, beta0, X0


def trend_break_test(series: pd.Series, n_boot: int = 999, block: int = 6) -> dict | None:
    """Sup-F test for one kink in a linear trend at an unknown date (middle 70% of the sample).

    The p-value comes from a moving-block bootstrap of the no-break model's residuals,
    which keeps their serial correlation.
    """
    s = series.dropna()
    n = len(s)
    if n < 48:
        return None
    rng = np.random.default_rng(C.RANDOM_SEED)
    y = s.values.astype(float)
    t = np.arange(n, dtype=float) / 12.0
    seas = np.zeros((n, 11))
    for j, m in enumerate(s.index.month):
        if m > 1:
            seas[j, m - 2] = 1.0
    cand = np.arange(int(0.15 * n), int(0.85 * n))
    f_obs, k_obs, beta0, X0 = _sup_f(y, t, seas, cand)
    fitted0 = X0 @ beta0
    resid = y - fitted0
    n_blocks = int(np.ceil(n / block))
    exceed = 0
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=n_blocks)
        e = np.concatenate([resid[a:a + block] for a in starts])[:n]
        f_b, *_ = _sup_f(fitted0 + e - e.mean(), t, seas, cand)
        exceed += f_b >= f_obs
    # Slopes on either side of the estimated break.
    X1 = np.column_stack([X0, np.clip(t - t[k_obs], 0, None)])
    beta1, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return {
        "break_month": s.index[k_obs].strftime("%Y-%m"),
        "sup_f": r(f_obs, 2),
        "p_value": r((exceed + 1) / (n_boot + 1), 4),
        "slope_before_per_year": r(beta1[1], 4),
        "slope_after_per_year": r(beta1[1] + beta1[-1], 4),
        "n_months": n, "bootstrap_draws": n_boot,
    }


# ----------------------------------------------------------------------------- synthetic control
def _scm_weights(y_pre: np.ndarray, X_pre: np.ndarray) -> np.ndarray:
    """Non-negative weights summing to one that best reproduce the pre-period path."""
    k = X_pre.shape[1]
    G, c = X_pre.T @ X_pre, X_pre.T @ y_pre
    obj = lambda w: float(w @ G @ w - 2 * c @ w)  # noqa: E731
    jac = lambda w: 2 * (G @ w - c)  # noqa: E731
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(k)},)
    best = None
    starts = [np.full(k, 1.0 / k)] + [np.eye(k)[i] * 0.9 + 0.1 / k for i in range(k)]
    for w0 in starts:
        res = minimize(obj, w0, jac=jac, bounds=[(0.0, 1.0)] * k, constraints=cons,
                       method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
        if best is None or res.fun < best.fun:
            best = res
    w = np.clip(best.x, 0, None)
    return w / w.sum()


def _scm_fit(panel: pd.DataFrame, treated: str, donors: list[str], pre: np.ndarray) -> dict:
    y = panel[treated].values
    X = panel[donors].values
    w = _scm_weights(y[pre], X[pre])
    gap = y - X @ w
    rmspe_pre = float(np.sqrt(np.mean(gap[pre] ** 2)))
    rmspe_post = float(np.sqrt(np.mean(gap[~pre] ** 2)))
    return {"weights": w, "synthetic": X @ w, "gap": gap, "rmspe_pre": rmspe_pre,
            "rmspe_post": rmspe_post,
            "ratio": rmspe_post / rmspe_pre if rmspe_pre > 0 else np.nan}


def synthetic_control(monthly_mean: pd.DataFrame, treated: str, detrend: bool = False,
                      exclude: tuple[str, ...] = (), t0: pd.Timestamp = T0) -> dict | None:
    """Synthetic control on log monthly demand, each zone measured against its own pre-period mean.

    detrend=True also removes each zone's own pre-period linear trend (extended forward),
    so the gap measures acceleration beyond what the zone was already doing.
    Inference: every donor zone is treated as a placebo; the p-value is the rank of the
    treated zone's post/pre RMSPE ratio among all zones.
    """
    if treated not in monthly_mean.columns:
        return None
    monthly_mean = monthly_mean.drop(columns=[c for c in exclude if c in monthly_mean.columns])
    last_ok = monthly_mean[treated].last_valid_index()
    df = monthly_mean.loc[:last_ok]
    keep = [c for c in df.columns if df[c].notna().mean() >= 0.97 and (df[c].dropna() > 0).all()]
    if treated not in keep or len(keep) < 6:
        return None
    df = df[keep].dropna()
    pre = np.asarray(df.index < t0)
    if pre.sum() < 24 or (~pre).sum() < 12:
        return None
    logp = np.log(df)
    panel = logp - logp[pre].mean()
    if detrend:
        t = np.arange(len(df), dtype=float)
        for c in panel.columns:
            slope, intercept = np.polyfit(t[pre], panel[c].values[pre], 1)
            panel[c] = panel[c] - (intercept + slope * t)
    donors = [c for c in keep if c != treated]
    main = _scm_fit(panel, treated, donors, pre)

    placebo_ratio, placebo_gaps = {}, {}
    for d in donors:
        fit = _scm_fit(panel, d, [x for x in donors if x != d], pre)
        placebo_ratio[d] = fit["ratio"]
        placebo_gaps[d] = fit["gap"]
    ratios = np.array(list(placebo_ratio.values()))
    p_value = (1 + int(np.sum(ratios >= main["ratio"]))) / (len(ratios) + 1)

    recent = np.zeros(len(df), dtype=bool)
    recent[-12:] = True
    gap_recent = float(main["gap"][recent].mean())
    actual_recent_mw = float(df[treated].values[recent].mean())
    to_mw = lambda g: actual_recent_mw * (1 - np.exp(-g))  # noqa: E731

    # Leave-one-out: drop each donor with real weight and refit.
    loo = []
    for i, d in enumerate(donors):
        if main["weights"][i] > 0.02:
            fit = _scm_fit(panel, treated, [x for x in donors if x != d], pre)
            loo.append(float(fit["gap"][recent].mean()))
    loo = loo or [gap_recent]
    pg = np.array(list(placebo_gaps.values()))
    return {
        "treated": treated, "detrended": detrend,
        "months": month_labels(df.index),
        "treatment_start": t0.strftime("%Y-%m"),
        "actual_index": rl(100 * np.exp(panel[treated].values), 2),
        "synthetic_index": rl(100 * np.exp(main["synthetic"]), 2),
        "gap_pct": rl(100 * (np.exp(main["gap"]) - 1), 2),
        "placebo_band_pct": {"low": rl(100 * (np.exp(np.quantile(pg, 0.05, axis=0)) - 1), 2),
                             "high": rl(100 * (np.exp(np.quantile(pg, 0.95, axis=0)) - 1), 2)},
        "weights": {d: r(w, 3) for d, w in sorted(zip(donors, main["weights"]), key=lambda z: -z[1])
                    if w > 0.005},
        "n_donors": len(donors),
        "rmspe_pre_pct": r(100 * main["rmspe_pre"], 2),
        "rmspe_ratio": r(main["ratio"], 2),
        "placebo_p_value": r(p_value, 3),
        "rank": f"{1 + int(np.sum(ratios >= main['ratio']))} of {len(ratios) + 1}",
        "recent_gap_pct": r(100 * (np.exp(gap_recent) - 1), 2),
        "recent_gap_mw": r(to_mw(gap_recent), 0),
        "recent_gap_mw_leave_one_out": [r(to_mw(min(loo)), 0), r(to_mw(max(loo)), 0)],
        "recent_actual_mw": r(actual_recent_mw, 0),
        "recent_window": [df.index[-12].strftime("%Y-%m"), df.index[-1].strftime("%Y-%m")],
    }


# ----------------------------------------------------------------------------- emissions
def prepare_generation(bal: pd.DataFrame, ba: str) -> pd.DataFrame | None:
    """Hourly demand, generation by fuel group and estimated CO2 for one balancing authority."""
    d = bal[bal["ba"] == ba].set_index("utc").sort_index()
    d = d[~d.index.duplicated(keep="last")]
    if d.empty:
        return None
    out = pd.DataFrame(index=d.index)
    groups: dict[str, list[str]] = {}
    for col in d.columns:
        g = fuel_group(col)
        if g:
            groups.setdefault(g, []).append(col)
    for g, cols in groups.items():
        out[g] = d[cols].astype("float64").sum(axis=1, min_count=1)
    for g in ("coal", "gas", "oil"):
        if g in out:
            out[g] = out[g].clip(lower=0)
        else:
            out[g] = np.nan
    if out[["coal", "gas"]].notna().sum().sum() == 0:
        return None
    out["co2"] = sum(C.EMISSION_FACTORS[g] * out[g].fillna(0) for g in ("coal", "gas", "oil"))
    out.loc[out[["coal", "gas"]].isna().all(axis=1), "co2"] = np.nan
    fuel_cols = [c for c in out.columns if c != "co2"]
    out["generation"] = out[fuel_cols].sum(axis=1, min_count=1)
    out["other"] = out.get("other", 0) if "other" in out else 0.0
    out["other"] = out["other"].fillna(0) + out["oil"].fillna(0)
    out["demand"] = d["demand"].astype("float64") if "demand" in d else np.nan
    out.loc[out["demand"] <= 0, "demand"] = np.nan
    out.loc[out["generation"] <= 0, ["generation", "co2"]] = np.nan
    return out.reindex(pd.date_range(out.index.min(), out.index.max(), freq="h"))


def _robust_keep(*arrays: np.ndarray, z: float = 8.0) -> np.ndarray:
    """Keep rows where every array is finite and within z robust standard deviations."""
    keep = np.ones(len(arrays[0]), dtype=bool)
    for a in arrays:
        keep &= np.isfinite(a)
    for a in arrays:
        v = a[keep]
        if len(v) == 0:
            continue
        med = np.median(v)
        mad = 1.4826 * np.median(np.abs(v - med))
        if mad > 0:
            keep &= np.abs(a - med) <= z * mad
    return keep


def _mef_design(g: pd.DataFrame):
    """Hourly changes in CO2 and demand, with changes in wind and solar output as controls.

    Wind and solar do not respond to demand, but they ramp at the same hours demand does.
    Controlling for them keeps their ramps from being mistaken for the grid's response to load.
    """
    dy = g["co2"].diff().values
    dx = g["demand"].diff().values
    controls = []
    for c in ("wind", "solar"):
        if c in g.columns and g[c].notna().sum() > 1000 and np.nanstd(g[c].values) > 0:
            controls.append(np.nan_to_num(g[c].diff().values, nan=0.0))
    return dy, dx, controls


def marginal_emission_factor(g: pd.DataFrame, mask: np.ndarray | None = None) -> dict | None:
    """Extra tonnes of CO2 per extra MWh of demand, from hourly first differences (HAC errors)."""
    dy, dx, controls = _mef_design(g)
    keep = _robust_keep(dx, dy)
    if mask is not None:
        keep &= mask
    if keep.sum() < 2000 or np.nanstd(dx[keep]) == 0:
        return None
    X = np.column_stack([np.ones(keep.sum()), dx[keep]]
                        + [c[keep] for c in controls if np.std(c[keep]) > 0])
    fit = sm.OLS(dy[keep], X).fit(cov_type="HAC", cov_kwds={"maxlags": 24})
    b, se = float(fit.params[1]), float(fit.bse[1])
    return {"mef": r(b, 4), "ci": [r(b - 1.96 * se, 4), r(b + 1.96 * se, 4)],
            "se": r(se, 5), "r2": r(fit.rsquared, 3), "n_hours": int(keep.sum())}


def mef_change_test(g: pd.DataFrame) -> dict | None:
    """Did the marginal emission factor change after the build-out began? (interaction test)"""
    dy, dx, controls = _mef_design(g)
    keep = _robust_keep(dx, dy)
    post = np.asarray(g.index >= T0, dtype=float)
    if keep.sum() < 5000 or post[keep].sum() < 2000 or (1 - post[keep]).sum() < 2000:
        return None
    cols = [np.ones(keep.sum()), dx[keep], post[keep], dx[keep] * post[keep]]
    for c in controls:
        cols += [v for v in (c[keep], c[keep] * post[keep]) if np.std(v) > 0]
    fit = sm.OLS(dy[keep], np.column_stack(cols)).fit(cov_type="HAC", cov_kwds={"maxlags": 24})
    b, c = float(fit.params[1]), float(fit.params[3])
    cov = fit.cov_params()
    se_after = float(np.sqrt(cov[1, 1] + cov[3, 3] + 2 * cov[1, 3]))
    return {"before": r(b, 4), "after": r(b + c, 4),
            "before_ci": [r(b - 1.96 * fit.bse[1], 4), r(b + 1.96 * fit.bse[1], 4)],
            "after_ci": [r(b + c - 1.96 * se_after, 4), r(b + c + 1.96 * se_after, 4)],
            "change": r(c, 4), "change_ci": [r(c - 1.96 * fit.bse[3], 4), r(c + 1.96 * fit.bse[3], 4)],
            "p_value": r(fit.pvalues[3], 4), "n_hours": int(keep.sum())}


DISPATCHABLE = ["gas", "coal", "hydro", "nuclear", "other"]


def marginal_fuel_mix(g: pd.DataFrame, mask: np.ndarray) -> dict | None:
    """Which sources answer one extra MWh of demand, holding wind and solar output fixed.

    Each dispatchable source's hourly change is regressed on the change in demand. What the
    region's own plants do not cover is met by imports (or lower exports).
    """
    _, dx, controls = _mef_design(g)
    keep = _robust_keep(dx) & mask
    for c in DISPATCHABLE:
        if c in g.columns:
            keep &= np.isfinite(g[c].diff().values)
    if keep.sum() < 2000:
        return None
    X = np.column_stack([np.ones(keep.sum()), dx[keep]]
                        + [c[keep] for c in controls if np.std(c[keep]) > 0])
    out = {}
    for c in DISPATCHABLE:
        if c in g.columns:
            out[c] = r(float(np.linalg.lstsq(X, g[c].diff().values[keep], rcond=None)[0][1]), 4)
    out["imports"] = r(1 - sum(v for v in out.values() if v is not None), 4)
    return out


def yearly_mix(g: pd.DataFrame) -> dict:
    cols = [c for c in FUEL_GROUPS if c in g.columns]
    yearly = g[cols].clip(lower=0).groupby(g.index.year).sum()
    share = yearly.div(yearly.sum(axis=1), axis=0)
    counts = g["generation"].groupby(g.index.year).count()
    ok = counts[counts >= 24 * 300].index
    share = share.loc[share.index.intersection(ok)]
    return {"years": [int(y) for y in share.index], **{c: rl(100 * share[c], 2) for c in cols}}


# ----------------------------------------------------------------------------- main
def run(balance_path: Path = C.BALANCE_FILE, subregion_path: Path = C.SUBREGION_FILE,
        out_path: Path | None = C.RESULTS_FILE, n_boot: int = 999) -> dict:
    bal = pd.read_parquet(balance_path)
    sub = pd.read_parquet(subregion_path)
    bal["utc"] = pd.to_datetime(bal["utc"])
    sub["utc"] = pd.to_datetime(sub["utc"])
    start = pd.Timestamp(f"{C.START_YEAR}-01-01")
    bal, sub = bal[bal["utc"] >= start], sub[sub["utc"] >= start]

    # ---- demand panels
    ba_wide = bal.pivot_table(index="utc", columns="ba", values="demand", aggfunc="last")
    zone_wide = sub.pivot_table(index="utc", columns="zone", values="demand", aggfunc="last")
    ba_clean, ba_report = clean_hourly(ba_wide)
    zone_clean, zone_report = clean_hourly(zone_wide)
    ba_m, zone_m = monthly_stats(ba_clean), monthly_stats(zone_clean)

    zm = zone_m["mean"]
    core = [z for z in zm.columns if zm[z].notna().mean() >= 0.97]
    if C.TREATED_ZONE not in core:
        raise RuntimeError(f"Zone {C.TREATED_ZONE} lacks enough valid months for the analysis.")
    hot = [z for z in C.HOT_ZONES if z in core]
    others = [z for z in core if z not in hot]
    pjm_total = zm[core].sum(axis=1, min_count=len(core))
    rest_hourly = zone_clean[others].sum(axis=1, min_count=len(others))
    rest_m = monthly_stats(rest_hourly.to_frame("rest"))

    # ---- 1. growth in baseload and average demand
    regions = {}
    series_sets = {ba: (ba_m["mean"][ba], ba_m["p05"][ba], C.BALANCING_AUTHORITIES[ba])
                   for ba in ba_m["mean"].columns if ba in C.BALANCING_AUTHORITIES}
    for z in hot:
        series_sets[f"{z}_ZONE"] = (zm[z], zone_m["p05"][z], C.HOT_ZONES[z])
    series_sets["PJM_REST"] = (rest_m["mean"]["rest"], rest_m["p05"]["rest"],
                               f"Rest of PJM ({len(others)} zones)")
    month_axis = ba_m["mean"].index.union(zm.index)
    for key, (mean_s, p05_s, label) in series_sets.items():
        base_trend, mean_trend = piecewise_trend(p05_s), piecewise_trend(mean_s)
        if base_trend is None or mean_trend is None:
            continue
        regions[key] = {
            "label": label,
            "baseload_trend": base_trend, "mean_trend": mean_trend,
            "baseload_index": rl(rolling_index(p05_s).reindex(month_axis), 2),
            "mean_index": rl(rolling_index(mean_s).reindex(month_axis), 2),
            "latest_12m_mean_mw": r(mean_s.dropna().tail(12).mean(), 0),
        }

    # ---- zone-by-zone change in growth (which zones sped up, and by how much)
    zone_trends = []
    for z in core:
        mt, bt = piecewise_trend(zm[z]), piecewise_trend(zone_m["p05"][z])
        if mt and bt:
            zone_trends.append({"zone": z, "hot": z in hot, "mean": mt, "baseload": bt,
                                "latest_12m_mean_mw": r(zm[z].dropna().tail(12).mean(), 0)})
    zone_trends.sort(key=lambda d: -d["mean"]["change_pct_points"])

    # ---- 2. each hot zone's share of PJM load, and the break test
    share_out = {}
    for z in hot:
        share = (100 * zm[z] / pjm_total).dropna()
        share_out[z] = {
            "months": month_labels(share.index), "share_pct": rl(share, 3),
            "share_12m_pct": rl(share.rolling(12, min_periods=11).mean(), 3),
            "first_year_avg_pct": r(share[share.index.year == share.index.year.min()].mean(), 2),
            "latest_12m_avg_pct": r(share.tail(12).mean(), 2),
            "break_test": trend_break_test(share, n_boot=n_boot), "n_zones": len(core),
        }

    # ---- 3. synthetic control (each hot zone is kept out of the other's comparison pool)
    scm_all = {}
    for z in hot:
        excl = tuple(h for h in hot if h != z)
        raw = synthetic_control(zm[core], z, detrend=False, exclude=excl)
        if raw is None:
            raise RuntimeError(f"Synthetic control for {z} could not be estimated.")
        # Placebo in time: pretend the build-out began two years early, using only pre-2023 data.
        fake = synthetic_control(zm[core].loc[zm.index < T0], z, exclude=excl,
                                 t0=T0 - pd.DateOffset(years=2))
        raw["placebo_in_time"] = None if fake is None else {
            "fake_start": fake["treatment_start"], "gap_pct": fake["recent_gap_pct"],
            "rank": fake["rank"], "p_value": fake["placebo_p_value"]}
        scm_all[z] = {"levels": raw,
                      "acceleration": synthetic_control(zm[core], z, detrend=True, exclude=excl)}

    # ---- load factor (flat, round-the-clock load raises it)
    def load_factor(hourly: pd.Series) -> dict:
        by = hourly.groupby(hourly.index.year)
        ok = by.count() >= 24 * 330
        lf = (by.mean() / by.quantile(0.999))[ok]   # 99.9th percentile as the peak
        return {"years": [int(y) for y in lf.index], "load_factor_pct": rl(100 * lf, 2)}

    load_factors = {f"{z}_ZONE": load_factor(zone_clean[z]) for z in hot}
    load_factors["PJM_REST"] = load_factor(rest_hourly)

    # ---- 4-6. emissions
    emissions, pjm_gen = {}, None
    for ba, label in C.BALANCING_AUTHORITIES.items():
        g = prepare_generation(bal, ba)
        if g is None:
            continue
        if ba == C.SUBREGION_PARENT:
            pjm_gen = g
        yearly, years = [], sorted(set(g.index.year))
        for y in years:
            mask = np.asarray(g.index.year == y)
            est = marginal_emission_factor(g, mask)
            gy = g[mask]
            both = gy["co2"].notna() & gy["generation"].notna()
            if est is None or both.sum() < 24 * 200:
                continue
            est["year"] = int(y)
            est["average_intensity"] = r(gy.loc[both, "co2"].sum() / gy.loc[both, "generation"].sum(), 4)
            est["partial_year"] = bool(both.sum() < 24 * 350)
            yearly.append(est)
        if len(yearly) < 3:
            continue
        pre_mask, post_mask = np.asarray(g.index < T0), np.asarray(g.index >= T0)
        emissions[ba] = {
            "label": label, "by_year": yearly,
            "change_test": mef_change_test(g),
            "marginal_mix_before": marginal_fuel_mix(g, pre_mask),
            "marginal_mix_after": marginal_fuel_mix(g, post_mask),
            "generation_mix": yearly_mix(g),
        }

    # ---- headline: what the extra load in the hot zones implies for emissions
    headline = None
    pjm = emissions.get(C.SUBREGION_PARENT)
    if pjm and pjm.get("change_test"):
        mef, mef_ci = pjm["change_test"]["after"], pjm["change_test"]["after_ci"]
        aef = [y["average_intensity"] for y in pjm["by_year"] if not y["partial_year"]][-1]
        mt = lambda mw_, f: mw_ * 8760 * f / 1e6  # noqa: E731

        def total(kind: str) -> dict | None:
            fits = [scm_all[z][kind] for z in hot]
            if any(f is None for f in fits):
                return None
            mw = sum(f["recent_gap_mw"] for f in fits)
            lo = sum(min(f["recent_gap_mw_leave_one_out"]) for f in fits)
            hi = sum(max(f["recent_gap_mw_leave_one_out"]) for f in fits)
            return {"by_zone_mw": {z: f["recent_gap_mw"] for z, f in zip(hot, fits)},
                    "extra_load_mw": r(mw, 0), "extra_load_mw_range": [r(lo, 0), r(hi, 0)],
                    "extra_twh_per_year": r(mw * 8760 / 1e6, 1),
                    "mt_co2_per_year": r(mt(mw, mef), 1),
                    "mt_co2_range": [r(mt(lo, mef_ci[0]), 1), r(mt(hi, mef_ci[1]), 1)],
                    "mt_co2_if_average_factor": r(mt(mw, aef), 1)}

        headline = {
            "zones": hot, "window": scm_all[hot[0]]["levels"]["recent_window"],
            # beyond each zone's own pre-2023 trend (the stricter reading)
            "since_2023": total("acceleration"),
            # all divergence from comparison zones since the 2019-22 baseline
            "since_baseline": total("levels"),
            "pjm_marginal_factor": mef, "pjm_marginal_factor_ci": mef_ci,
            "pjm_average_factor": aef,
            "marginal_vs_average_pct": r(100 * (mef / aef - 1), 1) if aef else None,
        }

    # ---- most recent week on the PJM grid
    latest = None
    if pjm_gen is not None:
        tail = pjm_gen.dropna(subset=["generation"]).tail(24 * 7)
        if len(tail) >= 24:
            latest = {"hours_utc": [t.strftime("%Y-%m-%d %H:%M") for t in tail.index],
                      "demand_mw": rl(tail["demand"], 0),
                      "intensity": rl(tail["co2"] / tail["generation"], 4),
                      **{f: rl(tail[f].clip(lower=0), 0) for f in FUEL_GROUPS if f in tail}}

    results = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "source": "U.S. Energy Information Administration, Form EIA-930 (Hourly Electric Grid Monitor)",
            "data_start": str(bal["utc"].min())[:10], "data_end": str(bal["utc"].max())[:16],
            "hours_analyzed": int(len(ba_clean)), "treatment_start": T0.strftime("%Y-%m"),
            "treated_zone": C.TREATED_ZONE, "hot_zones": {z: C.HOT_ZONES[z] for z in hot},
            "zones_used": core,
            "emission_factors_t_per_mwh": C.EMISSION_FACTORS,
            "months": month_labels(month_axis),
            "cleaning": {"balancing_authorities": ba_report,
                         "zones": {z: zone_report[z] for z in core}},
        },
        "regions": regions, "zone_trends": zone_trends, "zone_share": share_out,
        "synthetic_control": scm_all,
        "load_factor": load_factors, "emissions": emissions,
        "headline": headline, "latest_week_pjm": latest,
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(results, separators=(",", ":"), allow_nan=False)
        out_path.write_text(text)
        print(f"Wrote {out_path} ({len(text) / 1e3:.0f} kB)")
    return results


def summarize(res: dict) -> None:
    h = res["headline"]
    print(f"Data: {res['meta']['data_start']} to {res['meta']['data_end']}")
    for z, sh in res["zone_share"].items():
        print(f"{z} share of PJM: {sh['first_year_avg_pct']}% -> {sh['latest_12m_avg_pct']}%; "
              f"break {sh['break_test']}")
    for z, both in res["synthetic_control"].items():
        for kind, s in both.items():
            if s:
                print(f"SCM {z} {kind}: gap {s['recent_gap_pct']}% = {s['recent_gap_mw']} MW "
                      f"(loo {s['recent_gap_mw_leave_one_out']}), p={s['placebo_p_value']} "
                      f"rank {s['rank']}, pre-RMSPE {s['rmspe_pre_pct']}%, weights {s['weights']}")
    for zt in res["zone_trends"]:
        m = zt["mean"]
        print(f"  zone {zt['zone']:5s} mean growth {m['growth_before_pct']:>6}%/yr -> "
              f"{m['growth_after_pct']:>6}%/yr (change {m['change_pct_points']}, p={m['change_p_value']})")
    for k, v in res["regions"].items():
        b = v["baseload_trend"]
        print(f"  {k:9s} baseload growth {b['growth_before_pct']:>6}%/yr -> {b['growth_after_pct']:>6}%/yr "
              f"(p={b['change_p_value']})")
    for k, v in res["emissions"].items():
        c = v["change_test"]
        if c:
            print(f"  {k:5s} MEF {c['before']} -> {c['after']} (p={c['p_value']}); "
                  f"AEF latest {v['by_year'][-1]['average_intensity']}; mix after {v['marginal_mix_after']}")
    print(f"Load factor: {res['load_factor']}")
    print(f"Headline: {h}")


if __name__ == "__main__":
    summarize(run())
