"""Optional standalone contract for date-bounded, per-platform source discovery."""
from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse, urlunparse

SCHEMA_VERSION = "1.0"
PLATFORM_STATUSES = {"covered", "partial", "blocked", "unavailable"}
DATE_PROVENANCES = {"observed", "estimated", "unavailable"}
ACCESS_STATUSES = {"accessible", "blocked", "rate_limited", "paywalled", "login_required"}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _parse_iso_date(value: str, field: str) -> date:
    text = _norm(value)
    if not text:
        raise ValueError(f"{field} is required")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"invalid ISO date for {field}: {value}") from exc


def _canonicalize_url(url: str) -> str:
    text = _norm(url)
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid source URL: {url}")
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def build_discovery_packet(
    *,
    question: str,
    date_start: str,
    date_end: str,
    platforms: list[str],
    budget: dict[str, Any],
    platform_coverage: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    stop_conditions: list[str] | None = None,
) -> dict[str, Any]:
    """Build and validate a bounded, offline source-discovery packet."""
    q = _norm(question)
    if not q:
        raise ValueError("research question is required")
    start_d = _parse_iso_date(date_start, "date_start")
    end_d = _parse_iso_date(date_end, "date_end")
    if start_d > end_d:
        raise ValueError("date_start must not be after date_end")

    req_platforms = [_norm(p).lower() for p in platforms if _norm(p)]
    if not req_platforms:
        raise ValueError("at least one platform is required")
    req_platforms = list(dict.fromkeys(req_platforms))

    if not isinstance(budget, dict):
        raise ValueError("budget dict is required")
    max_items = int(budget.get("max_items", 0))
    max_requests = int(budget.get("max_requests_per_platform", 0))
    max_cost = float(budget.get("max_cost_usd", 0.0))
    if max_items <= 0 or max_requests <= 0 or max_cost < 0.0:
        raise ValueError("budget requires positive max_items, positive max_requests_per_platform, and non-negative max_cost_usd")

    cov_by_platform: dict[str, dict[str, Any]] = {}
    for entry in platform_coverage:
        plat = _norm(entry.get("platform")).lower()
        status = _norm(entry.get("status")).lower()
        if plat not in req_platforms:
            raise ValueError(f"coverage entry references unrequested platform: {plat}")
        if status not in PLATFORM_STATUSES:
            raise ValueError(f"invalid platform coverage status: {status}")
        reason = _norm(entry.get("reason"))
        if status != "covered" and not reason:
            raise ValueError(f"reason required for non-covered platform {plat} ({status})")
        cov_window = entry.get("covered_window")
        if cov_window is not None:
            c_start = _parse_iso_date(cov_window.get("start", ""), f"{plat}.covered_window.start")
            c_end = _parse_iso_date(cov_window.get("end", ""), f"{plat}.covered_window.end")
            if c_start > c_end:
                raise ValueError(f"invalid covered_window for {plat}")
            norm_window = {"start": c_start.isoformat(), "end": c_end.isoformat()}
        else:
            norm_window = None
        cov_by_platform[plat] = {
            "platform": plat,
            "status": status,
            "requested_window": {"start": start_d.isoformat(), "end": end_d.isoformat()},
            "covered_window": norm_window,
            "reason": reason or None,
            "stop_condition": _norm(entry.get("stop_condition")) or None,
        }

    missing_platforms = [p for p in req_platforms if p not in cov_by_platform]
    if missing_platforms:
        raise ValueError(f"missing platform_coverage entries for: {', '.join(missing_platforms)}")

    deduped: list[dict[str, Any]] = []
    by_canonical: dict[str, dict[str, Any]] = {}
    duplicates_collapsed = 0
    unverified_claims: list[dict[str, Any]] = []
    all_stops = list(stop_conditions or [])

    for raw in sources:
        plat = _norm(raw.get("platform")).lower()
        if plat not in req_platforms:
            raise ValueError(f"source references unrequested platform: {plat}")
        orig_url = _norm(raw.get("original_url") or raw.get("url"))
        canon_url = _canonicalize_url(_norm(raw.get("canonical_url") or orig_url))
        orig_checked = _canonicalize_url(orig_url)
        access = _norm(raw.get("access_status") or "accessible").lower()
        if access not in ACCESS_STATUSES:
            raise ValueError(f"invalid access_status: {access}")
        access_reason = _norm(raw.get("access_limit_reason"))
        if access != "accessible" and not access_reason:
            raise ValueError(f"access_limit_reason required for {canon_url} ({access})")

        pub_prov = _norm(raw.get("published_at_provenance") or "unavailable").lower()
        if pub_prov not in DATE_PROVENANCES:
            raise ValueError(f"invalid published_at_provenance: {pub_prov}")
        pub_at = _norm(raw.get("published_at")) or None
        if pub_prov in {"observed", "estimated"} and not pub_at:
            raise ValueError(f"published_at required when provenance is {pub_prov}")
        if pub_at:
            _parse_iso_date(pub_at, "published_at")
        ret_at = _norm(raw.get("retrieved_at")) or None
        if ret_at:
            _parse_iso_date(ret_at, "retrieved_at")

        claims_norm: list[dict[str, Any]] = []
        for c in raw.get("claims") or []:
            if isinstance(c, str):
                c_text, c_ver = _norm(c), False
            else:
                c_text, c_ver = _norm(c.get("text")), bool(c.get("verified", False))
            if not c_text:
                continue
            claims_norm.append({"text": c_text, "verified": c_ver})
            if not c_ver:
                unverified_claims.append({"canonical_url": canon_url, "claim": c_text})

        if canon_url in by_canonical:
            duplicates_collapsed += 1
            existing = by_canonical[canon_url]
            if orig_checked not in existing["duplicate_urls"]:
                existing["duplicate_urls"].append(orig_checked)
            continue

        if len(deduped) >= max_items:
            if "budget_max_items_reached" not in all_stops:
                all_stops.append("budget_max_items_reached")
            break

        entry = {
            "source_id": _norm(raw.get("source_id")) or f"src-{len(deduped) + 1}",
            "platform": plat,
            "original_url": orig_checked,
            "canonical_url": canon_url,
            "duplicate_urls": [],
            "related_topic": _norm(raw.get("related_topic")) or None,
            "published_at": pub_at,
            "published_at_provenance": pub_prov,
            "retrieved_at": ret_at,
            "access_status": access,
            "access_limit_reason": access_reason or None,
            "claims": claims_norm,
        }
        by_canonical[canon_url] = entry
        deduped.append(entry)

    for cov in cov_by_platform.values():
        if cov["stop_condition"] and cov["stop_condition"] not in all_stops:
            all_stops.append(cov["stop_condition"])

    full_coverage = all(
        c["status"] == "covered"
        and c["covered_window"] == {"start": start_d.isoformat(), "end": end_d.isoformat()}
        for c in cov_by_platform.values()
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "question": q,
        "date_window": {"start": start_d.isoformat(), "end": end_d.isoformat()},
        "platforms": req_platforms,
        "budget": {
            "max_items": max_items,
            "max_requests_per_platform": max_requests,
            "max_cost_usd": max_cost,
        },
        "full_coverage": full_coverage,
        "platform_coverage": [cov_by_platform[p] for p in req_platforms],
        "sources": deduped,
        "duplicates_collapsed": duplicates_collapsed,
        "unverified_claims": unverified_claims,
        "stop_conditions": all_stops,
        "side_effects": {
            "credentials_required": False,
            "paid_apis_enabled": False,
            "automatic_media_processing": False,
        },
    }
