"""
transform_lca.py
----------------
Transforms the US DOL FY26 Q1 Labor Condition Application (LCA) data
into the cleaned format used in cleaned_test.csv.

Usage:
    python transform_lca.py \
        --lca   REAL_LCA_Data.csv \
        --pw    REAL_Prevailing_Wage_data.csv \
        --out   output_cleaned.csv

The Prevailing Wage file is read but not merged here because the LCA
already carries a PREVAILING_WAGE column populated by DOL.  The PW file
is included for reference / future enrichment.
"""

import argparse
import re
import pandas as pd


# ---------------------------------------------------------------------------
# 1.  EMPLOYER CANONICALISATION
#     Map messy EMPLOYER_NAME strings → a clean short label.
# ---------------------------------------------------------------------------

EMPLOYER_MAP = {
    # Big Tech
    r"meta platforms|facebook": "Meta",
    r"\bgoogle\b|youtube": "Google",
    r"\bmicrosoft\b|linkedin": "Microsoft",
    r"\bamazon\b|aws\b|amazon web services": "Amazon",
    r"\bapple\b": "Apple",
    r"\bnvidia\b": "NVIDIA",
    r"\bintel\b": "Intel",
    r"\bibm\b": "IBM",
    r"\boracle\b": "Oracle",
    r"\bsalesforce\b": "Salesforce",
    r"\badobe\b": "Adobe",
    r"\bqualcomm\b": "Qualcomm",
    r"\bbroadcom\b": "Broadcom",
    r"\bnetflix\b": "Netflix",
    r"\bspotify\b": "Spotify",
    r"\btwitter\b|\bx corp\b": "X (Twitter)",
    r"\blunar\b|\btiktok\b|\bbytedance\b": "TikTok / ByteDance",
    r"\bsnap\b|\bsnapchat\b": "Snap",
    r"\buber\b": "Uber",
    r"\blyft\b": "Lyft",
    r"\bairbnb\b": "Airbnb",
    r"\bdoordash\b": "DoorDash",
    r"\bpaypal\b": "PayPal",
    r"\bblock\b|\bsquare\b": "Block (Square)",
    r"\bstripe\b": "Stripe",
    r"\bcoinbase\b": "Coinbase",
    r"\brobinhood\b": "Robinhood",
    # AI / ML
    r"\bopenai\b": "OpenAI",
    r"\banthropicpbc\b|\banthropic\b": "Anthropic",
    r"\bdatabricks\b": "Databricks",
    r"\bhugging face\b|\bhuggingface\b": "Hugging Face",
    r"\bscale ai\b": "Scale AI",
    r"\bcohere\b": "Cohere",
    r"\bstability ai\b": "Stability AI",
    r"\bmistral\b": "Mistral",
    r"\bperplexity\b": "Perplexity",
    # Cloud / SaaS
    r"\bpalantir\b": "Palantir",
    r"\bsnowflake\b": "Snowflake",
    r"\bdatadog\b": "Datadog",
    r"\bhashicorp\b": "HashiCorp",
    r"\btwilio\b": "Twilio",
    r"\bzendesk\b": "Zendesk",
    r"\bworkday\b": "Workday",
    r"\bservicenow\b": "ServiceNow",
    r"\bautodesk\b": "Autodesk",
    r"\bsap america\b|\bsap labs\b|\bsap se\b|\b\bsap\b": "SAP",
    r"\bsplunk\b": "Splunk",
    r"\bnuance\b": "Nuance",
    r"\bpalo alto networks\b": "Palo Alto Networks",
    r"\bcrowdstrike\b": "CrowdStrike",
    r"\bfortinet\b": "Fortinet",
    r"\bzscaler\b": "Zscaler",
    r"\bokta\b": "Okta",
    r"\btwilio\b": "Twilio",
    r"\bcloudflare\b": "Cloudflare",
    r"\bvercel\b": "Vercel",
    r"\bgitlab\b": "GitLab",
    r"\bgithub\b": "GitHub",
    r"\batlassian\b": "Atlassian",
    r"\bconfluent\b": "Confluent",
    r"\belastic\b": "Elastic",
    r"\bmongodbinc\b|\bmongodb\b": "MongoDB",
    r"\bredis\b": "Redis",
    r"\bcockroach labs\b": "CockroachDB",
    r"\bplanet labs\b|\bplanetlabs\b": "Planet Labs",
    # Finance
    r"\bjpmorgan\b|\bjp morgan\b|\bchase\b": "JPMorgan Chase",
    r"\bgoldman sachs\b": "Goldman Sachs",
    r"\bmorgan stanley\b": "Morgan Stanley",
    r"\bciti(corp|group|bank)\b|\bcitigroup\b|\bciti \b": "Citi",
    r"\bbank of america\b": "Bank of America",
    r"\bwells fargo\b": "Wells Fargo",
    r"\bblackrock\b": "BlackRock",
    r"\bvanguard\b": "Vanguard",
    r"\bfidelity\b": "Fidelity",
    r"\bbloomberg\b": "Bloomberg",
    r"\bvisa\b": "Visa",
    r"\bmastercard\b": "Mastercard",
    r"\bamerican express\b": "American Express",
    # Consulting / Outsourcing
    r"\btata consultancy\b|\btcs\b": "TCS",
    r"\binfosys\b": "Infosys",
    r"\bwipro\b": "Wipro",
    r"\bhcl\b": "HCL",
    r"\btech mahindra\b": "Tech Mahindra",
    r"\bcognizant\b": "Cognizant",
    r"\baccenture\b": "Accenture",
    r"\bdeloitte\b": "Deloitte",
    r"\bpwc\b|\bpricewaterhousecoopers\b": "PwC",
    r"\bkpmg\b": "KPMG",
    r"\bey\b|\bernst & young\b|\bernst and young\b": "EY",
    r"\bbain\b": "Bain",
    r"\bbcg\b|\bboston consulting\b": "BCG",
    r"\bmckinsey\b": "McKinsey",
    r"\bepam\b": "EPAM",
    r"\bglobal logic\b|\bgloballogic\b": "GlobalLogic",
    r"\bsabre\b": "Sabre",
    r"\bunisys\b": "Unisys",
    r"\bleidos\b": "Leidos",
    r"\bbooz allen\b": "Booz Allen",
    r"\bsaic\b": "SAIC",
    r"\braytheon\b": "Raytheon",
    r"\blockheed martin\b": "Lockheed Martin",
    r"\bnorthrop grumman\b": "Northrop Grumman",
    r"\bgeneral dynamics\b": "General Dynamics",
    r"\bbae systems\b": "BAE Systems",
    # Semiconductor / Hardware
    r"\bamd\b|\badvanced micro devices\b": "AMD",
    r"\barm\b": "ARM",
    r"\bapplied materials\b": "Applied Materials",
    r"\bklainc\b|\bkla\b": "KLA",
    r"\bmarvell\b": "Marvell",
    r"\banalog devices\b": "Analog Devices",
    r"\btexas instruments\b": "Texas Instruments",
    r"\bmicron\b": "Micron",
    r"\bwestern digital\b": "Western Digital",
    r"\bseagate\b": "Seagate",
    # Healthcare / Bio
    r"\bpfizer\b": "Pfizer",
    r"\bjohnson & johnson\b|\bjnj\b": "J&J",
    r"\babbvie\b": "AbbVie",
    r"\beli lilly\b|\belly lilly\b": "Eli Lilly",
    r"\bmerck\b": "Merck",
    r"\bbristol.myers\b|\bbms\b": "BMS",
    r"\bgenentech\b|\broche\b": "Roche / Genentech",
    r"\bnovartis\b": "Novartis",
    r"\bastrazeneca\b": "AstraZeneca",
    r"\bgilead\b": "Gilead",
    r"\bbiogen\b": "Biogen",
    r"\bamgen\b": "Amgen",
    r"\bmedtronic\b": "Medtronic",
    r"\bbecton dickinson\b|\bbd \b": "BD",
    r"\babbott\b": "Abbott",
    r"\bunitedhealth\b|\boptum\b": "UnitedHealth / Optum",
    r"\bcvs health\b|\baetna\b": "CVS / Aetna",
    # Other well-known tech
    r"\bsamsung\b": "Samsung",
    r"\bhuawei\b": "Huawei",
    r"\blg\b": "LG",
    r"\bsony\b": "Sony",
    r"\bsiemens\b": "Siemens",
    r"\bphilips\b": "Philips",
    r"\bering\b|\bamazon ring\b": "Ring (Amazon)",
    r"\btesla\b": "Tesla",
    r"\bspacex\b": "SpaceX",
    r"\bboeing\b": "Boeing",
    r"\bgeneral electric\b|\bge \b": "GE",
    r"\beat\b": "EA",
    r"\bactivision\b": "Activision",
    r"\bnintendo\b": "Nintendo",
    # Universities / Research
    r"\bmit\b|\bmassachusetts institute of technology\b": "MIT",
    r"\bstanford\b": "Stanford",
    r"\bharvard\b": "Harvard",
    r"\buc berkeley\b|\buniversity of california.+berkeley\b": "UC Berkeley",
    r"\buniversity of washington\b": "UW",
    r"\bcarnegie mellon\b": "CMU",
}

