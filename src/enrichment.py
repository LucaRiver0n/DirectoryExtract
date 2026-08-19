from __future__ import annotations

import re
from collections import deque
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import CompanyRecord, clean_text, normalize_phone


EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s().-]*)?(?:\(?\d{2,4}\)?[\s.-]*){2,4}\d{2,4}"
)

SEARCH_URL = "https://html.duckduckgo.com/html/"

SOCIAL_OR_DIRECTORY = (
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "directoriodecarga.com", "yelp.", "tripadvisor.",
    "zoominfo.com", "crunchbase.com", "dnb.com", "kompass.com", "bloomberg.com",
)


def _unwrap_ddg_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and "uddg" in parse_qs(parsed.query):
        return unquote(parse_qs(parsed.query)["uddg"][0])
    return href


def search_web(session: requests.Session, query: str, limit: int = 8) -> list[str]:
    """Búsqueda HTML opcional. Puede fallar o limitarse según la red/servicio."""
    try:
        response = session.get(
            SEARCH_URL,
            params={"q": query},
            timeout=20,
            headers={"Referer": "https://duckduckgo.com/"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "lxml")
    results: list[str] = []
    selectors = ["a.result__a", "a[data-testid='result-title-a']"]
    anchors = []
    for selector in selectors:
        anchors.extend(soup.select(selector))
    if not anchors:
        anchors = soup.find_all("a", href=True)

    for a in anchors:
        url = _unwrap_ddg_url(a.get("href", ""))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if url not in results:
            results.append(url)
        if len(results) >= limit:
            break
    return results


def find_official_website(session: requests.Session, record: CompanyRecord) -> str:
    location = " ".join(x for x in [record.ciudad, record.estado, record.pais] if x)
    query = f'"{record.nombre_empresa}" {location} sitio web oficial'
    for url in search_web(session, query):
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if any(blocked in host for blocked in SOCIAL_OR_DIRECTORY):
            continue
        if host:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}/"
    return ""


def find_linkedin(session: requests.Session, record: CompanyRecord) -> str:
    query = f'site:linkedin.com/company "{record.nombre_empresa}" {record.pais}'
    for url in search_web(session, query):
        parsed = urlparse(url)
        if "linkedin.com" in parsed.netloc.lower() and "/company/" in parsed.path.lower():
            return url.split("?", 1)[0]
    return ""


def _valid_email(email: str) -> bool:
    low = email.lower()
    bad_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
    if low.endswith(bad_suffixes):
        return False
    return not any(x in low for x in ["example.com", "sentry.io", "wixpress.com"])


def _extract_contacts(html: str, page_url: str) -> tuple[list[str], list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    emails = []
    for email in EMAIL_RE.findall(html + " " + text):
        email = email.strip(".,;:()[]<>\"'").lower()
        if _valid_email(email) and email not in emails:
            emails.append(email)

    phones: list[str] = []
    for match in PHONE_RE.findall(text):
        phone = clean_text(match)
        digits = re.sub(r"\D", "", phone)
        if not (8 <= len(digits) <= 16):
            continue
        # Evitar años, códigos postales y secuencias típicamente no telefónicas.
        if len(digits) == 8 and digits.startswith(("19", "20")):
            continue
        if normalize_phone(phone) and normalize_phone(phone) not in [normalize_phone(x) for x in phones]:
            phones.append(phone)

    linkedin: list[str] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a.get("href", ""))
        p = urlparse(href)
        if "linkedin.com" in p.netloc.lower() and "/company/" in p.path.lower():
            clean = href.split("?", 1)[0]
            if clean not in linkedin:
                linkedin.append(clean)
    return emails, phones, linkedin


def enrich_from_website(session: requests.Session, record: CompanyRecord, max_pages: int = 5) -> None:
    if not record.sitio_web:
        return
    root = record.sitio_web
    root_host = urlparse(root).netloc.lower().removeprefix("www.")
    if not root_host:
        return

    queue = deque([root])
    visited: set[str] = set()
    candidates: list[str] = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            response = session.get(url, timeout=15, allow_redirects=True)
            if response.status_code >= 400 or "text/html" not in response.headers.get("Content-Type", "text/html"):
                continue
        except requests.RequestException:
            continue

        emails, phones, linkedin = _extract_contacts(response.text, response.url)
        if not record.correo and emails:
            record.add_email(emails[0])
            record.fuente_correo = "Sitio web"
        for phone in phones:
            before = (record.telefono_1, record.telefono_2)
            record.add_phone(phone)
            if before != (record.telefono_1, record.telefono_2) and not record.fuente_telefono:
                record.fuente_telefono = "Sitio web"
            if record.telefono_1 and record.telefono_2:
                break
        if not record.linkedin and linkedin:
            record.linkedin = linkedin[0]
            record.fuente_linkedin = "Sitio web"

        soup = BeautifulSoup(response.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = urljoin(response.url, a.get("href", ""))
            parsed = urlparse(href)
            host = parsed.netloc.lower().removeprefix("www.")
            if host != root_host or href in visited:
                continue
            haystack = (a.get_text(" ", strip=True) + " " + parsed.path).casefold()
            if any(token in haystack for token in ["contact", "contacto", "nosotros", "about", "empresa", "ubicacion", "location"]):
                candidates.append(href.split("#", 1)[0])

        for candidate in candidates:
            if candidate not in visited and candidate not in queue:
                queue.append(candidate)

        if record.correo and record.telefono_1 and record.telefono_2 and record.linkedin:
            break


def enrich_record(
    session: requests.Session,
    record: CompanyRecord,
    *,
    find_site: bool,
    crawl_site: bool,
    find_linkedin_search: bool,
) -> CompanyRecord:
    if record.estado_extraccion != "OK":
        return record

    if find_site and not record.sitio_web:
        record.sitio_web = find_official_website(session, record)
        if record.sitio_web:
            record.fuente_sitio_web = "Búsqueda web"

    if crawl_site and record.sitio_web:
        enrich_from_website(session, record)

    if find_linkedin_search and not record.linkedin:
        record.linkedin = find_linkedin(session, record)
        if record.linkedin:
            record.fuente_linkedin = "Búsqueda web"
    return record
