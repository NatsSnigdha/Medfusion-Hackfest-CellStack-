"""
analytics/pipeline.py
Master orchestrator — runs full data pipeline in one call.
"""

import asyncio
from ingestion.fetchers import fetch_all, WHO_INDICATORS
from ingestion.normalizer import normalize_all
from analytics.epi_engine import (
    estimate_rt,
    calc_velocity,
    calc_outbreak_score,
    calc_global_threat,
    build_what_changed,
    calc_confidence,
)
from analytics.store import (
    init_db,
    upsert_records,
    upsert_scores,
    upsert_alerts,
    save_parquet_snapshot,
    query_top_countries,
    query_all_countries_map,
    query_alerts,
    query_scores,
)

# Indicators that provide mortality/deaths data
MORTALITY_INDICATORS = {
    "MALARIA_EST_MORTALITY_RATE", "NTDRABIES_DEATHS", "NTDEBOLA_CASES",
}


def run_pipeline() -> dict:
    init_db()

    raw = asyncio.run(fetch_all())
    records = normalize_all(raw)

    disease_counts = {}
    for r in records:
        d = r.get("disease", "Unknown")
        disease_counts[d] = disease_counts.get(d, 0) + 1
    print(f"[pipeline] Loaded diseases: { {k: v for k, v in sorted(disease_counts.items())} }")

    # Score all diseases with cases_total > 0 (not just COVID)
    scored = []
    for r in records:
        if r.get("cases_total", 0) > 0:
            cases_today = r.get("cases_today", 0) or 0
            cases_total = r.get("cases_total", 1) or 1
            # For WHO annual data cases_today=0 so use fraction of total as proxy
            prior_est = max(1, cases_today if cases_today > 0 else int(cases_total / 90))
            today_est = max(1, cases_today if cases_today > 0 else int(cases_total / 88))

            rt_result = estimate_rt(today_est, prior_est)
            vel_result = calc_velocity(today_est, prior_est)
            score_result = calc_outbreak_score(
                rt=rt_result.get("rt"),
                case_velocity=max(vel_result.get("velocity", 0), 0),
                climate_index=0,
            )
            scored.append({
                "country": r["country"],
                "disease": r["disease"],
                "score": score_result["score"],
                "level": score_result["level"],
                "rt": rt_result.get("rt") or 0,
                "velocity": vel_result.get("velocity", 0),
            })

    upsert_records(records)
    upsert_scores(scored)
    upsert_alerts(raw.get("promed_alerts", []))
    save_parquet_snapshot(records)

    covid_countries = query_all_countries_map("COVID-19")
    top_countries = query_top_countries("COVID-19", 20)
    alerts = query_alerts()
    scores = query_scores()

    global_threat = calc_global_threat(scores)

    # What changed — ALL diseases with cases_today > 0, not just COVID
    active_records = [r for r in records if r.get("cases_today", 0) > 0]
    # Fallback: include all COVID records if no other today data
    if not active_records:
        active_records = [r for r in records if r.get("disease") == "COVID-19"]
    what_changed = build_what_changed(active_records)

    confidence = calc_confidence()

    return {
        "covid_map": covid_countries,
        "top_countries": top_countries,
        "alerts": alerts,
        "scores": scores,
        "global_threat": global_threat,
        "what_changed": what_changed,
        "confidence": confidence,
        "climate_bangkok": raw.get("climate_bangkok", {}),
        "climate_delhi": raw.get("climate_delhi", {}),
        "promed_alerts": raw.get("promed_alerts", []),
        "gbif_vectors": raw.get("gbif_vectors", []),
        "fetched_at": raw.get("fetched_at", ""),
        "records": records,
    }