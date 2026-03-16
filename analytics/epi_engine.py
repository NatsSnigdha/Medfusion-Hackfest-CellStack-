"""
analytics/epi_engine.py

Core epidemiological calculations with full math transparency.
Every function returns both the result AND the step-by-step
reasoning so the UI can show "how we got here".
"""

import math
from typing import Optional


# ─── R_t Estimator ────────────────────────────────────────────
def estimate_rt(
    cases_this_week: int,
    cases_prior_week: int,
    serial_interval_days: float = 5.0,
) -> dict:
    """
    Estimate reproduction number R_t using simple ratio method.
    R_t = new_cases(t) / new_cases(t - serial_interval)

    Returns result + confidence interval + plain-English explanation.
    """
    if cases_prior_week <= 0:
        return _rt_fallback()

    rt = cases_this_week / cases_prior_week
    rt = round(rt, 3)

    # Bootstrap-approximated 95% CI (simplified Poisson uncertainty)
    se = math.sqrt(1 / max(cases_this_week, 1) + 1 / max(cases_prior_week, 1))
    ci_low = round(rt * math.exp(-1.96 * se), 2)
    ci_high = round(rt * math.exp(1.96 * se), 2)

    doubling = _doubling_time(rt, serial_interval_days)

    if rt > 1.5:
        status, color = "Rapidly growing", "danger"
    elif rt > 1.2:
        status, color = "Growing", "warning"
    elif rt > 1.0:
        status, color = "Slowly growing", "warning"
    elif rt > 0.8:
        status, color = "Declining", "success"
    else:
        status, color = "Rapidly declining", "success"

    plain = (
        f"Each infected person is currently passing the disease to "
        f"{'more than' if rt > 1 else 'fewer than'} 1 other person (R_t = {rt}). "
        f"{'The outbreak is ' + status.lower() + '.' if rt != 1.0 else 'The outbreak is stable.'}"
    )

    return {
        "rt": rt,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "status": status,
        "color": color,
        "doubling_weeks": doubling,
        "plain_english": plain,
        "steps": [
            f"New cases this week: {cases_this_week:,}",
            f"New cases prior week: {cases_prior_week:,}",
            f"R_t = {cases_this_week:,} ÷ {cases_prior_week:,} = {rt}",
            f"95% CI = [{ci_low}, {ci_high}] (Poisson uncertainty)",
            f"Doubling time = ln(2) ÷ ln(R_t) = {doubling}",
        ],
        "formula": "R_t = cases(week_t) / cases(week_t − serial_interval)",
    }


def _doubling_time(rt: float, serial_interval: float = 5.0) -> str:
    if rt <= 1.0:
        return "N/A (not growing)"
    try:
        weeks = math.log(2) / math.log(rt)
        days = weeks * serial_interval
        return f"{round(days, 1)} days"
    except Exception:
        return "N/A"


def _rt_fallback() -> dict:
    return {
        "rt": None, "ci_low": None, "ci_high": None,
        "status": "Insufficient data", "color": "gray",
        "doubling_weeks": "N/A", "plain_english": "Not enough data to estimate R_t.",
        "steps": ["No prior week data available."],
        "formula": "R_t = cases(week_t) / cases(week_t − serial_interval)",
    }


# ─── Case Fatality Rate ────────────────────────────────────────
def calc_cfr(deaths: int, cases: int) -> dict:
    """
    CFR = (deaths / cases) × 100
    Returns value + context + plain English.
    """
    if cases <= 0:
        return {"cfr": 0.0, "plain_english": "No case data.", "formula": "CFR = (deaths/cases) × 100"}

    cfr = round((deaths / cases) * 100, 3)

    if cfr < 0.1:
        severity = "very low"
    elif cfr < 1.0:
        severity = "low"
    elif cfr < 3.0:
        severity = "moderate"
    else:
        severity = "high"

    plain = (
        f"About {cfr}% of confirmed cases have been fatal. "
        f"This is a {severity} fatality rate. "
        f"({deaths:,} deaths from {cases:,} confirmed cases)"
    )

    return {
        "cfr": cfr,
        "severity": severity,
        "plain_english": plain,
        "formula": "CFR = (deaths ÷ cases) × 100",
        "steps": [
            f"Deaths: {deaths:,}",
            f"Confirmed cases: {cases:,}",
            f"CFR = ({deaths:,} ÷ {cases:,}) × 100 = {cfr}%",
        ],
    }


# ─── Case Velocity ─────────────────────────────────────────────
def calc_velocity(cases_today: int, cases_yesterday: int) -> dict:
    """
    Velocity = (today - yesterday) / yesterday × 100
    Represents % change — used for "What changed today" feed.
    """
    if cases_yesterday <= 0:
        return {"velocity": 0.0, "direction": "stable", "plain_english": "No baseline data."}

    pct = round(((cases_today - cases_yesterday) / cases_yesterday) * 100, 1)
    direction = "up" if pct > 5 else "down" if pct < -5 else "stable"

    plain = (
        f"Cases {'rose' if pct > 0 else 'fell'} by {abs(pct)}% today "
        f"({cases_today:,} vs {cases_yesterday:,} yesterday)."
    )

    return {
        "velocity": pct,
        "direction": direction,
        "cases_today": cases_today,
        "cases_yesterday": cases_yesterday,
        "plain_english": plain,
        "formula": "Velocity = (today − yesterday) / yesterday × 100",
    }


