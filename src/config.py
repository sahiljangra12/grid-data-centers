"""Shared settings for the grid and data centers study."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"            # large downloads, never committed
PROCESSED_DIR = ROOT / "data" / "processed"
SITE_DATA_DIR = ROOT / "docs" / "data"

BALANCE_FILE = PROCESSED_DIR / "balance_hourly.parquet"
SUBREGION_FILE = PROCESSED_DIR / "subregion_hourly.parquet"
FETCH_LOG = PROCESSED_DIR / "fetch_log.json"
RESULTS_FILE = SITE_DATA_DIR / "results.json"

START_YEAR = 2019

# EIA-930 bulk files (no API key needed).
BULK_URL = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_{kind}_{year}_{half}.csv"
HALVES = ("Jan_Jun", "Jul_Dec")

# Balancing authorities kept from the national file.
BALANCING_AUTHORITIES = {
    "PJM": "PJM (Mid-Atlantic)",
    "ERCO": "ERCOT (Texas)",
    "MISO": "MISO (Midwest)",
    "SWPP": "SPP (Central)",
    "NYIS": "NYISO (New York)",
    "ISNE": "ISO-NE (New England)",
    "CISO": "CAISO (California)",
    "SOCO": "Southern Company",
    "TVA": "Tennessee Valley Authority",
    "DUK": "Duke Energy Carolinas",
}

# Sub-regions are kept for PJM only: its zones are the unit of the causal design.
SUBREGION_PARENT = "PJM"
TREATED_ZONE = "DOM"   # Dominion zone: Northern Virginia's "Data Center Alley" (chosen in advance)
# AEP (which includes central Ohio) was not chosen in advance: it surfaced in the zone-by-zone
# growth comparison as the fastest-accelerating zone. It is analysed as a second hot spot and
# kept out of Dominion's comparison pool, and vice versa.
SECOND_ZONE = "AEP"
HOT_ZONES = {"DOM": "Dominion zone (Northern Virginia)", "AEP": "AEP zone (Ohio and Appalachia)"}

# The public release of ChatGPT (30 Nov 2022) is used as the start of the AI build-out.
# Everything through December 2022 is "before"; January 2023 onward is "after".
TREATMENT_START = "2023-01-01"

# Tonnes of CO2 per MWh of net generation, from EIA's 2023 national totals
# (emissions divided by generation; https://www.eia.gov/tools/faqs/faq.php?id=74).
#   coal        709 Mt / 675,115 GWh
#   natural gas 790 Mt / 1,806,063 GWh
#   petroleum    18 Mt / 16,233 GWh
EMISSION_FACTORS = {"coal": 1.050, "gas": 0.437, "oil": 1.109}

RANDOM_SEED = 20261122
