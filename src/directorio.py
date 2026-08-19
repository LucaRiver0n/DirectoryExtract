from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .http_client import get
from .models import CompanyRecord, clean_text


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ListingCompany:
    url: str
    listing_text: str = ""


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _same_directory_host(url: str) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host in {"directoriodecarga.com", "www.directoriodecarga.com", ""}


def validate_segment_url(url: str) -> str:
    url = clean_text(url)
    if not url:
        raise ValueError("Ingresá la URL del segmento.")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("La URL debe comenzar con http:// o https://")
    if "directoriodecarga.com" not in parsed.netloc.lower():
        raise ValueError("Esta primera versión está preparada para directoriodecarga.com")
    return urlunparse(parsed._replace(fragment=""))


def add_page_number(url: str, page_number: int) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if page_number <= 1:
        qs.pop("page_listado", None)
    else:
        qs["page_listado"] = [str(page_number)]
    query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=query))


def parse_record_count(html: str) -> int | None:
    text = _soup(html).get_text(" ", strip=True)
    match = re.search(r"\b([\d.,]+)\s+registros\b", text, flags=re.I)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def parse_max_page(html: str) -> int:
    soup = _soup(html)
    pages = [1]
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        parsed = urlparse(href)
        values = parse_qs(parsed.query).get("page_listado", [])
        for value in values:
            if value.isdigit():
                pages.append(int(value))
    # Fallback: el sitio muestra normalmente 12 registros por página.
    count = parse_record_count(html)
    if count:
        pages.append(max(1, math.ceil(count / 12)))
    return max(pages)


def parse_listing_companies(html: str, page_url: str) -> list[ListingCompany]:
    soup = _soup(html)
    found: dict[str, ListingCompany] = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if not _same_directory_host(absolute):
            continue
        if not parsed.path.startswith("/empresas/"):
            continue
        text = clean_text(a.get_text(" ", strip=True))
        current = found.get(absolute)
        if current is None or len(text) > len(current.listing_text):
            found[absolute] = ListingCompany(url=absolute, listing_text=text)
    return list(found.values())


def discover_company_urls(
    session: requests.Session,
    segment_url: str,
    *,
    max_records: int = 0,
    delay_seconds: float = 0.0,
    progress: ProgressCallback | None = None,
) -> list[ListingCompany]:
    segment_url = validate_segment_url(segment_url)
    first_response = get(session, add_page_number(segment_url, 1), delay_seconds=delay_seconds)
    first_html = first_response.text
    max_page = parse_max_page(first_html)

    all_companies: dict[str, ListingCompany] = {}
    for page in range(1, max_page + 1):
        if progress:
            progress(f"Leyendo página {page} de {max_page} del segmento…")
        html = first_html if page == 1 else get(
            session, add_page_number(segment_url, page), delay_seconds=delay_seconds
        ).text
        for company in parse_listing_companies(html, segment_url):
            if company.url not in all_companies:
                all_companies[company.url] = company
                if max_records and len(all_companies) >= max_records:
                    return list(all_companies.values())
    return list(all_companies.values())


def _value_after_label(strings: list[str], labels: Iterable[str]) -> str:
    normalized_labels = {clean_text(x).casefold() for x in labels}
    for idx, item in enumerate(strings[:-1]):
        if clean_text(item).casefold() in normalized_labels:
            candidate = clean_text(strings[idx + 1])
            if candidate and candidate.casefold() not in normalized_labels:
                return candidate
    return ""


def _company_name(soup: BeautifulSoup, strings: list[str]) -> str:
    for img in soup.find_all("img", alt=True):
        alt = clean_text(img.get("alt"))
        if alt.casefold().startswith("logo de "):
            return clean_text(alt[8:])
    h1 = soup.find("h1")
    if h1:
        text = clean_text(h1.get_text(" ", strip=True))
        # El título observado tiene la forma "EMPRESA en Ciudad, País".
        parts = re.split(r"\s+en\s+", text, maxsplit=1, flags=re.I)
        return clean_text(parts[0])
    return strings[0] if strings else ""


