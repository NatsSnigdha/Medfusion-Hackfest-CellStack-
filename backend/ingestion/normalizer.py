"""
ingestion/normalizer.py
Unifies all API data into a single standard schema.
Output: list of DiseaseRecord dicts that analytics can consume.
"""

from datetime import datetime, timezone
from typing import Any


STANDARD_DISEASES = {
    "COVID-19":    {"species": "SARS-CoV-2",                   "type": "viral"},
    "Influenza":   {"species": "Influenza A/B",                 "type": "viral"},
    "Dengue":      {"species": "DENV 1-4",                      "type": "viral"},
    "Malaria":     {"species": "Plasmodium falciparum",         "type": "parasitic"},
    "Cholera":     {"species": "Vibrio cholerae",               "type": "bacterial"},
    "Tuberculosis":{"species": "Mycobacterium tuberculosis",    "type": "bacterial"},
    "Mpox":        {"species": "Monkeypox virus",               "type": "viral"},
}


def normalize_all(raw: dict) -> list[dict]:
    """
    Master normalizer. Takes raw fetch_all() output,
    returns unified list of DiseaseRecord dicts.
    """
    records = []
    records.extend(_norm_covid(raw.get("covid_by_country", [])))
    records.extend(_norm_who_all(raw.get("who_all_diseases", [])))
    records.extend(_norm_flu(raw.get("flu_us", [])))
    return records