def canonicalise_employer(raw_name: str) -> str:
    """Return a short canonical employer label."""
    if not isinstance(raw_name, str):
        return "Unknown"
    lower = raw_name.lower().strip()
    for pattern, label in EMPLOYER_MAP.items():
        if re.search(pattern, lower):
            return label
    # Fallback: title-case up to the first comma, ampersand, or LLC/Inc suffix
    clean = re.sub(r"\b(inc\.?|llc\.?|corp\.?|ltd\.?|l\.l\.c\.?|pbc)\b.*",
                   "", raw_name, flags=re.I).strip().rstrip(",").strip()
    return clean.title() if clean else raw_name.title()


# ---------------------------------------------------------------------------
# 2.  JOB CATEGORY CLASSIFICATION
#     Map (SOC code, job title) → one of the 13 canonical categories.
# ---------------------------------------------------------------------------

# SOC prefix → category (checked first)
SOC_CATEGORY_MAP = {
    "15-1252": "Software Engineer",
    "15-1253": "Software Engineer",
    "15-1256": "Software Engineer",
    "15-1299": "Software Engineer",
    "15-1211": "Software Engineer",
    "15-1212": "Software Engineer",
    "15-1231": "Software Engineer",
    "15-1232": "Software Engineer",
    "15-1241": "DevOps / SRE",
    "15-1242": "DevOps / SRE",
    "15-1243": "DevOps / SRE",
    "15-1244": "Security Engineer",
    "15-1245": "Security Engineer",
    "15-1246": "Security Engineer",
    "15-1221": "Data Analyst",
    "15-1222": "Data Analyst",
    "15-2031": "Data Analyst",
    "15-2041": "Data Scientist",
    "15-2051": "Data Scientist",
    "15-1255": "Data Scientist",
    "15-2099": "Data Scientist",
    "11-3021": "DevOps / SRE",
    "17-2061": "Hardware Engineer",
    "17-2072": "Hardware Engineer",
    "17-2141": "Hardware Engineer",
    "17-2071": "Hardware Engineer",
    "17-2112": "Hardware Engineer",
    "17-2199": "Hardware Engineer",
    "11-2021": "Product Manager",
    "11-9199": "Product Manager",
    "15-1120": "Product Manager",
    "27-1024": "Designer",
    "27-1021": "Designer",
    "27-1025": "Designer",
    "13-1161": "Consultant",
    "13-1199": "Consultant",
    "13-2099": "Finance / Quant",
    "13-2011": "Finance / Quant",
    "13-2051": "Finance / Quant",
    "15-2031": "Finance / Quant",
}

