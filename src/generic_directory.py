from __future__ import annotations

import json
import re
from collections import Counter, deque
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

from .http_client import get
from .models import CompanyRecord, clean_text


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class GenericListingCompany:
    url: str
    listing_text: str = ""


COMPANY_HINTS = {
    "empresa", "empresas", "company", "companies", "business", "businesses",
    "member", "members", "profile", "profiles", "proveedor", "proveedores",
    "supplier", "suppliers", "vendor", "vendors", "ficha", "detalle", "detail",
    "organization", "organizacion", "listing", "directory-entry", "partner",
}

BLOCKED_PATH_TOKENS = {
    "login", "signin", "signup", "register", "registro", "contact", "contacto",
    "about", "nosotros", "privacy", "privacidad", "terms", "terminos", "cookies",
    "blog", "news", "noticias", "faq", "help", "ayuda", "search", "buscar",
    "category", "categoria", "tag", "author", "feed", "wp-content", "wp-admin",
    "cart", "checkout", "account", "mi-cuenta", "events", "eventos",
}

BLOCKED_TEXT = {
    "inicio", "home", "contacto", "contact", "nosotros", "about", "blog", "noticias",
    "news", "ver más", "leer más", "read more", "siguiente", "anterior", "next",
    "previous", "prev", "registrarse", "iniciar sesión", "login", "menu", "menú",
}

BLOCKED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".zip", ".doc",
    ".docx", ".xls", ".xlsx", ".css", ".js", ".xml", ".rss", ".ico",
)

SOCIAL_HOSTS = (
    "linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com",
    "youtube.com", "youtu.be", "tiktok.com", "wa.me", "whatsapp.com",
)

MAP_HOSTS = ("google.com", "maps.google", "goo.gl", "apple.com/maps", "bing.com/maps")

ORG_TYPES = {
    "organization", "corporation", "localbusiness", "professionalservice", "store",
    "travelagency", "automotivebusiness", "financialservice", "foodestablishment",
    "medicalbusiness", "legalservice", "governmentorganization", "educationalorganization",
}

LABELS = {
    "direccion": {"dirección", "direccion", "address", "endereço", "endereco", "domicilio"},
    "ciudad": {"ciudad", "city", "localidad", "cidade", "municipio", "municipality"},
    "estado": {"estado", "estado/provincia", "provincia", "state", "region", "región", "province"},
    "pais": {"país", "pais", "country", "país/región", "country/region"},
    "correo": {"correo", "correo electrónico", "email", "e-mail", "mail"},
    "telefono": {"teléfono", "telefono", "phone", "telephone", "tel", "móvil", "movil", "celular"},
    "web": {"sitio web", "website", "web", "página web", "pagina web", "site"},
}


class GenericDirectoryError(RuntimeError):
    pass