def parse_detail_html(html: str, detail_url: str, segmento: str) -> tuple[CompanyRecord, list[str]]:
    soup = _soup(html)
    strings = [clean_text(s) for s in soup.stripped_strings if clean_text(s)]
    record = CompanyRecord(
        nombre_empresa=_company_name(soup, strings),
        direccion=_value_after_label(strings, ["Dirección"]),
        ciudad=_value_after_label(strings, ["Ciudad"]),
        estado=_value_after_label(strings, ["Estado/Provincia", "Estado", "Provincia"]),
        pais=_value_after_label(strings, ["País"]),
        segmento=segmento,
        url_fuente=detail_url,
    )

    connect_urls: list[str] = []
    external_candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = clean_text(a.get("href"))
        absolute = urljoin(detail_url, href)
        parsed = urlparse(absolute)
        if "/connect" in parsed.path and "sn=" in parsed.query:
            connect_urls.append(absolute)
            continue
        if parsed.scheme not in {"http", "https"}:
            continue
        host = parsed.netloc.lower()
        if "linkedin.com" in host:
            record.linkedin = absolute
            record.fuente_linkedin = "Directorio"
        elif not _same_directory_host(absolute):
            external_candidates.append(absolute)

    # Si la ficha trae una web externa, priorizarla excluyendo mapas, video y recursos.
    blocked = (
        "google.com", "googleapis.com", "gstatic.com", "youtube.com", "youtu.be",
        "facebook.com", "instagram.com", "x.com", "twitter.com", "flagcdn.com",
    )
    for candidate in external_candidates:
        host = urlparse(candidate).netloc.lower()
        if not any(x in host for x in blocked):
            record.sitio_web = candidate
            record.fuente_sitio_web = "Directorio"
            break

    return record, list(dict.fromkeys(connect_urls))


def resolve_connect_value(
    session: requests.Session,
    connect_url: str,
    *,
    detail_url: str,
    delay_seconds: float = 0.0,
) -> tuple[str, str]:
    try:
        # Estos endpoints redirigen a tel:, mailto: o WhatsApp.
        response = session.get(
            connect_url,
            timeout=20,
            allow_redirects=False,
            headers={"Referer": detail_url},
        )
    except requests.RequestException:
        return "", ""

    location = response.headers.get("Location", "")
    if not location:
        return "", ""

    low = location.lower()
    if low.startswith("mailto:"):
        value = location.split(":", 1)[1].split("?", 1)[0]
        return "email", clean_text(value)
    if low.startswith("tel:"):
        return "phone", clean_text(location.split(":", 1)[1])
    if "wa.me/" in low or "whatsapp" in low:
        digits = re.sub(r"\D", "", location)
        return "phone", f"+{digits}" if digits else ""
    return "", ""


def fetch_company_record(
    session: requests.Session,
    company: ListingCompany,
    segmento: str,
    *,
    delay_seconds: float = 0.0,
) -> CompanyRecord:
    try:
        response = get(session, company.url, delay_seconds=delay_seconds)
        record, connect_urls = parse_detail_html(response.text, company.url, segmento)
        if not record.nombre_empresa:
            record.nombre_empresa = company.listing_text

        for connect_url in connect_urls:
            kind, value = resolve_connect_value(
                session, connect_url, detail_url=company.url, delay_seconds=delay_seconds
            )
            if kind == "email" and value:
                record.add_email(value)
                record.fuente_correo = "Directorio"
            elif kind == "phone" and value:
                before = (record.telefono_1, record.telefono_2)
                record.add_phone(value)
                if before != (record.telefono_1, record.telefono_2):
                    record.fuente_telefono = "Directorio"
        return record
    except Exception as exc:
        return CompanyRecord(
            nombre_empresa=company.listing_text,
            segmento=segmento,
            url_fuente=company.url,
            estado_extraccion="ERROR",
            observaciones=f"{type(exc).__name__}: {exc}",
        )