# Title keyword → category (fallback when SOC doesn't match)
TITLE_CATEGORY_KEYWORDS = [
    (r"machine learning|ml engineer|deep learning|mlops", "Machine Learning Engineer"),
    (r"data science|data scientist", "Data Scientist"),
    (r"data engineer|etl|pipeline|spark|kafka", "Data Engineer"),
    (r"data analyst|business analyst|bi\b|business intelligence|tableau|power bi", "Data Analyst"),
    (r"devops|sre|site reliability|platform engineer|infra|infrastructure|cloud engineer|devsecops", "DevOps / SRE"),
    (r"security|cyber|appsec|infosec|penetration|soc analyst|identity", "Security Engineer"),
    (r"hardware|firmware|fpga|vlsi|asic|embedded|rf engineer|circuit|pcb|chip|silicon", "Hardware Engineer"),
    (r"product manager|program manager|technical program|tpm\b|product owner", "Product Manager"),
    (r"ux|ui\b|user experience|designer|visual design|graphic|product design|interaction design", "Designer"),
    (r"quant|quantitative|actuar|financial engineer|risk model|algorithmic trad|hedge fund", "Finance / Quant"),
    (r"consultant|advisory|strategy\b|management consult", "Consultant"),
    (r"software engineer|software developer|sde\b|swe\b|backend|front.?end|full.?stack|mobile dev|ios dev|android dev|web dev", "Software Engineer"),
]

