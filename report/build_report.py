"""Build the technical report (LaTeX) from docs/data/results.json.

Writes the figures and report.tex into report/, then compiles docs/report.pdf.
Every number, table and figure comes from the results file, so the report cannot
drift from the website. Run:  python report/build_report.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report"
FIG = OUT / "figures"
R = json.loads((ROOT / "docs" / "data" / "results.json").read_text())

HOT, COOL, GREY = "#c8501e", "#2f6fbf", "#8c8c8c"
ZONES = {"AE": "Atlantic City Electric", "AEP": "AEP (Ohio, Appalachia)", "AP": "Allegheny Power",
         "ATSI": "FirstEnergy Ohio", "BC": "Baltimore Gas and Electric", "CE": "ComEd (Chicago)",
         "DAY": "Dayton", "DEOK": "Duke Ohio and Kentucky", "DOM": "Dominion (Virginia)",
         "DPL": "Delmarva", "DUQ": "Duquesne (Pittsburgh)", "EKPC": "East Kentucky",
         "JC": "Jersey Central", "ME": "Met-Ed", "PE": "PECO (Philadelphia)",
         "PEP": "Pepco (Washington)", "PL": "PPL (Pennsylvania)", "PN": "Penelec",
         "PS": "PSEG (New Jersey)", "RECO": "Rockland"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["TeX Gyre Pagella", "Palatino", "DejaVu Serif"],
    "mathtext.fontset": "cm", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.5, "axes.axisbelow": True,
    "legend.frameon": False, "pdf.fonttype": 3, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})


# ----------------------------------------------------------------------------- formatting
def num(x, d=0):
    return "n/a" if x is None else f"{x:,.{d}f}"


def sgn(x, d=1):
    if x is None:
        return "n/a"
    return ("+" if x > 0 else "$-$" if x < 0 else "") + f"{abs(x):,.{d}f}"


def pv(p):
    return "n/a" if p is None else "$<$0.001" if p < 0.001 else f"{p:.3f}"


def ptext(p):
    return "n/a" if p is None else "$p<0.001$" if p < 0.001 else f"$p={p:.3f}$"


def month(m):
    y, mo = m.split("-")
    return f"{MONTHS[int(mo) - 1]} {y}"


def esc(s):
    return str(s).replace("&", r"\&").replace("%", r"\%")


def xmonths(months):
    return [int(m[:4]) + (int(m[5:7]) - 0.5) / 12 for m in months]


def roll12(a):
    out = []
    for i in range(len(a)):
        w = [v for v in a[max(0, i - 11):i + 1] if v is not None]
        out.append(sum(w) / len(w) if i >= 11 and len(w) >= 11 else None)
    return out


SC = R["synthetic_control"]
AEP, DOM, DOMA = SC["AEP"]["levels"], SC["DOM"]["levels"], SC["DOM"]["acceleration"]
H = R["headline"]
ZT = {z["zone"]: z for z in R["zone_trends"]}
BAS = [k for k in R["meta"]["cleaning"]["balancing_authorities"] if k in R["regions"]]
PJM = R["emissions"]["PJM"]


# ----------------------------------------------------------------------------- figures
def fig_zones():
    zt = R["zone_trends"][::-1]
    fig, ax = plt.subplots(figsize=(6.3, 4.4))
    vals = [z["mean"]["change_pct_points"] for z in zt]
    ax.barh([ZONES.get(z["zone"], z["zone"]) for z in zt], vals,
            color=[HOT if z["hot"] else GREY for z in zt], height=0.68)
    for i, v in enumerate(vals):
        ax.text(max(v, 0) + 0.08, i, f"{v:+.1f}", va="center", fontsize=8)
    ax.axvline(0, color="#444", lw=0.6)
    ax.set_xlabel("Change in yearly demand growth, percentage points")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(min(vals) - 0.3, max(vals) + 0.7)
    fig.savefig(FIG / "fig1_zones.pdf")
    plt.close(fig)


def _gap_panel(ax, s, title):
    x = xmonths(s["months"])
    ax.fill_between(x, s["placebo_band_pct"]["low"], s["placebo_band_pct"]["high"], color="#dcdcdc", lw=0,
                    label="90% of placebo zones")
    ax.plot(x, s["gap_pct"], color=HOT, lw=1.3, label="Gap to synthetic control")
    ax.axhline(0, color="#444", lw=0.6)
    ax.axvline(2023, color="#444", lw=0.6, ls=(0, (3, 3)))
    ax.set_title(title, fontsize=9, loc="left")
    ax.set_ylabel("Percent")


def fig_aep():
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.7))
    x = xmonths(AEP["months"])
    axes[0].plot(x, roll12(AEP["synthetic_index"]), color=COOL, lw=1.3, label="Synthetic control")
    axes[0].plot(x, roll12(AEP["actual_index"]), color=HOT, lw=1.5, label="AEP zone")
    axes[0].axvline(2023, color="#444", lw=0.6, ls=(0, (3, 3)))
    axes[0].set_title("(a) Demand, 12-month average (2019-22 = 100)", fontsize=9, loc="left")
    axes[0].legend(fontsize=8, loc="upper left")
    _gap_panel(axes[1], AEP, "(b) Monthly gap")
    axes[1].legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "fig2_aep.pdf")
    plt.close(fig)


def fig_dom():
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.7))
    _gap_panel(axes[0], DOM, "(a) Against comparison zones")
    _gap_panel(axes[1], DOMA, "(b) Beyond its own pre-2023 trend")
    axes[0].legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_dominion.pdf")
    plt.close(fig)


def fig_share():
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    for z, c, name in (("DOM", HOT, "Dominion"), ("AEP", COOL, "AEP")):
        s = R["zone_share"][z]
        x = xmonths(s["months"])
        ax.plot(x, s["share_pct"], color=c, lw=0.5, alpha=0.35)
        ax.plot(x, s["share_12m_pct"], color=c, lw=1.6, label=name)
        b = s["break_test"]["break_month"]
        i = s["months"].index(b)
        if s["share_12m_pct"][i] is not None:
            ax.plot(x[i], s["share_12m_pct"][i], "o", ms=6, mfc="white", mec=c, mew=1.4)
    ax.set_ylabel("Share of PJM demand, percent")
    ax.legend(fontsize=8, loc="upper left")
    fig.savefig(FIG / "fig4_share.pdf")
    plt.close(fig)


def fig_regions():
    keys = sorted(BAS, key=lambda k: R["regions"][k]["baseload_trend"]["growth_after_pct"])
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    for i, k in enumerate(keys):
        t = R["regions"][k]["baseload_trend"]
        sig = t["change_p_value"] < 0.05
        ax.plot([t["growth_before_pct"], t["growth_after_pct"]], [i, i], color="#555" if sig else "#c4c4c4", lw=1)
        ax.plot(t["growth_before_pct"], i, "o", ms=6, mec=COOL, mew=1.3, mfc=COOL if sig else "white")
        ax.plot(t["growth_after_pct"], i, "o", ms=6, mec=HOT, mew=1.3, mfc=HOT if sig else "white")
    ax.set_yticks(range(len(keys)), [R["regions"][k]["label"] for k in keys])
    ax.axvline(0, color="#444", lw=0.6)
    ax.set_xlabel("Baseload growth, percent per year (blue: 2019-22, orange: 2023 onward)")
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG / "fig5_regions.pdf")
    plt.close(fig)


def fig_mef():
    ys = PJM["by_year"]
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.7), gridspec_kw={"width_ratios": [1.5, 1]})
    yr = [d["year"] for d in ys]
    axes[0].errorbar(yr, [d["mef"] for d in ys],
                     yerr=[[d["mef"] - d["ci"][0] for d in ys], [d["ci"][1] - d["mef"] for d in ys]],
                     color=HOT, marker="o", ms=4, lw=1.3, capsize=2, label="Marginal")
    axes[0].plot(yr, [d["average_intensity"] for d in ys], color=COOL, marker="s", ms=4, lw=1.3, label="Average")
    axes[0].set_ylim(0, None)
    axes[0].set_ylabel("t CO$_2$ per MWh")
    axes[0].set_title("(a) PJM emission factors by year", fontsize=9, loc="left")
    axes[0].legend(fontsize=8, loc="lower left")
    parts = [("gas", "Gas"), ("coal", "Coal"), ("hydro", "Hydro and\npumped storage"), ("other", "Other plants"),
             ("imports", "Imports")]
    b, a = PJM["marginal_mix_before"], PJM["marginal_mix_after"]
    y = range(len(parts))
    axes[1].barh([i + 0.2 for i in y], [100 * (b.get(k) or 0) for k, _ in parts], height=0.38, color=COOL,
                 label="2019-22")
    axes[1].barh([i - 0.2 for i in y], [100 * (a.get(k) or 0) for k, _ in parts], height=0.38, color=HOT,
                 label="2023 on")
    axes[1].set_yticks(list(y), [n for _, n in parts])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Share of response, percent")
    axes[1].set_title("(b) What answers one more MWh", fontsize=9, loc="left")
    axes[1].grid(axis="y", visible=False)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig6_emissions.pdf")
    plt.close(fig)


# ----------------------------------------------------------------------------- tables
def table(spec, head, rows, caption, label, size=r"\small"):
    body = " \\\\\n".join(" & ".join(r) for r in rows)
    return (f"\\begin{{table}}[H]\n\\centering{size}\n\\caption{{{caption}}}\\label{{{label}}}\n"
            f"\\begin{{tabular}}{{{spec}}}\n\\toprule\n{head} \\\\\n\\midrule\n{body} \\\\\n\\bottomrule\n"
            f"\\end{{tabular}}\n\\end{{table}}\n")


def tab_zones():
    rows = [[esc(ZONES.get(z["zone"], z["zone"])), sgn(z["mean"]["growth_before_pct"], 2),
             sgn(z["mean"]["growth_after_pct"], 2), sgn(z["mean"]["change_pct_points"], 2),
             pv(z["mean"]["change_p_value"]), sgn(z["baseload"]["change_pct_points"], 2),
             num(z["latest_12m_mean_mw"])] for z in R["zone_trends"]]
    return table("lrrrrrr", r" & \multicolumn{4}{c}{Mean demand} & Baseload & \\ \cmidrule(lr){2-5}\cmidrule(lr){6-6}"
                 "\nZone & 2019--22 & 2023 on & Change & $p$ & Change & Recent MW",
                 rows, "Yearly demand growth by PJM zone, percent, and the change in percentage points. "
                 "Baseload is the monthly 5th-percentile hour. $p$-values use Newey--West standard errors.",
                 "tab:zones", r"\footnotesize")


def tab_scm():
    rows = []
    for z, name in (("AEP", "AEP"), ("DOM", "Dominion")):
        for kind, lab in (("levels", "levels"), ("acceleration", "acceleration")):
            f = SC[z][kind]
            if f:
                lo, hi = min(f["recent_gap_mw_leave_one_out"]), max(f["recent_gap_mw_leave_one_out"])
                rows.append([f"{name}, {lab}", sgn(f["recent_gap_pct"], 1), num(f["recent_gap_mw"]),
                             f"{num(lo)}--{num(hi)}", num(f["rmspe_pre_pct"], 2), num(f["rmspe_ratio"], 1),
                             f["rank"].replace(" of ", "/"), f"{f['placebo_p_value']:.3f}"])
        p = SC[z]["levels"].get("placebo_in_time")
        if p:
            rows.append([f"{name}, placebo start {p['fake_start']}", sgn(p["gap_pct"], 1), "", "", "", "",
                         p["rank"].replace(" of ", "/"), f"{p['p_value']:.3f}"])
    return table("lrrrrrrr", r"Specification & Gap (\%) & MW & Leave-one-out MW & Pre-RMSPE (\%) & Ratio & Rank & $p$",
                 rows, "Synthetic control estimates. The gap is the average over the latest 12 months. "
                 "Ratio is post-2023 over pre-2023 RMSPE; rank and $p$ are from placebo zones. "
                 "The placebo start date uses pre-2023 data only.", "tab:scm", r"\footnotesize")


def tab_weights():
    specs = [("AEP, levels", AEP), ("Dominion, levels", DOM), ("Dominion, acceleration", DOMA)]
    rows = [[name, ", ".join(f"{ZONES.get(z, z).split(' (')[0]} {100 * w:.0f}" + r"\%" for z, w in s["weights"].items())]
            for name, s in specs if s]
    return table(r"lp{0.68\linewidth}", "Specification & Comparison zones and weights", rows,
                 "Composition of each synthetic control.", "tab:weights")


def tab_break():
    rows = []
    for z, name in (("AEP", "AEP"), ("DOM", "Dominion")):
        s, b = R["zone_share"][z], R["zone_share"][z]["break_test"]
        rows.append([name, num(s["first_year_avg_pct"], 2), num(s["latest_12m_avg_pct"], 2), month(b["break_month"]),
                     sgn(b["slope_before_per_year"], 2), sgn(b["slope_after_per_year"], 2), num(b["sup_f"], 1),
                     pv(b["p_value"])])
    return table("lrrlrrrr", r"Zone & Share 2019 & Latest & Break & Slope before & Slope after & Sup-$F$ & $p$", rows,
                 "Structural break tests on each zone's share of PJM demand (percent). Slopes are percentage points "
                 "per year. $p$-values from 999 moving-block bootstrap draws.", "tab:break")


def tab_regions():
    rows = []
    for k in sorted(BAS, key=lambda k: -R["regions"][k]["baseload_trend"]["change_pct_points"]):
        t = R["regions"][k]["baseload_trend"]
        rows.append([esc(R["regions"][k]["label"]), sgn(t["growth_before_pct"], 2),
                     f"[{sgn(t['growth_before_ci'][0], 1)}, {sgn(t['growth_before_ci'][1], 1)}]",
                     sgn(t["growth_after_pct"], 2),
                     f"[{sgn(t['growth_after_ci'][0], 1)}, {sgn(t['growth_after_ci'][1], 1)}]",
                     sgn(t["change_pct_points"], 2), pv(t["change_p_value"])])
    return table("lrrrrrr", r"Region & 2019--22 & 95\% CI & 2023 on & 95\% CI & Change & $p$", rows,
                 "Baseload growth by grid region, percent per year.", "tab:regions", r"\footnotesize")


def tab_mef():
    rows = []
    for k, v in R["emissions"].items():
        c = v["change_test"]
        if not c:
            continue
        full = [y for y in v["by_year"] if not y["partial_year"]]
        rows.append([esc(v["label"]), num(c["before"], 3), num(c["after"], 3),
                     f"[{num(c['after_ci'][0], 3)}, {num(c['after_ci'][1], 3)}]", pv(c["p_value"]),
                     num(full[-1]["average_intensity"], 3) if full else "n/a"])
    return table("lrrrrr", r"Region & Marginal 2019--22 & Marginal 2023 on & 95\% CI & $p$ (change) & Average",
                 rows, "Marginal emission factors, t CO$_2$ per MWh, and average intensity in the latest full year.",
                 "tab:mef", r"\footnotesize")


def tab_emissions():
    rows = []
    for key, name in (("since_2023", "New since 2023 (acceleration)"), ("since_baseline", "All divergence (levels)")):
        t = H[key]
        rows.append([name, num(t["by_zone_mw"]["AEP"]), num(t["by_zone_mw"]["DOM"]), num(t["extra_load_mw"]),
                     num(t["extra_twh_per_year"], 1), num(t["mt_co2_per_year"], 1),
                     f"{num(t['mt_co2_range'][0], 1)}--{num(t['mt_co2_range'][1], 1)}",
                     num(t["mt_co2_if_average_factor"], 1)])
    return table("lrrrrrrr", r"Reading & AEP MW & Dominion MW & Total MW & TWh/yr & Mt CO$_2$/yr & Range & At average",
                 rows, "Emissions implied by the additional load, at PJM's marginal emission factor.",
                 "tab:emissions", r"\footnotesize")


# ----------------------------------------------------------------------------- text
def build_tex() -> str:
    n_zones, n_reg = len(R["zone_trends"]), len(BAS)
    n_sig = sum(1 for k in BAS if R["regions"][k]["baseload_trend"]["change_p_value"] < 0.05
                and R["regions"][k]["baseload_trend"]["change_pct_points"] > 0)
    rest_max = max(z["mean"]["change_pct_points"] for z in R["zone_trends"] if not z["hot"])
    nd = AEP["n_donors"]
    ef = R["meta"]["emission_factors_t_per_mwh"]
    mix = PJM["marginal_mix_after"]
    ct = PJM["change_test"]
    a, d, da = AEP, DOM, DOMA
    v = {
        "RECORDS": num(R["meta"]["records_analyzed"] / 1e6, 1), "NZ": str(n_zones), "NR": str(n_reg), "NSIG": str(n_sig),
        "START": R["meta"]["data_start"], "END": R["meta"]["data_end"][:10], "RUN": R["meta"]["generated_utc"][:10],
        "ND": str(nd), "MINP": f"{1 / (nd + 1):.3f}", "RESTMAX": sgn(rest_max, 1),
        "AEP_B": sgn(ZT["AEP"]["mean"]["growth_before_pct"], 1), "AEP_A": sgn(ZT["AEP"]["mean"]["growth_after_pct"], 1),
        "AEP_C": sgn(ZT["AEP"]["mean"]["change_pct_points"], 1),
        "DOM_B": sgn(ZT["DOM"]["mean"]["growth_before_pct"], 1), "DOM_A": sgn(ZT["DOM"]["mean"]["growth_after_pct"], 1),
        "DOM_C": sgn(ZT["DOM"]["mean"]["change_pct_points"], 1),
        "A_RMSPE": num(a["rmspe_pre_pct"], 2), "A_GAP": num(a["recent_gap_pct"], 1), "A_MW": num(a["recent_gap_mw"]),
        "A_LO": num(min(a["recent_gap_mw_leave_one_out"])), "A_HI": num(max(a["recent_gap_mw_leave_one_out"])),
        "A_RANK": a["rank"], "A_P": f"{a['placebo_p_value']:.3f}", "A_PIT": sgn(a["placebo_in_time"]["gap_pct"], 1),
        "D_GAP": num(d["recent_gap_pct"], 1), "D_MW": num(d["recent_gap_mw"]), "D_RMSPE": num(d["rmspe_pre_pct"], 1),
        "D_PIT": sgn(d["placebo_in_time"]["gap_pct"], 1),
        "DA_GAP": num(da["recent_gap_pct"], 1), "DA_MW": num(da["recent_gap_mw"]), "DA_RANK": da["rank"],
        "DA_P": f"{da['placebo_p_value']:.3f}", "DA_RMSPE": num(da["rmspe_pre_pct"], 2),
        "W0": month(a["recent_window"][0]), "W1": month(a["recent_window"][1]),
        "SH_D0": num(R["zone_share"]["DOM"]["first_year_avg_pct"], 1),
        "SH_D1": num(R["zone_share"]["DOM"]["latest_12m_avg_pct"], 1),
        "SH_A0": num(R["zone_share"]["AEP"]["first_year_avg_pct"], 1),
        "SH_A1": num(R["zone_share"]["AEP"]["latest_12m_avg_pct"], 1),
        "BR_A": month(R["zone_share"]["AEP"]["break_test"]["break_month"]),
        "BR_D": month(R["zone_share"]["DOM"]["break_test"]["break_month"]),
        "BR_AP": ptext(R["zone_share"]["AEP"]["break_test"]["p_value"]),
        "BR_DP": ptext(R["zone_share"]["DOM"]["break_test"]["p_value"]),
        "MEF": num(H["pjm_marginal_factor"], 3), "MEF_LO": num(ct["after_ci"][0], 3), "MEF_HI": num(ct["after_ci"][1], 3),
        "MEF_PRE": num(ct["before"], 3), "MEF_P": ptext(ct["p_value"]), "AEF": num(H["pjm_average_factor"], 3),
        "MVA": num(H["marginal_vs_average_pct"], 0),
        "MX_GAS": num(100 * mix["gas"], 0), "MX_COAL": num(100 * mix["coal"], 0), "MX_HYD": num(100 * mix["hydro"], 0),
        "MX_IMP": num(100 * mix["imports"], 0),
        "EF_COAL": f"{ef['coal']:.3f}", "EF_GAS": f"{ef['gas']:.3f}", "EF_OIL": f"{ef['oil']:.3f}",
        "N_MW": num(H["since_2023"]["extra_load_mw"]), "N_GW": num(H["since_2023"]["extra_load_mw"] / 1000, 1),
        "N_TWH": num(H["since_2023"]["extra_twh_per_year"], 1), "N_MT": num(H["since_2023"]["mt_co2_per_year"], 1),
        "N_MT_LO": num(H["since_2023"]["mt_co2_range"][0], 1), "N_MT_HI": num(H["since_2023"]["mt_co2_range"][1], 1),
        "N_MT_AVG": num(H["since_2023"]["mt_co2_if_average_factor"], 1),
        "B_MW": num(H["since_baseline"]["extra_load_mw"]), "B_MT": num(H["since_baseline"]["mt_co2_per_year"], 1),
        "TAB_ZONES": tab_zones(), "TAB_SCM": tab_scm(), "TAB_WEIGHTS": tab_weights(), "TAB_BREAK": tab_break(),
        "TAB_REGIONS": tab_regions(), "TAB_MEF": tab_mef(), "TAB_EMISSIONS": tab_emissions(),
    }
    tex = (OUT / "report_template.tex").read_text()
    for k, val in v.items():
        tex = tex.replace(f"<<{k}>>", val)
    if "<<" in tex:
        left = sorted({tex[i:tex.index(">>", i) + 2] for i in range(len(tex)) if tex.startswith("<<", i)})
        raise RuntimeError(f"Unfilled placeholders in the report template: {left}")
    return tex


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (fig_zones, fig_aep, fig_dom, fig_share, fig_regions, fig_mef):
        f()
    (OUT / "report.tex").write_text(build_tex())
    if shutil.which("pdflatex") is None:
        print("pdflatex not found: wrote report/report.tex and figures, skipped the PDF.")
        return 0
    for _ in range(2):
        run = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "report.tex"],
                             cwd=OUT, capture_output=True, text=True)
        if run.returncode != 0:
            print(run.stdout[-3000:])
            return 1
    shutil.copy(OUT / "report.pdf", ROOT / "docs" / "report.pdf")
    for ext in ("aux", "log", "out", "pdf"):
        (OUT / f"report.{ext}").unlink(missing_ok=True)
    print("Wrote docs/report.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
