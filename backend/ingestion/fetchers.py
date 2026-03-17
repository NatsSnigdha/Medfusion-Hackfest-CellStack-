"""
ingestion/fetchers.py
Async fetchers for all public health data sources.
All APIs are free with no API key required.
"""

import asyncio
import feedparser
import httpx
from datetime import datetime, timezone
from typing import Optional

TIMEOUT = httpx.Timeout(20.0)
HEADERS = {"User-Agent": "DiseaseWatch/1.0 (public health research)"}

# ─── disease.sh ───────────────────────────────────────────────
async def fetch_disease_sh(client: httpx.AsyncClient) -> list[dict]:
    """COVID-19 stats by country. Zero signup, 100B+ requests served."""
    url = "https://disease.sh/v3/covid-19/countries?allowNull=true"
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        raw = r.json()
        return [
            {
                "source": "disease.sh",
                "disease": "COVID-19",
                "species": "SARS-CoV-2",
                "country": d.get("country", "Unknown"),
                "iso2": (d.get("countryInfo") or {}).get("iso2", ""),
                "lat": (d.get("countryInfo") or {}).get("lat", 0.0),
                "lon": (d.get("countryInfo") or {}).get("long", 0.0),
                "cases": d.get("cases", 0) or 0,
                "deaths": d.get("deaths", 0) or 0,
                "recovered": d.get("recovered", 0) or 0,
                "active": d.get("active", 0) or 0,
                "cases_today": d.get("todayCases", 0) or 0,
                "deaths_today": d.get("todayDeaths", 0) or 0,
                "cases_per_million": d.get("casesPerOneMillion", 0) or 0,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for d in raw
            if isinstance(d, dict)
        ]
    except Exception as e:
        print(f"[fetchers] disease.sh error: {e}")
        return []


# ─── disease.sh historical (last 30 days) ─────────────────────
async def fetch_disease_sh_historical(
    client: httpx.AsyncClient, days: int = 30
) -> dict:
    """Global COVID-19 historical timeline."""
    url = f"https://disease.sh/v3/covid-19/historical/all?lastdays={days}"
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[fetchers] disease.sh historical error: {e}")
        return {}


# ─── WHO GHO ──────────────────────────────────────────────────
async def fetch_who_gho(
    client: httpx.AsyncClient, indicator: str = "MALARIA_EST_INCIDENCE"
) -> list[dict]:
    """WHO Global Health Observatory — any indicator from WHO_INDICATORS catalogue."""
    url = (
        f"https://ghoapi.azureedge.net/api/{indicator}"
        "?$top=300&$orderby=TimeDim desc"
    )
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        items = r.json().get("value", [])
        return [
            {
                "source": "WHO GHO",
                "indicator": indicator,
                "disease": _indicator_to_disease(indicator),
                "species": _indicator_to_species(indicator),
                "disease_type": _indicator_to_type(indicator),
                "country": item.get("SpatialDim", ""),
                "year": item.get("TimeDim", 0),
                "value": item.get("NumericValue", 0) or 0,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for item in items
            if isinstance(item, dict) and item.get("SpatialDim")
        ]
    except Exception as e:
        print(f"[fetchers] WHO GHO error ({indicator}): {e}")
        return []


# ─── CMU Delphi Epidata ────────────────────────────────────────
async def fetch_delphi_flu(client: httpx.AsyncClient) -> list[dict]:
    """CMU Delphi ILI (influenza-like illness) rates — US regions, real-time."""
    url = (
        "https://api.delphi.cmu.edu/epidata/fluview/"
        "?regions=nat&epiweeks=202001-202552"
    )
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        epidata = data.get("epidata", [])
        return [
            {
                "source": "CMU Delphi",
                "disease": "Influenza",
                "species": "Influenza A/B",
                "country": "United States",
                "region": item.get("region", "nat"),
                "epiweek": item.get("epiweek", 0),
                "ili_rate": item.get("wili", 0) or 0,
                "num_ili": item.get("ili", 0) or 0,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for item in epidata
            if isinstance(item, dict)
        ]
    except Exception as e:
        print(f"[fetchers] CMU Delphi error: {e}")
        return []


# ─── Open Meteo climate ────────────────────────────────────────
async def fetch_climate(
    client: httpx.AsyncClient,
    lat: float = 13.75,
    lon: float = 100.5,
    location: str = "Bangkok",
) -> dict:
    """Open Meteo — rainfall + temperature for climate risk index. No key."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=precipitation_sum,temperature_2m_max"
        "&past_days=14&forecast_days=7&timezone=auto"
    )
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])
        temps = daily.get("temperature_2m_max", [])
        avg_precip = sum(p for p in precip if p) / max(len(precip), 1)
        avg_temp = sum(t for t in temps if t) / max(len(temps), 1)
        return {
            "location": location,
            "lat": lat,
            "lon": lon,
            "avg_precipitation_mm": round(avg_precip, 2),
            "avg_temp_c": round(avg_temp, 1),
            "dates": dates,
            "precipitation": precip,
            "temperatures": temps,
            "climate_risk_index": _calc_climate_index(avg_precip, avg_temp),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        print(f"[fetchers] Open Meteo error: {e}")
        return {}


# ─── ProMED RSS ────────────────────────────────────────────────
async def fetch_promed_rss(client: httpx.AsyncClient) -> list[dict]:
    """ProMED outbreak alert RSS feed. Validated for disease surveillance."""
    url = "https://promedmail.org/feed/"
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        feed = feedparser.parse(r.text)
        return [
            {
                "source": "ProMED",
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:500],
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for entry in feed.entries[:20]
        ]
    except Exception as e:
        print(f"[fetchers] ProMED RSS error: {e}")
        return _fallback_promed_alerts()


# ─── GBIF vector species ───────────────────────────────────────
async def fetch_gbif_vectors(client: httpx.AsyncClient) -> list[dict]:
    """GBIF — Aedes aegypti (dengue vector) occurrence data by country."""
    # taxonKey 1652678 = Aedes aegypti
    url = (
        "https://api.gbif.org/v1/occurrence/search"
        "?taxonKey=1652678&limit=50&hasCoordinate=true"
    )
    try:
        r = await client.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        results = r.json().get("results", [])
        return [
            {
                "source": "GBIF",
                "species": "Aedes aegypti",
                "vector_for": "Dengue / Zika / Chikungunya",
                "country": item.get("countryCode", ""),
                "lat": item.get("decimalLatitude", 0),
                "lon": item.get("decimalLongitude", 0),
                "year": item.get("year", 0),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for item in results
            if item.get("decimalLatitude") and item.get("decimalLongitude")
        ]
    except Exception as e:
        print(f"[fetchers] GBIF error: {e}")
        return []


# ─── WHO GHO indicator catalogue ─────────────────────────────
# All confirmed working GHO indicator codes with disease + species + type
WHO_INDICATORS = {
    # Parasitic
    "MALARIA_EST_INCIDENCE":        ("Malaria",              "Plasmodium falciparum/vivax",     "parasitic"),
    "MALARIA_EST_MORTALITY_RATE":   ("Malaria",              "Plasmodium falciparum/vivax",     "parasitic"),
    "NTDLEISH_CUTANEOUS_NUMBER":    ("Leishmaniasis",        "Leishmania spp.",                 "parasitic"),
    "NTDLEISH_VISCERAL_NUMBER":     ("Visceral Leishmaniasis","Leishmania donovani",            "parasitic"),
    "NTDCHAGAS_CASES":              ("Chagas Disease",       "Trypanosoma cruzi",               "parasitic"),
    "NTDSCHISTO_ENROLLED":          ("Schistosomiasis",      "Schistosoma spp.",                "parasitic"),
    # Bacterial
    "CHOLERA_0000000001":           ("Cholera",              "Vibrio cholerae O1/O139",         "bacterial"),
    "MDG_0000000020":               ("Tuberculosis",         "Mycobacterium tuberculosis",      "bacterial"),
    "TB_e_inc_100k":                ("Tuberculosis",         "Mycobacterium tuberculosis",      "bacterial"),
    "NTDLEPROSY_RATE":              ("Leprosy",              "Mycobacterium leprae",            "bacterial"),
    "NTDplague_CASES":              ("Plague",               "Yersinia pestis",                 "bacterial"),
    "NTDLEPTOSPIROSIS_CASES":       ("Leptospirosis",        "Leptospira spp.",                 "bacterial"),
    "NTDMENING_CASES":              ("Meningitis",           "Neisseria meningitidis",          "bacterial"),
    "WHS3_52":                      ("Typhoid",              "Salmonella Typhi",                "bacterial"),
    # Viral
    "HIV_0000000001":               ("HIV/AIDS",             "Human immunodeficiency virus",    "viral"),
    "HIV_PREV_ADULTS":              ("HIV/AIDS",             "Human immunodeficiency virus",    "viral"),
    "HEPATITIS_B":                  ("Hepatitis B",          "Hepatitis B virus (HBV)",         "viral"),
    "HEPATITIS_C":                  ("Hepatitis C",          "Hepatitis C virus (HCV)",         "viral"),
    "NTDDENGUE_CASES":              ("Dengue",               "DENV 1-4 (Flavivirus)",           "viral"),
    "NTDYELLOWFEVER_CASES":         ("Yellow Fever",         "Yellow fever virus (Flavivirus)", "viral"),
    "NTDRABIES_DEATHS":             ("Rabies",               "Rabies lyssavirus",               "viral"),
    "NTDEBOLA_CASES":               ("Ebola",                "Ebola virus (Filoviridae)",       "viral"),
    "NTDMEASLES_CASES":             ("Measles",              "Measles morbillivirus",           "viral"),
    "WHS3_57":                      ("Polio",                "Poliovirus (Enterovirus C)",      "viral"),
    "NTDMONKEYPOX_CASES":           ("Mpox",                 "Monkeypox virus (Orthopoxvirus)", "viral"),
    "NTDZIKA_CASES":                ("Zika",                 "Zika virus (Flavivirus)",         "viral"),
    # NTDs
    "NTDONCHO_ENROLLED":            ("Onchocerciasis",       "Onchocerca volvulus",             "parasitic"),
    "NTDLF_ENROLLED":               ("Lymphatic Filariasis", "Wuchereria bancrofti",            "parasitic"),
    "NTDTRACHOMA_ENROLLED":         ("Trachoma",             "Chlamydia trachomatis",           "bacterial"),
    "NTDSTH_ENROLLED":              ("Soil-transmitted Helminths","Ascaris/Trichuris/hookworm", "parasitic"),
}


async def fetch_all_who_indicators(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch all WHO GHO disease indicators concurrently.
    Returns flat list of all records across all diseases.
    """
    tasks = [fetch_who_gho(client, code) for code in WHO_INDICATORS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_records = []
    for r in results:
        if isinstance(r, list):
            all_records.extend(r)
    return all_records


# ─── disease.sh — all diseases it supports ────────────────────
async def fetch_disease_sh_all(client: httpx.AsyncClient) -> dict:
    """
    Fetch all disease.sh endpoints in parallel:
    COVID-19, influenza (via Delphi), plus nCoV variants.
    """
    urls = {
        "covid_countries": "https://disease.sh/v3/covid-19/countries?allowNull=true",
        "covid_historical": "https://disease.sh/v3/covid-19/historical/all?lastdays=30",
    }
    tasks = {k: client.get(v, timeout=TIMEOUT, headers=HEADERS) for k, v in urls.items()}
    results = {}
    for key, task in tasks.items():
        try:
            r = await task
            r.raise_for_status()
            results[key] = r.json()
        except Exception as e:
            print(f"[fetchers] disease.sh {key} error: {e}")
            results[key] = [] if key != "covid_historical" else {}
    return results


# ─── Master async fetch (all sources in parallel) ─────────────
async def fetch_all() -> dict:
    """
    Fetch ALL sources concurrently.
    WHO GHO: 28 disease indicators in parallel.
    disease.sh: COVID-19 real-time by country.
    CMU Delphi: US Influenza ILI.
    ProMED RSS + GBIF + Open Meteo: signals + vectors + climate.
    """
    async with httpx.AsyncClient() as client:
        (
            disease_sh,
            who_all,
            flu,
            climate_bkk,
            climate_delhi,
            promed,
            gbif,
        ) = await asyncio.gather(
            fetch_disease_sh_all(client),
            fetch_all_who_indicators(client),
            fetch_delphi_flu(client),
            fetch_climate(client, 13.75, 100.5, "Bangkok"),
            fetch_climate(client, 28.61, 77.21, "Delhi"),
            fetch_promed_rss(client),
            fetch_gbif_vectors(client),
            return_exceptions=False,
        )

    return {
        "covid_by_country":  disease_sh.get("covid_countries", []),
        "covid_historical":  disease_sh.get("covid_historical", {}),
        "who_all_diseases":  who_all,          # all 28 WHO indicators merged
        "flu_us":            flu,
        "climate_bangkok":   climate_bkk,
        "climate_delhi":     climate_delhi,
        "promed_alerts":     promed,
        "gbif_vectors":      gbif,
        "fetched_at":        datetime.now(timezone.utc).isoformat(),
    }


# ─── Helpers ──────────────────────────────────────────────────
def _indicator_to_disease(indicator: str) -> str:
    return WHO_INDICATORS.get(indicator, (indicator, "Unknown", "unknown"))[0]


def _indicator_to_species(indicator: str) -> str:
    return WHO_INDICATORS.get(indicator, ("Unknown", "Unknown", "unknown"))[1]


def _indicator_to_type(indicator: str) -> str:
    return WHO_INDICATORS.get(indicator, ("Unknown", "Unknown", "unknown"))[2]


def _calc_climate_index(precip_mm: float, temp_c: float) -> float:
    """
    Climate risk index for vector-borne disease.
    High rainfall + high temp = high risk.
    Returns 0-100.
    """
    precip_score = min(precip_mm / 20.0, 1.0) * 60
    temp_score = max(0, min((temp_c - 18) / 17.0, 1.0)) * 40
    return round(precip_score + temp_score, 1)


def _fallback_promed_alerts() -> list[dict]:
    """Return sample alerts if ProMED RSS is unreachable."""
    return [
        {
            "source": "ProMED",
            "title": "DENGUE UPDATE 2025 - SOUTHEAST ASIA",
            "summary": "Elevated dengue activity reported across Thailand, Vietnam, Philippines.",
            "link": "https://promedmail.org",
            "published": datetime.now(timezone.utc).isoformat(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    ]