def classify_job(soc_code: str, job_title: str) -> str:
    """Return one of the 13 canonical job categories."""
    # 1) SOC prefix match
    if isinstance(soc_code, str):
        prefix = soc_code[:7]  # e.g. "15-1252"
        if prefix in SOC_CATEGORY_MAP:
            return SOC_CATEGORY_MAP[prefix]
        prefix6 = soc_code[:6]
        if prefix6 in SOC_CATEGORY_MAP:
            return SOC_CATEGORY_MAP[prefix6]

    # 2) Title keyword match
    if isinstance(job_title, str):
        lower = job_title.lower()
        for pattern, cat in TITLE_CATEGORY_KEYWORDS:
            if re.search(pattern, lower):
                return cat

    return "Other"


# ---------------------------------------------------------------------------
# 3.  SENIORITY CLASSIFICATION
#     Map job title keywords → {Mid, Senior, Staff/Lead, Manager+}
# ---------------------------------------------------------------------------

def classify_seniority(job_title: str) -> str:
    if not isinstance(job_title, str):
        return "Mid"
    lower = job_title.lower()
    if re.search(r"\bmanager\b|\bdirector\b|\bvp\b|\bvice president\b|\bhead of\b|\bchief\b|\bcto\b|\bceo\b|\bcoo\b|\bcfo\b|\bpresident\b|\bsvp\b|\bevp\b|\bgm\b\b|general manager", lower):
        return "Manager+"
    if re.search(r"\bstaff\b|\blead\b|\bprincipal\b|\bdistinguished\b|\barchitect\b|\bfellow\b", lower):
        return "Staff/Lead"
    if re.search(r"\bsenior\b|\bsr\.\b|\bsr \b|\biii\b|\bexpert\b|\bspecialist ii\b", lower):
        return "Senior"
    return "Mid"


# ---------------------------------------------------------------------------
# 4.  WAGE ANNUALISATION
# ---------------------------------------------------------------------------

HOURS_PER_WEEK = 40
WEEKS_PER_YEAR = 52

def annualise(value_str: str, unit: str) -> float | None:
    """Convert a dollar-formatted wage string + unit to an annual float."""
    if not isinstance(value_str, str):
        return None
    amount_str = re.sub(r"[,$]", "", value_str.strip())
    try:
        amount = float(amount_str)
    except ValueError:
        return None

    unit = str(unit).strip().lower() if isinstance(unit, str) else ""
    if unit == "year":
        return round(amount, 2)
    elif unit == "hour":
        return round(amount * HOURS_PER_WEEK * WEEKS_PER_YEAR, 2)
    elif unit == "month":
        return round(amount * 12, 2)
    elif unit == "week":
        return round(amount * WEEKS_PER_YEAR, 2)
    elif unit == "bi-weekly":
        return round(amount * 26, 2)
    else:
        return round(amount, 2)


# ---------------------------------------------------------------------------
# 5.  MAIN TRANSFORM
# ---------------------------------------------------------------------------

