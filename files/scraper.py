"""
scraper.py
----------
Downloads the latest H-1B LCA disclosure Excel files from the US DOL
performance data page, converts them to cleaned CSV, and writes to
  data/lca_cleaned.csv

Run:
    python scraper.py               # auto-detect latest available quarters
    python scraper.py --quarters 2  # fetch last N quarters
    python scraper.py --force       # re-download even if file is fresh

Requires:  requests, beautifulsoup4, openpyxl, pandas
Install:   pip install requests beautifulsoup4 openpyxl pandas
"""

import argparse
import io
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# We import the transform logic from the sibling file
sys.path.insert(0, str(Path(__file__).parent))
from transform_lca import transform_dataframe

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DOL_PERF_PAGE   = "https://www.dol.gov/agencies/eta/foreign-labor/performance"
DATA_DIR        = Path(__file__).parent / "data"
OUTPUT_CSV      = DATA_DIR / "lca_cleaned.csv"
CACHE_DIR       = DATA_DIR / "raw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
}

# Fallback URL patterns to try if page scraping fails.
# DOL naming conventions across recent fiscal years:
_CURRENT_YEAR = datetime.now().year
_FISCAL_YEARS  = [_CURRENT_YEAR + 1, _CURRENT_YEAR, _CURRENT_YEAR - 1]

FALLBACK_URL_TEMPLATES = [
    # FY2026+ naming
    "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY{fy}_Q{q}.xlsx",
    # Older naming (FY2025 and earlier sometimes used H-1B_ prefix)
    "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/H-1B_Disclosure_Data_FY{fy}_Q{q}.xlsx",
    # Some quarters have been published as _Q{q}v1 or with a different prefix
    "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY{fy}Q{q}.xlsx",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def discover_links(session: requests.Session) -> list[dict]:
    """
    Scrape the DOL performance page and return a list of
    {"url": ..., "fy": ..., "quarter": ...} dicts for LCA Excel files.
    Falls back to URL template probing if scraping is blocked.
    """
    print(f"Fetching DOL performance page: {DOL_PERF_PAGE}")
    try:
        r = session.get(DOL_PERF_PAGE, timeout=30)
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"  Page returned {e.response.status_code}; falling back to URL probing.")
        return _probe_fallback_urls(session)

    soup = BeautifulSoup(r.text, "html.parser")
    candidates = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)
        # Match LCA disclosure xlsx links
        if not re.search(r"\.xlsx", href, re.I):
            continue
        if not re.search(r"LCA|H.?1B|Labor.Condition", href + text, re.I):
            continue

        # Extract FY and Q from URL
        fy_match = re.search(r"FY(\d{4})", href, re.I)
        q_match  = re.search(r"Q(\d)", href, re.I)
        fy = int(fy_match.group(1)) if fy_match else None
        q  = int(q_match.group(1))  if q_match  else None

        full_url = href if href.startswith("http") else "https://www.dol.gov" + href
        candidates.append({"url": full_url, "fy": fy, "quarter": q, "text": text})
        print(f"  Found: FY{fy} Q{q} — {full_url[-70:]}")

    if candidates:
        return candidates

    print("  No links found via page scrape; probing known URL patterns…")
    return _probe_fallback_urls(session)


def _probe_fallback_urls(session: requests.Session) -> list[dict]:
    """Probe known DOL URL patterns and return accessible ones."""
    found = []
    for fy in _FISCAL_YEARS:
        for q in [4, 3, 2, 1]:
            for tpl in FALLBACK_URL_TEMPLATES:
                url = tpl.format(fy=fy, q=q)
                try:
                    resp = session.head(url, timeout=10, allow_redirects=True)
                    if resp.status_code == 200:
                        ct = resp.headers.get("content-type", "")
                        cl = int(resp.headers.get("content-length", 0))
                        if "spreadsheet" in ct or cl > 100_000:
                            print(f"  Probed OK: FY{fy} Q{q} — {url[-70:]}")
                            found.append({"url": url, "fy": fy, "quarter": q, "text": ""})
                            break   # found a valid template for this fy+q, stop trying others
                except requests.RequestException:
                    pass
            if found and found[-1]["fy"] == fy and found[-1]["quarter"] == q:
                pass  # continue to next quarter
    return found


