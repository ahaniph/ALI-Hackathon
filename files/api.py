"""
api.py
------
FastAPI backend for SponsorScope.
Reads data/lca_cleaned.csv and serves three endpoints:

  GET /meta          → categories, states, total_rows
  GET /search        → ranked employer list with filters
  GET /company/{name} → individual company detail + recent filings

Run:
    uvicorn api:app --reload --port 8000

Install:
    pip install fastapi uvicorn pandas
"""

import math
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="SponsorScope API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_PATH = Path(__file__).parent / "data" / "lca_cleaned.csv"

# ---------------------------------------------------------------------------
# In-memory data store
# Loaded once at startup; call /reload to refresh after running scraper.py
# ---------------------------------------------------------------------------
_df: pd.DataFrame = pd.DataFrame()


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Data file not found: {DATA_PATH}\n"
            "Run `python scraper.py` first to download and clean the DOL data."
        )
    df = pd.read_csv(DATA_PATH, low_memory=False, parse_dates=["start_date"])
    # Normalise columns
    df["wage_annual"]            = pd.to_numeric(df["wage_annual"], errors="coerce")
    df["prevailing_wage_annual"] = pd.to_numeric(df["prevailing_wage_annual"], errors="coerce")
    df["is_new_hire"]            = df["is_new_hire"].astype(bool)
    df["total_workers"]          = pd.to_numeric(df["total_workers"], errors="coerce").fillna(1).astype(int)
    df["worksite_state"]         = df["worksite_state"].fillna("").str.upper()
    df["worksite_city"]          = df["worksite_city"].fillna("").str.strip()
    df["job_category"]           = df["job_category"].fillna("Other")
    df["seniority"]              = df["seniority"].fillna("Mid")
    df["employer_clean"]         = df["employer_clean"].fillna("Unknown")
    # Months ago helper (relative to today)
    today = pd.Timestamp.today()
    df["months_ago"] = ((today - df["start_date"]).dt.days // 30).clip(lower=0)
    return df


@app.on_event("startup")
def startup_event():
    global _df
    try:
        _df = load_data()
        print(f"[API] Loaded {len(_df):,} rows from {DATA_PATH}")
    except FileNotFoundError as e:
        print(f"[API] WARNING: {e}")
        print("[API]  Starting in empty-data mode. Run scraper.py then hit /reload.")


@app.get("/reload")
def reload_data():
    """Hot-reload the CSV without restarting the server."""
    global _df
    try:
        _df = load_data()
        return {"status": "ok", "rows": len(_df)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# Filtering helper
# ---------------------------------------------------------------------------

def apply_filters(
    df: pd.DataFrame,
    category: Optional[str],
    state: Optional[str],
    seniority: Optional[str] = None,
) -> pd.DataFrame:
    if category and category.lower() != "all":
        df = df[df["job_category"] == category]
    if state and state.upper() != "ALL":
        df = df[df["worksite_state"] == state.upper()]
    if seniority and seniority.lower() != "all":
        df = df[df["seniority"] == seniority]
    return df


# ---------------------------------------------------------------------------
# /meta
# ---------------------------------------------------------------------------

@app.get("/meta")
def get_meta():
    """Return filter options and dataset size."""
    if _df.empty:
        raise HTTPException(status_code=503, detail="Data not loaded. Run scraper.py first.")

    categories = ["All"] + sorted(_df["job_category"].dropna().unique().tolist())
    states     = ["All"] + sorted(_df["worksite_state"][_df["worksite_state"] != ""].unique().tolist())
    seniorities = ["All"] + ["Mid", "Senior", "Staff/Lead", "Manager+"]

    return {
        "categories": categories,
        "states":     states,
        "seniorities": seniorities,
        "total_rows": len(_df),
        "last_updated": datetime.fromtimestamp(
            DATA_PATH.stat().st_mtime
        ).strftime("%Y-%m-%d %H:%M") if DATA_PATH.exists() else None,
    }


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------

@app.get("/search")
def search(
    category: str = Query("All"),
    state:    str = Query("All"),
    seniority: str = Query("All"),
    sort_by:  str = Query("count", pattern="^(count|salary|recent)$"),
    limit:    int = Query(50, ge=1, le=200),
):
    """
    Return a ranked list of employer aggregates matching the filters.
    Response shape:
      {
        results: [ {employer, count, median, min, max,
                    recent_date, months_ago, city_list, city_count} ],
        total: int,
        stats: { total_companies, total_filings, median_salary, new_hire_pct }
      }
    """
    if _df.empty:
        raise HTTPException(status_code=503, detail="Data not loaded. Run scraper.py first.")

    sub = apply_filters(_df, category, state, seniority)

    if sub.empty:
        return {
            "results": [],
            "total": 0,
            "stats": {"total_companies": 0, "total_filings": 0,
                      "median_salary": 0, "new_hire_pct": 0},
        }

    # Aggregate per employer
    grp = (
        sub.groupby("employer_clean", sort=False)
        .agg(
            count            = ("employer_clean", "size"),
            median           = ("wage_annual",    "median"),
            min_wage         = ("wage_annual",    "min"),
            max_wage         = ("wage_annual",    "max"),
            recent_date      = ("start_date",     "max"),
            months_ago       = ("months_ago",     "min"),
            new_hires        = ("is_new_hire",    "sum"),
        )
        .reset_index()
    )

    # City lists per employer (up to 6 most common)
    city_agg = (
        sub.groupby("employer_clean")["worksite_city"]
        .apply(lambda s: s.value_counts().head(6).index.tolist())
        .reset_index()
        .rename(columns={"worksite_city": "city_list"})
    )
    city_agg["city_count"] = city_agg["city_list"].apply(len)

    grp = grp.merge(city_agg, on="employer_clean", how="left")
    grp["city_list"]  = grp["city_list"].apply(lambda x: x if isinstance(x, list) else [])
    grp["city_count"] = grp["city_count"].fillna(0).astype(int)

    # Sort
    if sort_by == "salary":
        grp = grp.sort_values("median", ascending=False)
    elif sort_by == "recent":
        grp = grp.sort_values("recent_date", ascending=False, na_position="last")
    else:  # count
        grp = grp.sort_values("count", ascending=False)

    # Dataset-wide stats (for the current filter)
    total_filings  = int(sub["total_workers"].sum())
    median_salary  = int(sub["wage_annual"].median()) if not sub["wage_annual"].isna().all() else 0
    new_hire_pct   = int(round(100 * sub["is_new_hire"].mean())) if len(sub) else 0

    total_count = len(grp)
    grp = grp.head(limit)

    def _safe_date(v):
        if pd.isna(v):
            return None
        if isinstance(v, (pd.Timestamp, datetime, date)):
            return str(v)[:10]
        return str(v)[:10]

    results = [
        {
            "employer":     row["employer_clean"],
            "count":        int(row["count"]),
            "median":       round(float(row["median"]), 2) if not math.isnan(row["median"]) else 0,
            "min":          round(float(row["min_wage"]), 2) if not math.isnan(row["min_wage"]) else 0,
            "max":          round(float(row["max_wage"]), 2) if not math.isnan(row["max_wage"]) else 0,
            "recent_date":  _safe_date(row["recent_date"]),
            "months_ago":   int(row["months_ago"]) if not math.isnan(row["months_ago"]) else 0,
            "city_list":    row["city_list"],
            "city_count":   int(row["city_count"]),
        }
        for _, row in grp.iterrows()
    ]

    return {
        "results": results,
        "total":   total_count,
        "stats": {
            "total_companies": total_count,
            "total_filings":   total_filings,
            "median_salary":   median_salary,
            "new_hire_pct":    new_hire_pct,
        },
    }


# ---------------------------------------------------------------------------
# /company/{employer}
# ---------------------------------------------------------------------------

@app.get("/company/{employer}")
def company_detail(
    employer:  str,
    category:  str = Query("All"),
    state:     str = Query("All"),
    seniority: str = Query("All"),
    max_filings: int = Query(30, ge=1, le=200),
):
    """
    Return aggregate + recent individual filings for one employer.
    Response shape:
      {
        employer, count, median, min, max, city_list,
        filings: [ {id, title, city, state, salary, date, seniority,
                    soc_code, is_new_hire, case_status} ]
      }
    """
    if _df.empty:
        raise HTTPException(status_code=503, detail="Data not loaded. Run scraper.py first.")

    # Match employer (case-insensitive)
    mask = _df["employer_clean"].str.lower() == employer.lower()
    emp_df = _df[mask].copy()

    if emp_df.empty:
        raise HTTPException(status_code=404, detail=f"Employer '{employer}' not found.")

    sub = apply_filters(emp_df, category, state, seniority)
    if sub.empty:
        # Graceful degradation: return aggregate from unfiltered data
        sub = emp_df

    wages = sub["wage_annual"].dropna()
    median_w = float(wages.median()) if len(wages) else 0
    min_w    = float(wages.min())    if len(wages) else 0
    max_w    = float(wages.max())    if len(wages) else 0

    cities = sub["worksite_city"].value_counts().head(8).index.tolist()

    # Most recent filings
    filings_df = (
        sub.sort_values("start_date", ascending=False, na_position="last")
        .head(max_filings)
    )
    filings = [
        {
            "id":          int(idx),
            "title":       str(row["job_title"]) if pd.notna(row["job_title"]) else "—",
            "city":        str(row["worksite_city"]),
            "state":       str(row["worksite_state"]),
            "salary":      round(float(row["wage_annual"]), 2) if pd.notna(row["wage_annual"]) else None,
            "date":        str(row["start_date"])[:10] if pd.notna(row["start_date"]) else None,
            "seniority":   str(row["seniority"]),
            "soc_code":    str(row["soc_code"]) if pd.notna(row["soc_code"]) else None,
            "is_new_hire": bool(row["is_new_hire"]),
            "case_status": str(row["case_status"]) if pd.notna(row["case_status"]) else None,
        }
        for idx, row in filings_df.iterrows()
    ]

    return {
        "employer":  employer,
        "count":     len(sub),
        "median":    round(median_w, 2),
        "min":       round(min_w, 2),
        "max":       round(max_w, 2),
        "city_list": cities,
        "filings":   filings,
    }


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status":    "ok",
        "rows":      len(_df),
        "data_path": str(DATA_PATH),
        "loaded":    not _df.empty,
    }
