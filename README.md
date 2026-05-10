# SponsorScope — Setup & Usage

Find every company that's actually sponsored H-1B visas, with real salary ranges and locations — built straight from DOL public disclosure data.

---

## Project layout

```
sponsorscope/
├── scraper.py          ← downloads + cleans DOL LCA data
├── transform_lca.py    ← cleaning / classification logic
├── api.py              ← FastAPI backend (serves the React frontend)
├── requirements.txt
├── data/
│   ├── raw/            ← cached raw .xlsx files (auto-created)
│   └── lca_cleaned.csv ← cleaned output (auto-created by scraper)
└── frontend/
    └── SponsorScope.jsx ← React component (drop into your Vite/CRA app)
```

---

## Quick start (5 minutes)

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Download & clean the latest DOL data

```bash
python scraper.py
```

This will:
- Fetch the DOL performance data page to discover the latest LCA Excel file(s)
- Download them to `data/raw/` (cached — won't re-download unless `--force`)
- Run the full cleaning pipeline and write `data/lca_cleaned.csv`

Options:
```
--quarters 2    # fetch the last 2 quarters instead of just 1
--force         # re-download even if a cached file exists
--out PATH      # write cleaned CSV to a custom path
```

### 3. Start the API server

```bash
uvicorn api:app --reload --port 8000
```

The API will be live at `http://localhost:8000`.
Check `http://localhost:8000/health` to confirm.

### 4. Run the React frontend

Drop `SponsorScope.jsx` into your existing React project (Vite, CRA, Next.js, etc.):

```bash
# New Vite project from scratch:
npm create vite@latest sponsorscope-ui -- --template react
cd sponsorscope-ui
npm install lucide-react
# copy SponsorScope.jsx into src/
# import and render <SponsorScope /> in App.jsx
npm run dev
```

Open `http://localhost:5173` — the app talks to your API at port 8000.

---

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /meta` | Available filter options (categories, states) and total row count |
| `GET /search?category=&state=&sort_by=&limit=` | Ranked employer list with salary aggregates |
| `GET /company/{name}?category=&state=` | Individual company detail + recent filings |
| `GET /reload` | Hot-reload `lca_cleaned.csv` without restarting the server |
| `GET /health` | Liveness check |

### Search parameters

| Param | Values | Default |
|---|---|---|
| `category` | Any job category or `All` | `All` |
| `state` | Two-letter state code or `All` | `All` |
| `seniority` | `Mid`, `Senior`, `Staff/Lead`, `Manager+`, `All` | `All` |
| `sort_by` | `count`, `salary`, `recent` | `count` |
| `limit` | 1–200 | 50 |

---

## Updating the data

The DOL publishes new quarterly files roughly in January, April, July, and October.

```bash
# Pull the latest quarter (skips if already cached)
python scraper.py

# Force a fresh download of the last 2 quarters
python scraper.py --quarters 2 --force

# Then hot-reload the running API without restarting:
curl http://localhost:8000/reload
```

---

## Troubleshooting

**`scraper.py` fails to access dol.gov**

The DOL occasionally rate-limits or blocks automated downloads. If that happens:
1. Manually download the latest `.xlsx` from:  
   https://www.dol.gov/agencies/eta/foreign-labor/performance
2. Place it in `data/raw/`
3. Run the transformer directly:
   ```bash
   python transform_lca.py --lca data/raw/LCA_Disclosure_Data_FY2026_Q1.xlsx --out data/lca_cleaned.csv
   ```
   *(Note: `transform_lca.py` also accepts `.xlsx` via pandas — just pass the path.)*

**API returns `503 Data not loaded`**

Run `python scraper.py` first to generate `data/lca_cleaned.csv`.

**Frontend shows "Demo mode (API offline)"**

The React app fell back to mock data because it couldn't reach `http://localhost:8000`.  
Make sure `uvicorn api:app --port 8000` is running.

---

## Data source

All data comes from the [US DOL OFLC Performance Data](https://www.dol.gov/agencies/eta/foreign-labor/performance) — public disclosure under the Immigration and Nationality Act. Not affiliated with USCIS or DOL.