def validate_directory_url(url: str) -> str:
    url = clean_text(url)
    if not url:
        raise ValueError("Ingresá la URL del directorio o segmento.")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Ingresá una URL web válida (http:// o https://).")
    return urlunparse(parsed._replace(fragment=""))


def _same_host(url: str, base_url: str) -> bool:
    a = urlparse(url).netloc.lower().removeprefix("www.")
    b = urlparse(base_url).netloc.lower().removeprefix("www.")
    return bool(a and b and a == b)


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def _looks_like_asset(url: str) -> bool:
    low = urlparse(url).path.lower()
    return low.endswith(BLOCKED_EXTENSIONS)


def _anchor_text(anchor: Tag) -> str:
    text = clean_text(anchor.get_text(" ", strip=True))
    if text:
        return text
    img = anchor.find("img", alt=True)
    return clean_text(img.get("alt", "")) if img else ""


def _has_card_ancestor(anchor: Tag) -> bool:
    node = anchor.parent
    hops = 0
    while isinstance(node, Tag) and hops < 4:
        classes = " ".join(node.get("class", [])).casefold()
        node_id = clean_text(node.get("id", "")).casefold()
        haystack = f"{classes} {node_id}"
        if any(token in haystack for token in [
            "company", "empresa", "business", "member", "supplier", "vendor", "profile",
            "result", "listing", "directory", "card", "item", "entry", "partner",
        ]):
            return True
        node = node.parent
        hops += 1
    return False


def _path_signature(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "/"
    normalized = []
    for part in parts:
        if part.isdigit():
            normalized.append("{id}")
        elif re.fullmatch(r"[0-9a-f]{8,}", part, re.I):
            normalized.append("{id}")
        else:
            normalized.append(part)
    if len(normalized) >= 2:
        normalized[-1] = "{slug}"
    return "/" + "/".join(normalized)


def _score_company_anchor(anchor: Tag, absolute: str, page_url: str) -> int:
    parsed = urlparse(absolute)
    path = parsed.path.casefold()
    text = _anchor_text(anchor)
    low_text = text.casefold()

    if not _same_host(absolute, page_url) or _looks_like_asset(absolute):
        return -100
    if _clean_url(absolute).rstrip("/") == _clean_url(page_url).rstrip("/"):
        return -100
    if any(f"/{token}" in path or path.endswith(f"/{token}") for token in BLOCKED_PATH_TOKENS):
        return -20
    if low_text in BLOCKED_TEXT:
        return -20

    score = 0
    segments = [p for p in parsed.path.split("/") if p]
    current_segments = [p for p in urlparse(page_url).path.split("/") if p]
    if len(segments) >= 2:
        score += 2
    if len(segments) > len(current_segments):
        score += 1
    if any(token in path for token in COMPANY_HINTS):
        score += 5
    if _has_card_ancestor(anchor):
        score += 3
    if 2 <= len(text) <= 120 and not text.isdigit():
        score += 2
    if any(ch.isalpha() for ch in text):
        score += 1
    if anchor.find("img"):
        score += 1
    if parsed.query:
        if any(k in parsed.query.casefold() for k in ["id=", "company=", "empresa=", "member=", "profile="]):
            score += 2
    return score


def _select_manual_companies(soup: BeautifulSoup, page_url: str, selector: str) -> list[GenericListingCompany]:
    found: dict[str, GenericListingCompany] = {}
    for node in soup.select(selector):
        anchor = node if node.name == "a" else node.find("a", href=True)
        if not anchor or not anchor.get("href"):
            continue
        absolute = _clean_url(urljoin(page_url, anchor.get("href")))
        if not _same_host(absolute, page_url) or _looks_like_asset(absolute):
            continue
        text = _anchor_text(anchor) or clean_text(node.get_text(" ", strip=True))
        found.setdefault(absolute, GenericListingCompany(absolute, text))
    return list(found.values())


def parse_listing_companies_generic(
    html: str,
    page_url: str,
    *,
    company_selector: str = "",
) -> list[GenericListingCompany]:
    soup = BeautifulSoup(html, "lxml")
    if company_selector.strip():
        return _select_manual_companies(soup, page_url, company_selector.strip())

    scored: list[tuple[int, str, str, str]] = []
    for anchor in soup.find_all("a", href=True):
        absolute = _clean_url(urljoin(page_url, anchor.get("href", "")))
        score = _score_company_anchor(anchor, absolute, page_url)
        if score <= 0:
            continue
        scored.append((score, absolute, _anchor_text(anchor), _path_signature(urlparse(absolute).path)))

    if not scored:
        return []

    # Los directorios suelen repetir la misma estructura de URL para cada ficha.
    signature_counts = Counter(sig for score, url, text, sig in scored if score >= 2)
    common_signatures = {sig for sig, count in signature_counts.items() if count >= 2}

    found: dict[str, GenericListingCompany] = {}
    for score, absolute, text, signature in scored:
        effective_score = score + (3 if signature in common_signatures else 0)
        if effective_score < 5:
            continue
        previous = found.get(absolute)
        item = GenericListingCompany(absolute, text)
        if previous is None or len(item.listing_text) > len(previous.listing_text):
            found[absolute] = item

    # Si la heurística quedó demasiado estricta, conservar los mejores enlaces repetidos.
    if len(found) < 2 and common_signatures:
        best_sig = signature_counts.most_common(1)[0][0]
        for score, absolute, text, signature in scored:
            if signature == best_sig and score >= 2:
                found.setdefault(absolute, GenericListingCompany(absolute, text))

    return list(found.values())


def _pagination_candidates(soup: BeautifulSoup, page_url: str, next_selector: str = "") -> list[str]:
    candidates: list[tuple[int, str]] = []

    if next_selector.strip():
        for node in soup.select(next_selector.strip()):
            anchor = node if node.name == "a" else node.find("a", href=True)
            if anchor and anchor.get("href"):
                url = _clean_url(urljoin(page_url, anchor.get("href")))
                if _same_host(url, page_url):
                    candidates.append((100, url))
        return [url for _, url in candidates]

    for anchor in soup.find_all("a", href=True):
        absolute = _clean_url(urljoin(page_url, anchor.get("href", "")))
        if not _same_host(absolute, page_url) or _looks_like_asset(absolute):
            continue
        text = clean_text(anchor.get_text(" ", strip=True)).casefold()
        rel = " ".join(anchor.get("rel", [])).casefold()
        parent_classes = " ".join(anchor.parent.get("class", []) if isinstance(anchor.parent, Tag) else []).casefold()
        href_low = absolute.casefold()
        score = 0
        if "next" in rel:
            score += 100
        if text in {"next", "siguiente", "próximo", "proximo", "›", "»", ">", "→"}:
            score += 80
        if any(token in parent_classes for token in ["pagination", "pager", "paginacion", "paginación"]):
            score += 20
        if re.search(r"(?:[?&](?:page|pagina|p|pg)=\d+|/page/\d+/?$|/pagina/\d+/?$)", href_low):
            score += 12
        if score:
            candidates.append((score, absolute))

    ordered: list[str] = []
    for _, url in sorted(candidates, key=lambda x: x[0], reverse=True):
        if url not in ordered and url != _clean_url(page_url):
            ordered.append(url)
    return ordered


def discover_company_urls_generic(
    session: requests.Session,
    directory_url: str,
    *,
    max_records: int = 0,
    delay_seconds: float = 0.0,
    progress: ProgressCallback | None = None,
    company_selector: str = "",
    next_selector: str = "",
    max_pages: int = 120,
) -> list[GenericListingCompany]:
    directory_url = validate_directory_url(directory_url)
    queue = deque([directory_url])
    visited_pages: set[str] = set()
    all_companies: dict[str, GenericListingCompany] = {}

    while queue and len(visited_pages) < max_pages:
        page_url = queue.popleft()
        if page_url in visited_pages:
            continue
        visited_pages.add(page_url)
        if progress:
            progress(f"Analizando página {len(visited_pages)} del directorio…")

        response = get(session, page_url, delay_seconds=delay_seconds)
        soup = BeautifulSoup(response.text, "lxml")
        companies = parse_listing_companies_generic(
            response.text,
            response.url,
            company_selector=company_selector,
        )

        for company in companies:
            # No tomar las propias páginas de paginación como fichas.
            if company.url in visited_pages:
                continue
            all_companies.setdefault(company.url, company)
            if max_records and len(all_companies) >= max_records:
                return list(all_companies.values())

        pagination = _pagination_candidates(soup, response.url, next_selector=next_selector)
        for candidate in pagination:
            if candidate not in visited_pages and candidate not in queue:
                queue.append(candidate)

        # Sin links de paginación detectables, basta la página actual.
        if not pagination and len(visited_pages) == 1:
            break

    if not all_companies:
        raise GenericDirectoryError(
            "No pude detectar fichas de empresas automáticamente. "
            "Probá con un selector CSS de empresa en Configuración avanzada."
        )
    return list(all_companies.values())


def _iter_jsonld_objects(value):
    if isinstance(value, dict):
        if "@graph" in value:
            yield from _iter_jsonld_objects(value["@graph"])
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_jsonld_objects(item)


def _jsonld_org(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for obj in _iter_jsonld_objects(data):
            types = obj.get("@type", []) if isinstance(obj, dict) else []
            if isinstance(types, str):
                types = [types]
            if any(clean_text(t).casefold() in ORG_TYPES for t in types):
                return obj
    return {}


def _first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get("content") if node.has_attr("content") else node.get_text(" ", strip=True))
            if value:
                return value
    return ""


def _label_value(soup: BeautifulSoup, labels: set[str]) -> str:
    normalized = {x.casefold() for x in labels}
    # dl/dt/dd es muy común en fichas de directorios.
    for dt in soup.find_all("dt"):
        label = clean_text(dt.get_text(" ", strip=True)).strip(":").casefold()
        if label in normalized:
            dd = dt.find_next_sibling("dd")
            if dd:
                value = clean_text(dd.get_text(" ", strip=True))
                if value:
                    return value

    strings = [clean_text(s) for s in soup.stripped_strings if clean_text(s)]
    for i, item in enumerate(strings[:-1]):
        label = item.strip(":").casefold()
        if label in normalized:
            candidate = strings[i + 1]
            if candidate.strip(":").casefold() not in normalized:
                return candidate
    return ""


def _address_from_json(value) -> tuple[str, str, str, str]:
    if isinstance(value, str):
        return clean_text(value), "", "", ""
    if not isinstance(value, dict):
        return "", "", "", ""
    street = clean_text(value.get("streetAddress"))
    locality = clean_text(value.get("addressLocality"))
    region = clean_text(value.get("addressRegion"))
    country = value.get("addressCountry", "")
    if isinstance(country, dict):
        country = country.get("name", "")
    country = clean_text(country)
    postal = clean_text(value.get("postalCode"))
    full = ", ".join(x for x in [street, postal, locality, region, country] if x)
    return full, locality, region, country


def _extract_email_phone_links(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
    emails: list[str] = []
    phones: list[str] = []
    for a in soup.find_all("a", href=True):
        href = clean_text(a.get("href", ""))
        low = href.casefold()
        if low.startswith("mailto:"):
            value = href.split(":", 1)[1].split("?", 1)[0].strip()
            if value and value not in emails:
                emails.append(value)
        elif low.startswith("tel:"):
            value = clean_text(href.split(":", 1)[1])
            if value and value not in phones:
                phones.append(value)
        elif "wa.me/" in low or "whatsapp" in low:
            digits = re.sub(r"\D", "", href)
            if digits:
                value = f"+{digits}"
                if value not in phones:
                    phones.append(value)
    return emails, phones


def parse_detail_html_generic(
    html: str,
    detail_url: str,
    segmento: str,
    *,
    listing_text: str = "",
) -> CompanyRecord:
    soup = BeautifulSoup(html, "lxml")
    org = _jsonld_org(soup)

    name = clean_text(org.get("name")) if org else ""
    if not name:
        name = _first_text(soup, ["h1", "[itemprop='name']", "meta[property='og:title']", "title"])
    if not name:
        name = listing_text

    address, city, state, country = _address_from_json(org.get("address")) if org else ("", "", "", "")
    if not address:
        address = _first_text(soup, ["address", "[itemprop='streetAddress']", ".address", ".direccion", ".dirección"])
    city = city or _label_value(soup, LABELS["ciudad"])
    state = state or _label_value(soup, LABELS["estado"])
    country = country or _label_value(soup, LABELS["pais"])
    address = address or _label_value(soup, LABELS["direccion"])

    record = CompanyRecord(
        nombre_empresa=name,
        direccion=address,
        ciudad=city,
        estado=state,
        pais=country,
        segmento=segmento,
        url_fuente=detail_url,
    )

    if org:
        email = clean_text(org.get("email"))
        phone = clean_text(org.get("telephone"))
        site = clean_text(org.get("url"))
        if email:
            record.add_email(email.replace("mailto:", ""))
            record.fuente_correo = "Directorio"
        if phone:
            record.add_phone(phone.replace("tel:", ""))
            record.fuente_telefono = "Directorio"
        if site and site.startswith(("http://", "https://")) and not _same_host(site, detail_url):
            record.sitio_web = site
            record.fuente_sitio_web = "Directorio"
        same_as = org.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        for url in same_as:
            if "linkedin.com" in clean_text(url).casefold():
                record.linkedin = clean_text(url)
                record.fuente_linkedin = "Directorio"
                break

    emails, phones = _extract_email_phone_links(soup)
    if not record.correo and emails:
        record.add_email(emails[0])
        record.fuente_correo = "Directorio"
    for phone in phones:
        before = (record.telefono_1, record.telefono_2)
        record.add_phone(phone)
        if before != (record.telefono_1, record.telefono_2):
            record.fuente_telefono = "Directorio"

    if not record.correo:
        email_text = _label_value(soup, LABELS["correo"])
        if "@" in email_text:
            record.add_email(email_text)
            record.fuente_correo = "Directorio"
    if not record.telefono_1:
        phone_text = _label_value(soup, LABELS["telefono"])
        if phone_text:
            record.add_phone(phone_text)
            record.fuente_telefono = "Directorio"

    external_candidates: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        absolute = _clean_url(urljoin(detail_url, a.get("href", "")))
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        host = parsed.netloc.casefold()
        label = clean_text(a.get_text(" ", strip=True)).casefold()
        if "linkedin.com" in host and "/company/" in parsed.path.casefold() and not record.linkedin:
            record.linkedin = absolute
            record.fuente_linkedin = "Directorio"
            continue
        if _same_host(absolute, detail_url) or any(x in host for x in SOCIAL_HOSTS + MAP_HOSTS):
            continue
        score = 1
        if any(token in label for token in ["website", "sitio web", "página web", "pagina web", "web", "site"]):
            score += 5
        if a.get("rel") and "nofollow" not in [x.casefold() for x in a.get("rel", [])]:
            score += 1
        external_candidates.append((score, absolute))

    if not record.sitio_web and external_candidates:
        record.sitio_web = sorted(external_candidates, key=lambda x: x[0], reverse=True)[0][1]
        record.fuente_sitio_web = "Directorio"

    return record


def fetch_company_record_generic(
    session: requests.Session,
    company: GenericListingCompany,
    segmento: str,
    *,
    delay_seconds: float = 0.0,
) -> CompanyRecord:
    try:
        response = get(session, company.url, delay_seconds=delay_seconds)
        return parse_detail_html_generic(
            response.text,
            response.url,
            segmento,
            listing_text=company.listing_text,
        )
    except Exception as exc:
        return CompanyRecord(
            nombre_empresa=company.listing_text,
            segmento=segmento,
            url_fuente=company.url,
            estado_extraccion="ERROR",
            observaciones=f"{type(exc).__name__}: {exc}",
        )


def analyze_directory_compatibility(
    session: requests.Session,
    directory_url: str,
    *,
    company_selector: str = "",
) -> dict:
    url = validate_directory_url(directory_url)
    response = get(session, url)
    companies = parse_listing_companies_generic(response.text, response.url, company_selector=company_selector)
    soup = BeautifulSoup(response.text, "lxml")
    pagination = _pagination_candidates(soup, response.url)
    count = len(companies)
    if count >= 8:
        level, score = "Alta", 92
    elif count >= 3:
        level, score = "Media", 74
    elif count >= 1:
        level, score = "Baja", 52
    else:
        level, score = "No detectada", 20
    return {
        "level": level,
        "score": score,
        "companies_on_page": count,
        "pagination_detected": bool(pagination),
        "host": urlparse(response.url).netloc,
        "final_url": response.url,
    }