def _apply_transforms(lca: pd.DataFrame) -> pd.DataFrame:
    """
    Core transform logic applied to an already-loaded DataFrame.
    Shared by both transform() (CSV path → CSV path) and
    transform_dataframe() (DataFrame → DataFrame).
    """
    # -- keep only H-1B records (drop H-1B1, E-3, etc. if present)
    if "VISA_CLASS" in lca.columns:
        lca = lca[lca["VISA_CLASS"].str.contains("H-1B", na=False)].copy()
        print(f"  {len(lca):,} rows after filtering to H-1B.")

    # -- employer labels
    lca["employer_clean"] = lca["EMPLOYER_NAME"].apply(canonicalise_employer)
    lca["employer_name"] = lca["EMPLOYER_NAME"].fillna("").str.strip()

    # -- job fields
    lca["job_title"] = lca["JOB_TITLE"].fillna("").str.strip()
    lca["soc_code"] = lca["SOC_CODE"].fillna("").str.strip().str[:7]
    lca["soc_title"] = lca["SOC_TITLE"].fillna("").str.strip()

    lca["job_category"] = lca.apply(
        lambda r: classify_job(r["SOC_CODE"], r["JOB_TITLE"]), axis=1
    )
    lca["seniority"] = lca["JOB_TITLE"].apply(classify_seniority)

    # -- worksite
    lca["worksite_city"] = lca["WORKSITE_CITY"].fillna("").str.strip().str.title()
    lca["worksite_state"] = lca["WORKSITE_STATE"].fillna("").str.strip().str.upper()

    # -- wages (annualised)
    lca["wage_annual"] = lca.apply(
        lambda r: annualise(r["WAGE_RATE_OF_PAY_FROM"], r["WAGE_UNIT_OF_PAY"]), axis=1
    )
    lca["prevailing_wage_annual"] = lca.apply(
        lambda r: annualise(r["PREVAILING_WAGE"], r["PW_UNIT_OF_PAY"]), axis=1
    )

    # -- dates
    lca["start_date"] = pd.to_datetime(lca["BEGIN_DATE"], errors="coerce").dt.strftime("%Y-%m-%d")

    # -- case status: strip " - Withdrawn" suffix to normalise
    lca["case_status"] = (
        lca["CASE_STATUS"]
        .fillna("")
        .str.replace(r"\s*-\s*Withdrawn", "", regex=True)
        .str.strip()
    )

    # -- is_new_hire: NEW_EMPLOYMENT == 1
    lca["is_new_hire"] = lca["NEW_EMPLOYMENT"].fillna(0).astype(int).astype(bool)

    # -- total workers
    lca["total_workers"] = lca["TOTAL_WORKER_POSITIONS"].fillna(1).astype(int)

    # -- assemble output columns
    out_cols = [
        "employer_clean", "employer_name", "job_title", "job_category",
        "seniority", "worksite_city", "worksite_state",
        "wage_annual", "prevailing_wage_annual",
        "start_date", "case_status", "is_new_hire", "total_workers",
        "soc_code", "soc_title",
    ]
    result = lca[out_cols].reset_index(drop=True)

    # -- drop rows missing critical wage/city info
    result = result.dropna(subset=["wage_annual", "prevailing_wage_annual"])
    result = result[result["worksite_city"] != ""]

    print(f"  {len(result):,} rows after cleaning.")
    return result


def transform_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform an already-loaded raw DOL LCA DataFrame into cleaned format.
    Called by scraper.py after downloading and reading the Excel file.
    """
    return _apply_transforms(df.copy())


def transform(lca_path: str, out_path: str) -> pd.DataFrame:
    print(f"Reading LCA file: {lca_path}")
    lca = pd.read_csv(lca_path, encoding="latin1", low_memory=False)
    print(f"  {len(lca):,} rows loaded.")

    result = _apply_transforms(lca)
    result.to_csv(out_path, index=False)
    print(f"Output written to: {out_path}")
    return result


# ---------------------------------------------------------------------------
# 6.  CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transform DOL LCA data to cleaned format.")
    parser.add_argument("--lca", default="REAL_LCA_Data.csv", help="Path to LCA CSV")
    parser.add_argument("--pw",  default="REAL_Prevailing_Wage_data.csv",
                        help="Path to Prevailing Wage CSV (currently unused in merge but accepted)")
    parser.add_argument("--out", default="output_cleaned.csv", help="Output CSV path")
    args = parser.parse_args()

    df = transform(args.lca, args.out)
    print("\nSample output:")
    print(df.head(5).to_string())
    print("\nColumn dtypes:")
    print(df.dtypes)
    print("\nJob category distribution:")
    print(df["job_category"].value_counts())
    print("\nSeniority distribution:")
    print(df["seniority"].value_counts())