def download_xlsx(session: requests.Session, url: str, dest: Path) -> Path:
    """Download an xlsx to dest (with resume/cache support)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading → {dest.name} …", end="", flush=True)
    r = session.get(url, timeout=120, stream=True)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):  # 1 MB chunks
            f.write(chunk)
            downloaded += len(chunk)
    size_mb = downloaded / 1e6
    print(f" {size_mb:.1f} MB ✓")
    return dest


def xlsx_to_dataframe(path: Path):
    """Read a DOL LCA file (.xlsx or .csv) into a pandas DataFrame."""
    import pandas as pd
    print(f"  Reading {path.name} …", end="", flush=True)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path, engine="openpyxl")
    elif suffix == ".csv":
        df = pd.read_csv(path, encoding="latin1", low_memory=False)
    else:
        # Try Excel first, fall back to CSV
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception:
            df = pd.read_csv(path, encoding="latin1", low_memory=False)
    print(f" {len(df):,} rows")
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape & clean DOL LCA data.",
        epilog=(
            "Examples:\n"
            "  python scraper.py                          # auto-download latest quarter\n"
            "  python scraper.py --local data/raw/LCA_Disclosure_Data_FY2026_Q1.xlsx\n"
            "  python scraper.py --local file1.xlsx file2.xlsx  # merge multiple files\n"
            "  python scraper.py --quarters 2 --force    # re-download last 2 quarters\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--local", nargs="+", metavar="FILE",
        help="Skip download; use one or more local .xlsx files directly",
    )
    parser.add_argument("--quarters", type=int, default=1,
                        help="How many recent quarters to fetch (default: 1)")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if cached file exists")
    parser.add_argument("--out", default=str(OUTPUT_CSV),
                        help=f"Output CSV path (default: {OUTPUT_CSV})")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    import pandas as pd
    frames = []

    # ----------------------------------------------------------------
    # MODE A: local files supplied via --local (or auto-detected)
    # ----------------------------------------------------------------
    local_paths: list[Path] = []

    if args.local:
        # Explicit --local paths
        for p in args.local:
            local_paths.append(Path(p))
    else:
        # Auto-detect: if data/raw/ already has xlsx files and DOL is unreachable,
        # we'll fall through to MODE B first; but if MODE B finds nothing we'll
        # pick up whatever is already in data/raw/.
        pass

    if local_paths:
        for p in local_paths:
            if not p.exists():
                print(f"[ERROR] File not found: {p}")
                sys.exit(1)
            print(f"Reading local file: {p}")
            frames.append(xlsx_to_dataframe(p))
    else:
        # ----------------------------------------------------------------
        # MODE B: discover + download from DOL
        # ----------------------------------------------------------------
        session = get_session()
        links = discover_links(session)

        # If download discovery failed, fall back to any xlsx already in data/raw/
        if not links:
            existing = sorted(CACHE_DIR.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
            if existing:
                print(f"\n[INFO] Could not reach DOL; found {len(existing)} cached file(s) in {CACHE_DIR}:")
                for f in existing:
                    print(f"  {f.name}")
                for f in existing[: args.quarters]:
                    frames.append(xlsx_to_dataframe(f))
            else:
                print("\n[ERROR] Could not find any LCA disclosure files.")
                print("  Download the xlsx manually from:")
                print("  https://www.dol.gov/agencies/eta/foreign-labor/performance")
                print("  then run:  python scraper.py --local data/raw/<filename>.xlsx")
                sys.exit(1)
        else:
            # Sort by FY desc, quarter desc → most recent first
            links.sort(key=lambda x: (x["fy"] or 0, x["quarter"] or 0), reverse=True)
            links = links[: args.quarters]

            for link in links:
                fname = Path(link["url"]).name
                cached = CACHE_DIR / fname
                if cached.exists() and not args.force:
                    age_hours = (time.time() - cached.stat().st_mtime) / 3600
                    print(f"  Using cached {fname} (age {age_hours:.0f}h).")
                else:
                    print(f"\nFY{link['fy']} Q{link['quarter']}:")
                    download_xlsx(session, link["url"], cached)
                frames.append(xlsx_to_dataframe(cached))

    if not frames:
        print("[ERROR] No data frames loaded.")
        sys.exit(1)

    combined_raw = pd.concat(frames, ignore_index=True)
    print(f"\nCombined raw rows: {len(combined_raw):,}")

    # 3. Transform
    print("Transforming…")
    cleaned = transform_dataframe(combined_raw)
    print(f"Cleaned rows: {len(cleaned):,}")

    # 4. Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(out_path, index=False)
    print(f"\n✓ Saved to {out_path}")
    print(cleaned[["employer_clean", "job_category", "seniority", "wage_annual"]].head(5).to_string())


if __name__ == "__main__":
    main()