from pathlib import Path

from src.generic_directory import parse_detail_html_generic, parse_listing_companies_generic

HERE = Path(__file__).parent


def load(name):
    return (HERE / "fixtures" / name).read_text(encoding="utf-8")


def test_generic_listing_detection():
    companies = parse_listing_companies_generic(
        load("generic_listing.html"),
        "https://example.org/directory",
    )
    urls = {c.url for c in companies}
    assert "https://example.org/members/acme-logistics" in urls
    assert "https://example.org/members/ocean-link" in urls
    assert "https://example.org/contact" not in urls


def test_generic_detail_jsonld():
    record = parse_detail_html_generic(
        load("generic_detail.html"),
        "https://example.org/members/acme-logistics",
        "Logística",
    )
    assert record.nombre_empresa == "ACME Logistics"
    assert record.correo == "sales@acme.test"
    assert record.telefono_1 == "+52 55 1234 5678"
    assert record.estado == "Nuevo León"
    assert record.pais == "México"
    assert record.sitio_web == "https://acme.test"
    assert "/company/acme-logistics/" in record.linkedin
