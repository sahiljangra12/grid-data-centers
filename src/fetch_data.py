"""Download EIA-930 hourly grid data and reduce it to two compact parquet files.

Source: EIA Hourly Electric Grid Monitor bulk files (Form EIA-930), public domain,
no API key required. Run:  python src/fetch_data.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (grid-data-centers research pipeline)"}
KIND_SPELLINGS = {"BALANCE": ("BALANCE", "Balance"), "SUBREGION": ("SUBREGION", "Subregion")}
FUEL_RE = re.compile(r"^Net Generation \(MW\) from (.+?)(?: \((Imputed|Adjusted)\))?$")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def download(kind: str, year: int, half: str) -> Path | None:
    """Fetch one six-month file. Returns None when EIA has not published it."""
    dest = C.RAW_DIR / f"EIA930_{kind}_{year}_{half}.csv"
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for spelling in KIND_SPELLINGS[kind]:
        url = C.BULK_URL.format(kind=spelling, year=year, half=half)
        for attempt in range(4):
            try:
                with requests.get(url, headers=HEADERS, stream=True, timeout=(30, 300)) as r:
                    if r.status_code == 404:
                        break
                    r.raise_for_status()
                    tmp = dest.with_suffix(".part")
                    with open(tmp, "wb") as fh:
                        for block in r.iter_content(chunk_size=1 << 20):
                            fh.write(block)
                # An HTML error page instead of a CSV is treated as "not published".
                with open(tmp, "rb") as fh:
                    head = fh.read(200).lstrip(b"\xef\xbb\xbf").lstrip()
                if head[:1] == b"<" or tmp.stat().st_size < 10_000:
                    tmp.unlink()
                    break
                tmp.replace(dest)
                print(f"  downloaded {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)", flush=True)
                return dest
            except requests.RequestException as exc:
                wait = 5 * (attempt + 1)
                print(f"  retry {attempt + 1} for {url}: {exc} (waiting {wait}s)", flush=True)
                time.sleep(wait)
    return None


def parse_time(s: pd.Series) -> pd.Series:
    out = pd.to_datetime(s, format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
    if out.isna().mean() > 0.5:
        out = pd.to_datetime(s, errors="coerce")
    return out


def to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def read_header(path: Path) -> list[str]:
    return [c.strip() for c in pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns]


def pick(cols: list[str], base: str) -> str | None:
    """Prefer EIA's anomaly-adjusted column, fall back to the raw one."""
    for cand in (f"{base} (Adjusted)", base):
        if cand in cols:
            return cand
    return None


def load_balance(path: Path) -> pd.DataFrame:
    cols = read_header(path)
    need = {"Balancing Authority": "ba", "UTC Time at End of Hour": "utc",
            "Local Time at End of Hour": "local"}
    missing = [c for c in need if c not in cols]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}; found {cols[:12]}")
    mapping = dict(need)
    for base, name in (("Demand (MW)", "demand"), ("Net Generation (MW)", "net_generation")):
        col = pick(cols, base)
        if col:
            mapping[col] = name
    for extra, name in (("Demand Forecast (MW)", "demand_forecast"),
                        ("Total Interchange (MW)", "interchange")):
        if extra in cols:
            mapping[extra] = name
    fuels: dict[str, dict[str, str]] = {}
    for c in cols:
        m = FUEL_RE.match(c)
        if m:
            fuels.setdefault(m.group(1), {})[m.group(2) or "raw"] = c
    for fuel, variants in fuels.items():
        mapping[variants.get("Adjusted") or variants.get("raw") or next(iter(variants.values()))] = (
            "gen_" + slug(fuel))

    parts = []
    reader = pd.read_csv(path, dtype=str, encoding="utf-8-sig", chunksize=200_000,
                         skipinitialspace=True)
    for chunk in reader:
        chunk.columns = [c.strip() for c in chunk.columns]
        chunk = chunk[chunk["Balancing Authority"].str.strip().isin(C.BALANCING_AUTHORITIES)]
        if chunk.empty:
            continue
        chunk = chunk[list(mapping)].rename(columns=mapping)
        parts.append(chunk)
    if not parts:
        raise ValueError(f"{path.name}: none of the expected balancing authorities found")
    df = pd.concat(parts, ignore_index=True)
    df["ba"] = df["ba"].str.strip()
    df["utc"] = parse_time(df["utc"])
    df["local"] = parse_time(df["local"])
    for c in df.columns:
        if c not in ("ba", "utc", "local"):
            df[c] = to_number(df[c]).astype("float32")
    return df.dropna(subset=["utc"])


def load_subregion(path: Path) -> pd.DataFrame:
    cols = read_header(path)
    need = {"Balancing Authority": "ba", "Sub-Region": "zone", "Demand (MW)": "demand",
            "UTC Time at End of Hour": "utc", "Local Time at End of Hour": "local"}
    missing = [c for c in need if c not in cols]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}; found {cols}")
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", usecols=list(need),
                     skipinitialspace=True).rename(columns=lambda c: need[c.strip()])
    df = df[df["ba"].str.strip() == C.SUBREGION_PARENT].copy()
    df["zone"] = df["zone"].str.strip()
    df["utc"] = parse_time(df["utc"])
    df["local"] = parse_time(df["local"])
    df["demand"] = to_number(df["demand"]).astype("float32")
    return df.drop(columns="ba").dropna(subset=["utc"])


def main() -> int:
    this_year = datetime.now(timezone.utc).year
    log = {"fetched_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
           "source": "EIA Form EIA-930, Hourly Electric Grid Monitor bulk files",
           "files": []}
    balance, subregion = [], []
    for year in range(C.START_YEAR, this_year + 1):
        for half in C.HALVES:
            for kind, loader, bucket in (("BALANCE", load_balance, balance),
                                         ("SUBREGION", load_subregion, subregion)):
                path = download(kind, year, half)
                if path is None:
                    print(f"  not available: {kind} {year} {half}", flush=True)
                    continue
                df = loader(path)
                bucket.append(df)
                log["files"].append({"file": path.name, "rows_kept": int(len(df))})
                print(f"  parsed {path.name}: {len(df):,} rows", flush=True)

    if len(balance) < 8 or len(subregion) < 8:
        print(f"ERROR: too few files (balance={len(balance)}, subregion={len(subregion)}). "
              "EIA may be unreachable; nothing was written.")
        return 1

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    bal = (pd.concat(balance, ignore_index=True)
           .drop_duplicates(subset=["ba", "utc"], keep="last")
           .sort_values(["ba", "utc"]).reset_index(drop=True))
    sub = (pd.concat(subregion, ignore_index=True)
           .drop_duplicates(subset=["zone", "utc"], keep="last")
           .sort_values(["zone", "utc"]).reset_index(drop=True))
    bal.to_parquet(C.BALANCE_FILE, index=False, compression="zstd")
    sub.to_parquet(C.SUBREGION_FILE, index=False, compression="zstd")

    log.update({
        "balance_rows": int(len(bal)), "subregion_rows": int(len(sub)),
        "balance_columns": list(bal.columns),
        "zones": sorted(sub["zone"].unique().tolist()),
        "first_hour_utc": str(bal["utc"].min()), "last_hour_utc": str(bal["utc"].max()),
    })
    C.FETCH_LOG.write_text(json.dumps(log, indent=2))
    print(f"Saved {len(bal):,} balance rows and {len(sub):,} zone rows; "
          f"{log['first_hour_utc']} to {log['last_hour_utc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