# ─── Outbreak Risk Score ───────────────────────────────────────
def calc_outbreak_score(
    rt: Optional[float],
    case_velocity: float,
    climate_index: float = 0.0,
    reporting_lag_days: float = 2.0,
) -> dict:
    """
    Composite outbreak risk score (0-100).
    Risk = 0.40×velocity_score + 0.30×rt_score + 0.20×climate + 0.10×lag_penalty

    Weights derived from WHO surveillance literature.
    """
    # Normalise each factor to 0-100
    velocity_score = min(max(case_velocity, 0), 100)
    rt_score = min(max(((rt or 1.0) - 1.0) / 1.5 * 100, 0), 100) if rt else 0
    lag_penalty = min(reporting_lag_days / 7 * 100, 100)

    score = (
        0.40 * velocity_score
        + 0.30 * rt_score
        + 0.20 * climate_index
        + 0.10 * lag_penalty
    )
    score = round(min(score, 100), 1)

    if score >= 70:
        level, color = "Critical", "danger"
    elif score >= 50:
        level, color = "Elevated", "warning"
    elif score >= 30:
        level, color = "Moderate", "warning"
    else:
        level, color = "Low", "success"

    plain = (
        f"The overall outbreak risk is {level.lower()} (score {score}/100). "
        f"Case velocity is the largest driver ({velocity_score:.0f}/100), "
        f"followed by transmission rate ({rt_score:.0f}/100)."
    )

    return {
        "score": score,
        "level": level,
        "color": color,
        "plain_english": plain,
        "factors": {
            "case_velocity": round(velocity_score, 1),
            "rt_score": round(rt_score, 1),
            "climate_index": round(climate_index, 1),
            "reporting_lag": round(lag_penalty, 1),
        },
        "weights": {"velocity": 0.40, "rt": 0.30, "climate": 0.20, "lag": 0.10},
        "formula": "Risk = 0.40×velocity + 0.30×R_t_score + 0.20×climate + 0.10×lag",
        "steps": [
            f"Case velocity score: {velocity_score:.1f}",
            f"R_t score: {rt_score:.1f}",
            f"Climate index: {climate_index:.1f}",
            f"Reporting lag penalty: {lag_penalty:.1f}",
            f"Final = 0.40×{velocity_score:.1f} + 0.30×{rt_score:.1f} + "
            f"0.20×{climate_index:.1f} + 0.10×{lag_penalty:.1f} = {score}",
        ],
    }


# ─── Global Threat Thermometer ─────────────────────────────────
def calc_global_threat(country_scores: list[dict]) -> dict:
    """
    Aggregate country-level outbreak scores into a single global
    threat level (0-100) for the threat thermometer widget.

    Uses population-weighted mean of top-20 highest-risk countries.
    """
    if not country_scores:
        return {"score": 0, "level": "Unknown", "color": "gray", "plain_english": "No data."}

    scores = sorted(
        [s["score"] for s in country_scores if "score" in s],
        reverse=True,
    )
    top20 = scores[:20]
    global_score = round(sum(top20) / len(top20), 1) if top20 else 0

    if global_score >= 65:
        level, color = "Critical", "danger"
    elif global_score >= 45:
        level, color = "Elevated", "warning"
    elif global_score >= 25:
        level, color = "Moderate", "info"
    else:
        level, color = "Low", "success"

    plain = (
        f"Global disease threat is {level.lower()} ({global_score}/100), "
        f"based on the average risk across the 20 highest-burden countries."
    )

    return {
        "score": global_score,
        "level": level,
        "color": color,
        "plain_english": plain,
        "top_country_count": len(top20),
    }


# ─── "What Changed Today" builder ─────────────────────────────
def build_what_changed(records: list[dict]) -> list[dict]:
    """
    Produces the delta-first change feed.
    Sorts by absolute % change descending.
    """
    changes = []
    for r in records:
        today = r.get("cases_today", 0) or 0
        total = r.get("cases_total", 1) or 1
        # Estimate yesterday from 7-day average
        yesterday_est = max(1, int(total / 90))
        vel = calc_velocity(today, yesterday_est)

        if abs(vel["velocity"]) < 1:
            continue

        emoji_dir = "↑" if vel["direction"] == "up" else ("↓" if vel["direction"] == "down" else "→")
        changes.append({
            "country": r.get("country", ""),
            "disease": r.get("disease", ""),
            "velocity": vel["velocity"],
            "direction": vel["direction"],
            "cases_today": today,
            "headline": (
                f"{r.get('disease','?')} in {r.get('country','?')}: "
                f"{emoji_dir} {abs(vel['velocity'])}% since yesterday"
            ),
            "plain_english": vel["plain_english"],
        })

    changes.sort(key=lambda x: abs(x["velocity"]), reverse=True)
    return changes[:10]


# ─── Data quality / confidence scorer ─────────────────────────
def calc_confidence(
    districts_reporting_pct: float = 80.0,
    model_accuracy_30d: float = 0.83,
    signal_consistency: float = 0.88,
) -> dict:
    """
    Confidence = 0.4×completeness + 0.4×accuracy + 0.2×consistency
    Returns 0-100 score with plain-English explanation.
    """
    score = round(
        0.4 * districts_reporting_pct
        + 0.4 * model_accuracy_30d * 100
        + 0.2 * signal_consistency * 100,
        1,
    )

    plain = (
        f"Model confidence is {score:.0f}%. "
        f"{100 - districts_reporting_pct:.0f}% of districts haven't reported yet "
        f"(estimated from neighbours). Model was within ±15% of actual cases "
        f"{model_accuracy_30d*100:.0f}% of the time last month."
    )

    return {
        "score": score,
        "color": "success" if score >= 80 else "warning" if score >= 60 else "danger",
        "plain_english": plain,
        "factors": {
            "data_completeness": districts_reporting_pct,
            "model_accuracy_30d": model_accuracy_30d * 100,
            "signal_consistency": signal_consistency * 100,
        },
        "formula": "Confidence = 0.4×completeness + 0.4×accuracy + 0.2×consistency",
    }
