"""Feasibility probe: which PJM load forecast files can be downloaded, and what is in them."""
import io, json, re, sys
from pathlib import Path
import requests

OUT = Path(__file__).resolve().parent
RAW, EXT = OUT / "raw", OUT / "extract"
RAW.mkdir(exist_ok=True); EXT.mkdir(exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
     "Accept": "*/*"}
B = "https://www.pjm.com/-/media/"
cands = {}
for y in range(2019, 2027):
    cands[f"{y}-load-report.pdf"] = [B + f"DotCom/library/reports-notices/load-forecast/{y}-load-report.pdf",
                                     B + f"library/reports-notices/load-forecast/{y}-load-report.ashx"]
for y in (2024, 2025, 2026):
    cands[f"{y}-load-report-tables.xlsx"] = [B + f"DotCom/planning/res-adeq/load-forecast/{y}-load-report-tables.xlsx",
                                             B + f"DotCom/library/reports-notices/load-forecast/{y}-load-report-tables.xlsx"]
cands["2026-load-forecast-accuracy-report.pdf"] = [B + "DotCom/planning/res-adeq/load-forecast/2026-load-forecast-accuracy-report.pdf"]
cands["2026-load-forecast-accuracy-data.xlsx"] = [B + "DotCom/planning/res-adeq/load-forecast/2026-load-forecast-accuracy-report-data.xlsx",
                                                  B + "DotCom/planning/res-adeq/load-forecast/2026-load-forecast-accuracy-data.xlsx"]
log = {}
for name, urls in cands.items():
    log[name] = {"ok": False, "tries": []}
    for u in urls:
        try:
            r = requests.get(u, headers=H, timeout=90)
            head = r.content[:5]
            good = r.status_code == 200 and (head.startswith(b"%PDF") or head.startswith(b"PK"))
            log[name]["tries"].append([u, r.status_code, len(r.content), head.decode("latin1")])
            if good:
                (RAW / name).write_bytes(r.content); log[name].update(ok=True, url=u, bytes=len(r.content)); break
        except Exception as e:  # noqa: BLE001
            log[name]["tries"].append([u, "ERR", str(e)[:120]])
# what is inside
import openpyxl, pdfplumber
for f in sorted(RAW.glob("*.xlsx")):
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    info = {}
    for ws in wb.worksheets:
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 9: break
            rows.append([str(c)[:14] for c in row[:16] if c is not None])
        info[ws.title] = {"dims": ws.calculate_dimension() if not ws.max_row else f"{ws.max_row}x{ws.max_column}", "head": rows}
    log[f.name]["sheets"] = info
for f in sorted(RAW.glob("*.pdf")):
    try:
        with pdfplumber.open(f) as pdf:
            hits = {}
            for n, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                m = re.search(r"Table ([A-F]-\d+[ab]?)", t)
                if m and m.group(1) in ("B-1", "E-1", "B-9") and m.group(1) not in hits:
                    hits[m.group(1)] = n
                    (EXT / f"{f.stem}_{m.group(1)}.txt").write_text(t)
            log[f.name]["pages"] = len(pdf.pages); log[f.name]["tables_found"] = hits
    except Exception as e:  # noqa: BLE001
        log[f.name]["pdf_error"] = str(e)[:200]
(OUT / "probe_log.json").write_text(json.dumps(log, indent=1))
print(json.dumps({k: (v["ok"], v.get("bytes")) for k, v in log.items()}, indent=1))
