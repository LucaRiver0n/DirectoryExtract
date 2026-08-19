from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from .directorio import (
    ListingCompany,
    discover_company_urls as discover_ddc_urls,
    fetch_company_record as fetch_ddc_record,
    validate_segment_url as validate_ddc_url,
)
from .generic_directory import (
    GenericListingCompany,
    analyze_directory_compatibility,
    discover_company_urls_generic,
    fetch_company_record_generic,
    validate_directory_url,
)


@dataclass(frozen=True)
class SourceProfile:
    engine: str
    label: str
    optimized: bool


def source_profile(url: str) -> SourceProfile:
    host = urlparse(url if "://" in url else f"https://{url}").netloc.casefold()
    if "directoriodecarga.com" in host:
        return SourceProfile("directoriodecarga", "Motor optimizado · Directorio de Carga", True)
    return SourceProfile("universal", "Motor universal · Detección automática", False)


def validate_source_url(url: str) -> str:
    profile = source_profile(url)
    if profile.engine == "directoriodecarga":
        return validate_ddc_url(url)
    return validate_directory_url(url)


def analyze_source(
    session: requests.Session,
    url: str,
    *,
    company_selector: str = "",
) -> dict:
    profile = source_profile(url)
    clean = validate_source_url(url)
    if profile.optimized:
        return {
            "level": "Optimizada",
            "score": 100,
            "companies_on_page": None,
            "pagination_detected": True,
            "host": urlparse(clean).netloc,
            "final_url": clean,
            "engine": profile.label,
        }
    result = analyze_directory_compatibility(session, clean, company_selector=company_selector)
    result["engine"] = profile.label
    return result


def discover_companies(
    session: requests.Session,
    url: str,
    *,
    max_records: int = 0,
    delay_seconds: float = 0.0,
    progress=None,
    company_selector: str = "",
    next_selector: str = "",
):
    profile = source_profile(url)
    clean = validate_source_url(url)
    if profile.engine == "directoriodecarga":
        return profile, discover_ddc_urls(
            session,
            clean,
            max_records=max_records,
            delay_seconds=delay_seconds,
            progress=progress,
        )
    return profile, discover_company_urls_generic(
        session,
        clean,
        max_records=max_records,
        delay_seconds=delay_seconds,
        progress=progress,
        company_selector=company_selector,
        next_selector=next_selector,
    )


def fetch_company(
    session: requests.Session,
    profile: SourceProfile,
    company: ListingCompany | GenericListingCompany,
    segmento: str,
    *,
    delay_seconds: float = 0.0,
):
    if profile.engine == "directoriodecarga":
        return fetch_ddc_record(session, company, segmento, delay_seconds=delay_seconds)
    return fetch_company_record_generic(session, company, segmento, delay_seconds=delay_seconds)
