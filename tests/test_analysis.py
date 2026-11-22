import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analysis as A  # noqa: E402
import fetch_data as F  # noqa: E402
import synthetic  # noqa: E402


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    bal, sub = synthetic.make()
    bal.to_parquet(d / "bal.parquet")
    sub.to_parquet(d / "sub.parquet")
    return A.run(d / "bal.parquet", d / "sub.parquet", d / "results.json", n_boot=99), d


def test_output_is_valid_json(results):
    res, d = results
    loaded = json.loads((d / "results.json").read_text())
    for key in ("meta", "regions", "dominion_share", "synthetic_control", "emissions", "headline"):
        assert loaded[key] is not None


def test_synthetic_control_recovers_planted_effect(results):
    scm = results[0]["synthetic_control"]
    # DOM gains 10%/yr extra after 2023; the last 12 months of a 3-year post period average ~2.5 years in.
    expected = 100 * (np.exp(synthetic.TRUE_EXTRA_GROWTH * 2.5) - 1)
    assert abs(scm["recent_gap_pct"] - expected) < 4
    assert scm["rmspe_pre_pct"] < 2
    assert scm["placebo_p_value"] <= 0.11  # smallest possible with 9 donors is 0.10
    assert abs(sum(scm["weights"].values()) - 1) < 0.05


def test_marginal_emission_factor_recovered(results):
    pjm = results[0]["emissions"]["PJM"]
    for year in pjm["by_year"]:
        assert abs(year["mef"] - synthetic.TRUE_MEF) < 0.03
    assert pjm["change_test"]["p_value"] > 0.01  # nothing changed in the synthetic grid


def test_break_test_finds_the_kink(results):
    brk = results[0]["dominion_share"]["break_test"]
    assert brk["p_value"] < 0.05
    assert abs(pd.Timestamp(brk["break_month"]) - pd.Timestamp("2023-01-01")).days < 240


def test_growth_change_detected_only_where_planted(results):
    regions = results[0]["regions"]
    assert regions["DOM_ZONE"]["mean_trend"]["change_pct_points"] > 5
    assert abs(regions["PJM_REST"]["mean_trend"]["change_pct_points"]) < 2


def test_cleaning_removes_spikes():
    idx = pd.date_range("2024-01-01", periods=24 * 60, freq="h")
    s = pd.Series(1000.0, index=idx)
    s.iloc[100], s.iloc[200], s.iloc[300] = 0.0, 50000.0, np.nan
    clean, report = A.clean_hourly(s.to_frame("x"))
    assert clean["x"].between(900, 1100).all()
    assert report["x"]["hours_flagged"] == 2


def test_fuel_grouping():
    assert A.fuel_group("gen_natural_gas") == "gas"
    assert A.fuel_group("gen_hydropower_and_pumped_storage") == "hydro"
    assert A.fuel_group("gen_solar_with_integrated_battery_storage") == "solar"
    assert A.fuel_group("gen_battery_storage") == "other"
    assert A.fuel_group("demand") is None


def test_balance_parser_handles_commas_and_renamed_columns(tmp_path):
    csv = tmp_path / "EIA930_BALANCE_2099_Jan_Jun.csv"
    csv.write_text(
        '"Balancing Authority","Data Date","Hour Number","Local Time at End of Hour",'
        '"UTC Time at End of Hour","Demand (MW)","Demand (MW) (Adjusted)","Net Generation (MW)",'
        '"Net Generation (MW) from Coal","Net Generation (MW) from Coal (Adjusted)",'
        '"Net Generation (MW) from Natural Gas (Adjusted)","Net Generation (MW) from Natural-Gas  (Adjusted)"\n'
        '"PJM","01/01/2099","1","01/01/2099 1:00:00 AM","01/01/2099 6:00:00 AM",'
        '"90,000","91,000","95,000","20,000","21,000","30,000","1,000"\n'
        '"ZZZ","01/01/2099","1","01/01/2099 1:00:00 AM","01/01/2099 6:00:00 AM",'
        '"1","1","1","1","1","1","1"\n')
    df = F.load_balance(csv)
    assert len(df) == 1 and df["ba"].iloc[0] == "PJM"
    assert df["demand"].iloc[0] == 91000          # adjusted column preferred
    assert df["gen_coal"].iloc[0] == 21000
    assert df["gen_natural_gas"].iloc[0] == 31000  # two spellings merged
    assert df["utc"].iloc[0] == pd.Timestamp("2099-01-01 06:00")
