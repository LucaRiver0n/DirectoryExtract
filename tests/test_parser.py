from pathlib import Path

from src.directorio import parse_detail_html, parse_listing_companies, parse_max_page, parse_record_count

HERE = Path(__file__).parent


def load(name):
    return (HERE / "fixtures" / name).read_text(encoding="utf-8")


def test_listing():
    html = load("listing.html")
    companies = parse_listing_companies(html, "https://directoriodecarga.com/mexico/agentes-navieros")
    assert len(companies) == 2
    assert parse_record_count(html) == 227
    assert parse_max_page(html) == 19


def test_detail():
    record, connect = parse_detail_html(
        load("detail.html"),
        "https://directoriodecarga.com/empresas/empresa-uno",
        "Agentes Navieros",
    )
    assert record.nombre_empresa == "EMPRESA UNO"
    assert record.direccion == "Av. Ejemplo 123"
    assert record.estado == "Ciudad de México"
    assert record.pais == "México"
    assert record.sitio_web.startswith("https://empresauno.com")
    assert "/company/empresa-uno" in record.linkedin
    assert len(connect) == 2