def _norm_covid(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        out.append({
            "disease":          "COVID-19",
            "species":          "SARS-CoV-2",
            "disease_type":     "viral",
            "country":          r.get("country", "Unknown"),
            "iso2":             r.get("iso2", ""),
            "lat":              r.get("lat", 0.0),
            "lon":              r.get("lon", 0.0),
            "cases_total":      int(r.get("cases", 0) or 0),
            "deaths_total":     int(r.get("deaths", 0) or 0),
            "cases_today":      int(r.get("cases_today", 0) or 0),
            "deaths_today":     int(r.get("deaths_today", 0) or 0),
            "active":           int(r.get("active", 0) or 0),
            "cases_per_million":float(r.get("cases_per_million", 0) or 0),
            "cfr":              _safe_cfr(r.get("deaths", 0), r.get("cases", 0)),
            "source":           "disease.sh",
            "fetched_at":       r.get("fetched_at", _now()),
        })
    return out


def _norm_who_all(raw: list[dict]) -> list[dict]:
    """
    Normalize all WHO GHO records from the merged indicator fetch.
    Uses ISO-3 country code + WHO country name lookup for display.
    Deduplicates: keeps most recent year per (disease, country).
    """
    # First pass: collect all records
    seen: dict[tuple, dict] = {}
    for r in raw:
        disease = r.get("disease", "")
        country_code = r.get("country", "")
        if not disease or not country_code:
            continue

        key = (disease, country_code)
        year = r.get("year", 0) or 0
        # Keep the most recent year's record
        if key not in seen or year > (seen[key].get("year", 0) or 0):
            country_name = _iso3_to_name(country_code)
            if not country_name:
                continue
            seen[key] = {
                "disease":      disease,
                "species":      r.get("species", "Unknown"),
                "disease_type": r.get("disease_type", "unknown"),
                "country":      country_name,
                "iso2":         country_code,
                "lat":          0.0,
                "lon":          0.0,
                "year":         year,
                "value":        float(r.get("value", 0) or 0),
                "indicator":    r.get("indicator", ""),
                # Map WHO value to cases_total for map rendering
                "cases_total":  int(float(r.get("value", 0) or 0)),
                "deaths_total": 0,
                "cases_today":  0,
                "deaths_today": 0,
                "cfr":          0.0,
                "source":       "WHO GHO",
                "fetched_at":   r.get("fetched_at", _now()),
            }

    return list(seen.values())


# ISO-3 → country name lookup (WHO uses ISO-3 codes)
_ISO3_MAP: dict[str, str] = {
    "AFG":"Afghanistan","ALB":"Albania","DZA":"Algeria","AGO":"Angola",
    "ARG":"Argentina","ARM":"Armenia","AUS":"Australia","AUT":"Austria",
    "AZE":"Azerbaijan","BGD":"Bangladesh","BLR":"Belarus","BEL":"Belgium",
    "BEN":"Benin","BOL":"Bolivia","BIH":"Bosnia and Herzegovina",
    "BWA":"Botswana","BRA":"Brazil","BGR":"Bulgaria","BFA":"Burkina Faso",
    "BDI":"Burundi","KHM":"Cambodia","CMR":"Cameroon","CAN":"Canada",
    "CAF":"Central African Republic","TCD":"Chad","CHL":"Chile","CHN":"China",
    "COL":"Colombia","COD":"Democratic Republic of the Congo","COG":"Congo",
    "CRI":"Costa Rica","CIV":"Cote d'Ivoire","HRV":"Croatia","CUB":"Cuba",
    "CZE":"Czech Republic","DNK":"Denmark","DOM":"Dominican Republic",
    "ECU":"Ecuador","EGY":"Egypt","SLV":"El Salvador","ETH":"Ethiopia",
    "FIN":"Finland","FRA":"France","GAB":"Gabon","GMB":"Gambia",
    "GEO":"Georgia","DEU":"Germany","GHA":"Ghana","GRC":"Greece",
    "GTM":"Guatemala","GIN":"Guinea","HTI":"Haiti","HND":"Honduras",
    "HUN":"Hungary","IND":"India","IDN":"Indonesia","IRN":"Iran",
    "IRQ":"Iraq","IRL":"Ireland","ISR":"Israel","ITA":"Italy",
    "JAM":"Jamaica","JPN":"Japan","JOR":"Jordan","KAZ":"Kazakhstan",
    "KEN":"Kenya","PRK":"North Korea","KOR":"South Korea","KWT":"Kuwait",
    "KGZ":"Kyrgyzstan","LAO":"Laos","LBN":"Lebanon","LBR":"Liberia",
    "LBY":"Libya","LTU":"Lithuania","MKD":"North Macedonia","MDG":"Madagascar",
    "MWI":"Malawi","MYS":"Malaysia","MLI":"Mali","MRT":"Mauritania",
    "MEX":"Mexico","MDA":"Moldova","MNG":"Mongolia","MAR":"Morocco",
    "MOZ":"Mozambique","MMR":"Myanmar","NAM":"Namibia","NPL":"Nepal",
    "NLD":"Netherlands","NZL":"New Zealand","NIC":"Nicaragua","NER":"Niger",
    "NGA":"Nigeria","NOR":"Norway","OMN":"Oman","PAK":"Pakistan",
    "PAN":"Panama","PNG":"Papua New Guinea","PRY":"Paraguay","PER":"Peru",
    "PHL":"Philippines","POL":"Poland","PRT":"Portugal","QAT":"Qatar",
    "ROU":"Romania","RUS":"Russia","RWA":"Rwanda","SAU":"Saudi Arabia",
    "SEN":"Senegal","SLE":"Sierra Leone","SOM":"Somalia","ZAF":"South Africa",
    "SSD":"South Sudan","ESP":"Spain","LKA":"Sri Lanka","SDN":"Sudan",
    "SWE":"Sweden","CHE":"Switzerland","SYR":"Syria","TWN":"Taiwan",
    "TJK":"Tajikistan","TZA":"Tanzania","THA":"Thailand","TLS":"Timor-Leste",
    "TGO":"Togo","TTO":"Trinidad and Tobago","TUN":"Tunisia","TUR":"Turkey",
    "TKM":"Turkmenistan","UGA":"Uganda","UKR":"Ukraine","ARE":"United Arab Emirates",
    "GBR":"United Kingdom","USA":"United States","URY":"Uruguay",
    "UZB":"Uzbekistan","VEN":"Venezuela","VNM":"Vietnam","YEM":"Yemen",
    "ZMB":"Zambia","ZWE":"Zimbabwe",
}

def _iso3_to_name(code: str) -> str:
    return _ISO3_MAP.get(code, "")


def _norm_who(raw: list[dict], disease: str) -> list[dict]:
    """Legacy single-disease normalizer — kept for compatibility."""
    meta = STANDARD_DISEASES.get(disease, {})
    out = []
    for r in raw:
        country_name = _iso3_to_name(r.get("country", ""))
        if not country_name:
            continue
        out.append({
            "disease":      disease,
            "species":      meta.get("species", "Unknown"),
            "disease_type": meta.get("type", "unknown"),
            "country":      country_name,
            "iso2":         r.get("country", ""),
            "lat":          0.0,
            "lon":          0.0,
            "year":         int(r.get("year", 0) or 0),
            "value":        float(r.get("value", 0) or 0),
            "cases_total":  int(float(r.get("value", 0) or 0)),
            "deaths_total": 0,
            "cases_today":  0,
            "deaths_today": 0,
            "cfr":          0.0,
            "source":       "WHO GHO",
            "fetched_at":   r.get("fetched_at", _now()),
        })
    return out


def _norm_flu(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        out.append({
            "disease":      "Influenza",
            "species":      "Influenza A/B",
            "disease_type": "viral",
            "country":      "United States",
            "iso2":         "US",
            "lat":          37.09,
            "lon":          -95.71,
            "epiweek":      r.get("epiweek", 0),
            "ili_rate":     float(r.get("ili_rate", 0) or 0),
            "cases_total":  0,
            "deaths_total": 0,
            "cases_today":  0,
            "deaths_today": 0,
            "source":       "CMU Delphi",
            "fetched_at":   r.get("fetched_at", _now()),
        })
    return out


def _safe_cfr(deaths: Any, cases: Any) -> float:
    try:
        d, c = float(deaths or 0), float(cases or 0)
        return round((d / c) * 100, 3) if c > 0 else 0.0
    except Exception:
        return 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()