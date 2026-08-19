from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from src.directorio import discover_company_urls, fetch_company_record, validate_segment_url
from src.enrichment import enrich_record
from src.exporter import BASE_COLUMNS, CONTROL_COLUMNS, records_to_excel
from src.http_client import build_session
from src.models import CompanyRecord


APP_NAME = "B2B Data Extractor"
APP_VERSION = "3.0"
DEFAULT_URL = "https://directoriodecarga.com/mexico/agentes-navieros"

st.set_page_config(
    page_title=f"{APP_NAME} · Intelligence Workspace",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None,
)


def init_state() -> None:
    defaults = {
        "records": [],
        "excel_bytes": None,
        "last_segment": "",
        "last_include_control": True,
        "last_mode": "Directorio",
        "last_volume": "Todas",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def palette(mode: str) -> dict[str, str]:
    if mode == "Oscuro":
        return {
            "bg": "#070A11",
            "bg2": "#090E18",
            "sidebar": "#0A0F19",
            "surface": "#0D1420",
            "surface2": "#111A28",
            "surface3": "#151F2F",
            "text": "#F6F8FB",
            "text2": "#C7D0DD",
            "muted": "#7F8A9D",
            "line": "rgba(255,255,255,.085)",
            "line2": "rgba(255,255,255,.13)",
            "accent": "#64DDF5",
            "accent2": "#7C8DFF",
            "accent_soft": "rgba(100,221,245,.10)",
            "accent2_soft": "rgba(124,141,255,.12)",
            "success": "#42D59C",
            "success_soft": "rgba(66,213,156,.10)",
            "warning": "#F4C76B",
            "danger": "#FF7B88",
            "shadow": "0 24px 70px rgba(0,0,0,.28)",
            "shadow_small": "0 10px 32px rgba(0,0,0,.18)",
            "grid": "rgba(255,255,255,.025)",
            "input": "#0C131E",
            "button_text": "#041015",
        }
    return {
        "bg": "#F5F7FA",
        "bg2": "#F8FAFC",
        "sidebar": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface2": "#F9FBFD",
        "surface3": "#F3F6FA",
        "text": "#0A1220",
        "text2": "#344054",
        "muted": "#667085",
        "line": "rgba(13,24,38,.085)",
        "line2": "rgba(13,24,38,.13)",
        "accent": "#087EA4",
        "accent2": "#536DFE",
        "accent_soft": "rgba(8,126,164,.08)",
        "accent2_soft": "rgba(83,109,254,.09)",
        "success": "#0E9F6E",
        "success_soft": "rgba(14,159,110,.08)",
        "warning": "#B7791F",
        "danger": "#D6455D",
        "shadow": "0 24px 70px rgba(31,44,61,.10)",
        "shadow_small": "0 10px 28px rgba(31,44,61,.075)",
        "grid": "rgba(10,18,32,.025)",
        "input": "#FFFFFF",
        "button_text": "#FFFFFF",
    }


def inject_styles(mode: str) -> None:
    p = palette(mode)
    css = f"""
    <style>
    :root {{
        --bg:{p['bg']}; --bg2:{p['bg2']}; --sidebar:{p['sidebar']};
        --surface:{p['surface']}; --surface2:{p['surface2']}; --surface3:{p['surface3']};
        --text:{p['text']}; --text2:{p['text2']}; --muted:{p['muted']};
        --line:{p['line']}; --line2:{p['line2']}; --accent:{p['accent']}; --accent2:{p['accent2']};
        --accent-soft:{p['accent_soft']}; --accent2-soft:{p['accent2_soft']};
        --success:{p['success']}; --success-soft:{p['success_soft']};
        --warning:{p['warning']}; --danger:{p['danger']}; --shadow:{p['shadow']};
        --shadow-small:{p['shadow_small']}; --grid:{p['grid']}; --input:{p['input']};
        --button-text:{p['button_text']};
    }}

    html, body, [class*="css"] {{font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}}
    #MainMenu, footer, [data-testid="stToolbar"] {{visibility:hidden !important;}}
    header[data-testid="stHeader"] {{background:transparent !important; height:0 !important;}}
    [data-testid="stAppViewContainer"] {{
        background:
          radial-gradient(circle at 76% -10%, var(--accent2-soft), transparent 30rem),
          radial-gradient(circle at 15% 8%, var(--accent-soft), transparent 24rem),
          linear-gradient(var(--grid) 1px, transparent 1px),
          linear-gradient(90deg, var(--grid) 1px, transparent 1px),
          var(--bg);
        background-size:auto, auto, 34px 34px, 34px 34px, auto;
        color:var(--text);
    }}
    [data-testid="stMain"] {{background:transparent;}}
    .block-container {{max-width:1480px; padding:1.7rem 2.25rem 4rem;}}

    [data-testid="stSidebar"] {{
        width:336px !important; min-width:336px !important;
        border-right:1px solid var(--line) !important;
        background:var(--sidebar) !important;
        box-shadow:18px 0 50px rgba(0,0,0,.025);
    }}
    [data-testid="stSidebar"] > div:first-child {{background:var(--sidebar) !important; padding-top:1.35rem;}}
    [data-testid="stSidebar"] * {{color:var(--text);}}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{color:var(--muted);}}

    /* Native widget polish */
    [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
    [data-testid="stNumberInput"] > div > div {{
        background:var(--input) !important; border-color:var(--line2) !important;
        border-radius:12px !important; box-shadow:none !important;
    }}
    input, textarea {{color:var(--text) !important; -webkit-text-fill-color:var(--text) !important;}}
    input::placeholder, textarea::placeholder {{color:var(--muted) !important; opacity:.7;}}
    label, [data-testid="stWidgetLabel"] p {{color:var(--text2) !important; font-weight:650 !important;}}
    [data-baseweb="popover"] > div, [role="listbox"] {{background:var(--surface) !important; color:var(--text) !important;}}

    [data-testid="stSegmentedControl"] button {{
        border-color:var(--line) !important; background:var(--surface2) !important;
        color:var(--muted) !important; min-height:38px; font-weight:750;
    }}
    [data-testid="stSegmentedControl"] button[aria-pressed="true"] {{
        background:var(--text) !important; color:var(--bg) !important; border-color:var(--text) !important;
    }}

    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {{
        min-height:48px; border-radius:12px !important; font-weight:780 !important;
        letter-spacing:-.01em; transition:all .18s ease;
    }}
    div[data-testid="stButton"] button[kind="primary"], div[data-testid="stDownloadButton"] button[kind="primary"] {{
        background:linear-gradient(105deg,var(--accent),var(--accent2)) !important;
        color:var(--button-text) !important; border:none !important;
        box-shadow:0 12px 30px var(--accent2-soft) !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] p,
    div[data-testid="stDownloadButton"] button[kind="primary"] p {{color:var(--button-text) !important;}}
    div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover {{transform:translateY(-1px); filter:brightness(1.035);}}
    div[data-testid="stButton"] button[kind="secondary"] {{background:var(--surface) !important; color:var(--text) !important; border-color:var(--line2) !important;}}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border:1px solid var(--line) !important; border-radius:20px !important;
        background:linear-gradient(180deg,var(--surface),var(--surface2)) !important;
        box-shadow:var(--shadow-small); overflow:hidden;
    }}
    [data-testid="stExpander"] {{border:1px solid var(--line) !important; background:var(--surface2) !important; border-radius:12px !important;}}
    [data-testid="stExpander"] details summary p {{color:var(--text2) !important; font-weight:700 !important;}}

    [data-testid="stMetric"] {{
        border:1px solid var(--line); border-radius:16px; padding:15px 16px;
        background:var(--surface); box-shadow:var(--shadow-small);
    }}
    [data-testid="stMetricLabel"] p {{color:var(--muted) !important; font-weight:720 !important;}}
    [data-testid="stMetricValue"] {{color:var(--text) !important; font-weight:850 !important; letter-spacing:-.035em;}}
    [data-testid="stMetricDelta"] {{color:var(--success) !important;}}

    [data-testid="stDataFrame"] {{border:1px solid var(--line); border-radius:15px; overflow:hidden;}}
    [data-baseweb="tab-list"] {{gap:8px; border-bottom:1px solid var(--line);}}
    [data-baseweb="tab"] {{color:var(--muted) !important; font-weight:740;}}
    [aria-selected="true"][data-baseweb="tab"] {{color:var(--text) !important;}}
    [data-baseweb="tab-highlight"] {{background:var(--accent) !important;}}
    [data-testid="stProgress"] > div > div > div > div {{background:linear-gradient(90deg,var(--accent),var(--accent2)) !important;}}

    .brand {{display:flex; align-items:center; gap:12px; margin:0 0 22px;}}
    .brand-mark {{position:relative; width:39px; height:39px; border-radius:12px; background:linear-gradient(145deg,var(--accent),var(--accent2)); box-shadow:0 12px 26px var(--accent2-soft);}}
    .brand-mark:before {{content:""; position:absolute; inset:9px; border:1.6px solid rgba(255,255,255,.88); border-radius:6px;}}
    .brand-mark:after {{content:""; position:absolute; width:6px; height:6px; border-radius:2px; background:#fff; right:8px; top:8px; box-shadow:-11px 11px 0 rgba(255,255,255,.65);}}
    .brand-name {{font-size:15px; font-weight:850; letter-spacing:-.025em; color:var(--text); line-height:1.15;}}
    .brand-sub {{font-size:10px; font-weight:750; letter-spacing:.12em; color:var(--muted); text-transform:uppercase; margin-top:4px;}}

    .side-label {{font-size:10px; font-weight:820; letter-spacing:.13em; text-transform:uppercase; color:var(--muted); margin:20px 0 8px;}}
    .side-summary {{border:1px solid var(--line); background:var(--surface2); border-radius:14px; padding:13px 14px; margin:10px 0 0;}}
    .side-summary-top {{display:flex; justify-content:space-between; align-items:center; gap:8px;}}
    .side-summary-title {{font-size:12px; color:var(--muted); font-weight:680;}}
    .side-summary-value {{font-size:13px; color:var(--text); font-weight:820;}}
    .side-rule {{height:1px; background:var(--line); margin:12px 0;}}
    .system-line {{display:flex; align-items:center; gap:8px; color:var(--muted); font-size:11px; margin-top:20px;}}
    .live-dot {{width:7px; height:7px; border-radius:50%; background:var(--success); box-shadow:0 0 0 5px var(--success-soft);}}

    .topbar {{display:flex; justify-content:space-between; align-items:center; gap:16px; margin:2px 0 28px;}}
    .breadcrumb {{font-size:11px; font-weight:800; letter-spacing:.11em; color:var(--muted); text-transform:uppercase;}}
    .workspace-status {{display:inline-flex; align-items:center; gap:8px; border:1px solid var(--line); background:var(--surface); border-radius:999px; padding:7px 11px; font-size:11px; font-weight:740; color:var(--text2); box-shadow:var(--shadow-small);}}

    .hero {{position:relative; overflow:hidden; border:1px solid var(--line); border-radius:24px; padding:38px 42px; background:linear-gradient(135deg,var(--surface) 0%,var(--surface2) 62%,var(--accent2-soft) 130%); box-shadow:var(--shadow); margin-bottom:20px;}}
    .hero:before {{content:""; position:absolute; width:460px; height:460px; border-radius:50%; right:-210px; top:-250px; background:radial-gradient(circle,var(--accent-soft),transparent 64%); border:1px solid var(--line);}}
    .hero:after {{content:""; position:absolute; width:260px; height:260px; border-radius:50%; right:-60px; bottom:-210px; border:1px solid var(--line); box-shadow:0 0 0 42px var(--accent-soft),0 0 0 84px var(--accent2-soft);}}
    .eyebrow {{display:inline-flex; align-items:center; gap:9px; color:var(--accent); font-size:10px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; margin-bottom:17px;}}
    .eyebrow-line {{width:24px; height:1px; background:var(--accent);}}
    .hero h1 {{position:relative; z-index:1; max-width:900px; font-size:clamp(2.45rem,4.8vw,4.6rem); line-height:.98; letter-spacing:-.055em; font-weight:820; color:var(--text); margin:0 0 18px;}}
    .hero h1 span {{background:linear-gradient(100deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent;}}
    .hero p {{position:relative; z-index:1; max-width:760px; color:var(--muted); font-size:1rem; line-height:1.7; margin:0;}}
    .hero-chips {{display:flex; flex-wrap:wrap; gap:8px; margin-top:25px; position:relative; z-index:1;}}
    .chip {{border:1px solid var(--line); border-radius:999px; padding:7px 10px; background:var(--surface); color:var(--text2); font-size:10px; font-weight:760; letter-spacing:.02em;}}

    .panel-title-row {{display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px;}}
    .kicker {{font-size:10px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); margin-bottom:7px;}}
    .title {{font-size:1.3rem; font-weight:820; color:var(--text); letter-spacing:-.03em; line-height:1.2;}}
    .copy {{font-size:.83rem; color:var(--muted); margin-top:5px; line-height:1.55;}}
    .mini-badge {{white-space:nowrap; border:1px solid var(--line); background:var(--surface2); color:var(--text2); border-radius:999px; padding:7px 10px; font-size:10px; font-weight:750;}}

    .schema {{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px;}}
    .schema-item {{display:flex; align-items:center; gap:9px; border:1px solid var(--line); background:var(--surface2); border-radius:11px; padding:9px 10px; font-size:11px; color:var(--text2); font-weight:670;}}
    .schema-icon {{width:20px; height:20px; border-radius:6px; display:grid; place-items:center; background:var(--accent-soft); color:var(--accent); font-size:9px; font-weight:900;}}

    .step-grid {{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px;}}
    .step-card {{border:1px solid var(--line); background:var(--surface); border-radius:16px; padding:18px; min-height:145px; box-shadow:var(--shadow-small);}}
    .step-index {{font-size:9px; font-weight:850; letter-spacing:.13em; color:var(--accent); text-transform:uppercase;}}
    .step-title {{font-size:14px; font-weight:800; letter-spacing:-.02em; color:var(--text); margin:14px 0 7px;}}
    .step-copy {{font-size:11px; color:var(--muted); line-height:1.6;}}

    .metric-card {{border:1px solid var(--line); background:var(--surface); border-radius:17px; padding:16px 17px 14px; box-shadow:var(--shadow-small); min-height:118px;}}
    .metric-label {{font-size:10px; color:var(--muted); font-weight:760; letter-spacing:.04em; text-transform:uppercase;}}
    .metric-value {{font-size:2rem; color:var(--text); font-weight:840; letter-spacing:-.045em; margin:7px 0 5px;}}
    .metric-foot {{font-size:10px; color:var(--muted); font-weight:650;}}
    .metric-foot b {{color:var(--success);}}
    .metric-track {{height:4px; background:var(--surface3); border-radius:99px; overflow:hidden; margin-top:12px;}}
    .metric-fill {{height:100%; border-radius:99px; background:linear-gradient(90deg,var(--accent),var(--accent2));}}

    .quality-item {{margin:13px 0 16px;}}
    .quality-head {{display:flex; justify-content:space-between; gap:12px; margin-bottom:7px;}}
    .quality-label {{font-size:11px; font-weight:750; color:var(--text2);}}
    .quality-value {{font-size:11px; font-weight:830; color:var(--text);}}
    .quality-track {{height:7px; background:var(--surface3); border-radius:99px; overflow:hidden;}}
    .quality-fill {{height:100%; background:linear-gradient(90deg,var(--accent),var(--accent2)); border-radius:99px;}}

    .empty-state {{border:1px dashed var(--line2); border-radius:18px; padding:26px; background:var(--surface2); color:var(--muted);}}
    .empty-title {{color:var(--text); font-size:13px; font-weight:800; margin-bottom:6px;}}
    .footer-note {{text-align:center; color:var(--muted); font-size:10px; padding-top:28px; opacity:.75;}}

    @media (max-width: 980px) {{
      [data-testid="stSidebar"] {{width:305px !important; min-width:305px !important;}}
      .block-container {{padding:1.3rem 1rem 3rem;}}
      .hero {{padding:30px 24px;}}
      .step-grid {{grid-template-columns:1fr;}}
      .schema {{grid-template-columns:1fr;}}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def infer_from_url(url: str) -> tuple[str, str]:
    try:
        path = [p for p in urlparse(url).path.split("/") if p]
        country = titleize(path[0]) if path else ""
        segment = titleize(path[-1]) if len(path) >= 2 else ""
        country_map = {"Mexico": "México", "Peru": "Perú", "Panama": "Panamá"}
        return segment, country_map.get(country, country)
    except Exception:
        return "", ""


def titleize(value: str) -> str:
    value = re.sub(r"[-_]+", " ", value.strip())
    return " ".join(part.capitalize() for part in value.split())


def rows_dataframe(records: list[CompanyRecord], include_control: bool) -> pd.DataFrame:
    columns = BASE_COLUMNS + (CONTROL_COLUMNS if include_control else [])
    return pd.DataFrame([{label: record.as_dict().get(key, "") for label, key in columns} for record in records])


def percent(count: int, total: int) -> int:
    return round((count / total) * 100) if total else 0


def panel_header(kicker: str, title: str, copy: str, badge: str | None = None) -> None:
    badge_html = f'<div class="mini-badge">{html.escape(badge)}</div>' if badge else ""
    st.markdown(
        f"""
        <div class="panel-title-row">
          <div>
            <div class="kicker">{html.escape(kicker)}</div>
            <div class="title">{html.escape(title)}</div>
            <div class="copy">{html.escape(copy)}</div>
          </div>
          {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str | int, pct: int, foot: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{html.escape(label)}</div>
          <div class="metric-value">{html.escape(str(value))}</div>
          <div class="metric-foot">{foot}</div>
          <div class="metric-track"><div class="metric-fill" style="width:{max(0,min(100,pct))}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def quality_bar(label: str, pct: int) -> None:
    st.markdown(
        f"""
        <div class="quality-item">
          <div class="quality-head"><span class="quality-label">{html.escape(label)}</span><span class="quality-value">{pct}%</span></div>
          <div class="quality-track"><div class="quality-fill" style="width:{pct}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


init_state()

# Sidebar comes first so theme changes are applied immediately on rerun.
with st.sidebar:
    st.markdown(
        f"""
        <div class="brand">
          <div class="brand-mark"></div>
          <div>
            <div class="brand-name">B2B Data Extractor</div>
            <div class="brand-sub">Intelligence Workspace · v{APP_VERSION}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-label">Apariencia</div>', unsafe_allow_html=True)
    theme_mode = st.segmented_control(
        "Apariencia",
        ["Claro", "Oscuro"],
        default="Oscuro",
        key="theme_mode",
        label_visibility="collapsed",
        width="stretch",
    ) or "Oscuro"

    st.markdown('<div class="side-label">Volumen de extracción</div>', unsafe_allow_html=True)
    volume_mode = st.segmented_control(
        "Volumen",
        ["Todas", "Cantidad"],
        default="Todas",
        label_visibility="collapsed",
        width="stretch",
        key="volume_mode",
    ) or "Todas"
    if volume_mode == "Cantidad":
        quantity = int(
            st.number_input(
                "Cantidad de empresas",
                min_value=1,
                max_value=10000,
                value=100,
                step=25,
                help="El extractor se detendrá al alcanzar esta cantidad.",
            )
        )
        max_records = quantity
        volume_summary = f"{quantity:,}".replace(",", ".") + " empresas"
    else:
        max_records = 0
        volume_summary = "Todas las empresas"

    st.markdown('<div class="side-label">Profundidad</div>', unsafe_allow_html=True)
    extraction_mode = st.selectbox(
        "Profundidad de extracción",
        ["Directorio", "Enriquecida"],
        index=0,
        label_visibility="collapsed",
        help="Enriquecida intenta completar web oficial, contactos y LinkedIn cuando faltan.",
    )
    if extraction_mode == "Directorio":
        find_site = crawl_site = find_linkedin = False
    else:
        find_site = crawl_site = find_linkedin = True

    with st.expander("Configuración avanzada"):
        include_control = st.toggle(
            "Trazabilidad de fuentes",
            value=True,
            help="Incluye columnas de control, URL fuente y observaciones en el Excel.",
        )
        delay_seconds = st.slider(
            "Pausa entre solicitudes",
            0.0,
            2.0,
            0.25,
            0.05,
            help="Una pausa moderada reduce la carga sobre el sitio fuente.",
        )

    st.markdown(
        f"""
        <div class="side-summary">
          <div class="side-summary-top"><span class="side-summary-title">Alcance</span><span class="side-summary-value">{html.escape(volume_summary)}</span></div>
          <div class="side-rule"></div>
          <div class="side-summary-top"><span class="side-summary-title">Modo</span><span class="side-summary-value">{html.escape(extraction_mode)}</span></div>
          <div class="side-rule"></div>
          <div class="side-summary-top"><span class="side-summary-title">Salida</span><span class="side-summary-value">Excel · 10 campos</span></div>
        </div>
        <div class="system-line"><span class="live-dot"></span> Sistema disponible</div>
        """,
        unsafe_allow_html=True,
    )

inject_styles(theme_mode)

st.markdown(
    """
    <div class="topbar">
      <div class="breadcrumb">Data Operations / Extraction Workspace</div>
      <div class="workspace-status"><span class="live-dot"></span> Ready for extraction</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow"><span class="eyebrow-line"></span> B2B Data Intelligence</div>
      <h1>De directorios a una base comercial <span>lista para accionar.</span></h1>
      <p>Convertí segmentos completos de empresas en datos estructurados, trazables y listos para Excel. Una experiencia diseñada para operar con velocidad, claridad y control.</p>
      <div class="hero-chips">
        <span class="chip">Segmentación precisa</span>
        <span class="chip">Datos de contacto</span>
        <span class="chip">Enriquecimiento opcional</span>
        <span class="chip">Trazabilidad de fuentes</span>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

main_col, info_col = st.columns([1.65, 0.75], gap="large")

with main_col:
    with st.container(border=True):
        panel_header(
            "Nueva extracción",
            "Definí la fuente",
            "Pegá la URL del segmento. El sistema detectará automáticamente segmento y país para que solo tengas que validar antes de ejecutar.",
            "Directorio de Carga",
        )
        segment_url = st.text_input(
            "URL del segmento",
            value=DEFAULT_URL,
            placeholder="https://directoriodecarga.com/mexico/...",
            icon=":material/link:",
        )
        inferred_segment, inferred_country = infer_from_url(segment_url)
        c1, c2 = st.columns(2)
        with c1:
            segmento = st.text_input(
                "Segmento",
                value=inferred_segment or "Agentes Navieros",
                icon=":material/category:",
            )
        with c2:
            pais_forzado = st.text_input(
                "País",
                value=inferred_country or "México",
                icon=":material/public:",
            )

        st.caption("Solo se incorporan empresas pertenecientes al segmento fuente. El enriquecimiento no agrega empresas externas.")
        st.write("")
        start = st.button(
            "Iniciar extracción",
            type="primary",
            icon=":material/arrow_forward:",
            use_container_width=True,
        )

with info_col:
    with st.container(border=True):
        panel_header(
            "Output",
            "Estructura del Excel",
            "El archivo final mantiene un esquema consistente para trabajar, cruzar o importar la base.",
        )
        schema_items = [
            ("01", "Nombre de empresa"), ("02", "Correo"),
            ("03", "Teléfono 1"), ("04", "Teléfono 2"),
            ("05", "Dirección"), ("06", "Estado"),
            ("07", "País"), ("08", "Sitio web"),
            ("09", "LinkedIn"), ("10", "Segmento"),
        ]
        schema_html = "".join(
            f'<div class="schema-item"><span class="schema-icon">{i}</span>{html.escape(label)}</div>'
            for i, label in schema_items
        )
        st.markdown(f'<div class="schema">{schema_html}</div>', unsafe_allow_html=True)

if start:
    try:
        clean_url = validate_segment_url(segment_url)
        if not segmento.strip():
            raise ValueError("Ingresá el nombre del segmento.")

        session = build_session()
        st.write("")
        with st.container(border=True):
            panel_header(
                "Procesamiento",
                "Extracción en curso",
                "Estamos recorriendo el segmento y estructurando la información empresa por empresa.",
                volume_summary,
            )
            with st.status("Preparando extracción…", expanded=True) as status:
                status_line = st.empty()
                progress_bar = st.progress(0, text="Leyendo el segmento…")

                def listing_progress(message: str) -> None:
                    status_line.markdown(f"**Directorio:** {message}")

                companies = discover_company_urls(
                    session,
                    clean_url,
                    max_records=int(max_records),
                    delay_seconds=float(delay_seconds),
                    progress=listing_progress,
                )
                if not companies:
                    raise RuntimeError("No se encontraron empresas en el segmento.")

                records: list[CompanyRecord] = []
                total = len(companies)
                for idx, company in enumerate(companies, start=1):
                    display_name = company.listing_text or company.url
                    status_line.markdown(f"**{idx}/{total}** · Extrayendo **{display_name}**")
                    record = fetch_company_record(
                        session,
                        company,
                        segmento.strip(),
                        delay_seconds=float(delay_seconds),
                    )
                    if not record.pais:
                        record.pais = pais_forzado.strip()

                    if record.estado_extraccion == "OK" and (find_site or crawl_site or find_linkedin):
                        status_line.markdown(f"**{idx}/{total}** · Enriqueciendo **{record.nombre_empresa}**")
                        record = enrich_record(
                            session,
                            record,
                            find_site=find_site,
                            crawl_site=crawl_site,
                            find_linkedin_search=find_linkedin,
                        )

                    records.append(record)
                    progress_bar.progress(idx / total, text=f"Procesadas {idx} de {total}")

                st.session_state.records = records
                st.session_state.excel_bytes = records_to_excel(records, include_control=include_control)
                st.session_state.last_segment = segmento.strip()
                st.session_state.last_include_control = include_control
                st.session_state.last_mode = extraction_mode
                st.session_state.last_volume = volume_summary
                status_line.markdown(f"**Completado.** Se procesaron {len(records)} empresas.")
                status.update(label=f"Extracción completada · {len(records)} empresas", state="complete", expanded=False)

    except Exception as exc:
        st.error(f"No se pudo completar la extracción: {type(exc).__name__}: {exc}", icon=":material/error:")

records: list[CompanyRecord] = st.session_state.records

if records:
    st.write("")
    panel_header(
        "Intelligence snapshot",
        "Resumen de ejecución",
        "Cobertura de los campos más importantes y acceso directo a la base procesada.",
        st.session_state.last_volume,
    )

    total = len(records)
    ok = sum(r.estado_extraccion == "OK" for r in records)
    with_email = sum(bool(r.correo) for r in records)
    with_phone = sum(bool(r.telefono_1) for r in records)
    with_site = sum(bool(r.sitio_web) for r in records)
    with_linkedin = sum(bool(r.linkedin) for r in records)

    m1, m2, m3, m4, m5 = st.columns(5, gap="small")
    with m1:
        metric_card("Empresas", total, percent(ok, total), f"<b>{percent(ok,total)}%</b> procesadas OK")
    with m2:
        metric_card("Correo", with_email, percent(with_email, total), f"<b>{percent(with_email,total)}%</b> de cobertura")
    with m3:
        metric_card("Teléfono", with_phone, percent(with_phone, total), f"<b>{percent(with_phone,total)}%</b> de cobertura")
    with m4:
        metric_card("Sitio web", with_site, percent(with_site, total), f"<b>{percent(with_site,total)}%</b> de cobertura")
    with m5:
        metric_card("LinkedIn", with_linkedin, percent(with_linkedin, total), f"<b>{percent(with_linkedin,total)}%</b> de cobertura")

    st.write("")
    data_col, quality_col = st.columns([1.7, 0.7], gap="large")
    with data_col:
        with st.container(border=True):
            panel_header("Dataset", "Base procesada", "Filtrá y revisá los registros antes de descargar.", f"{total} registros")
            df = rows_dataframe(records, st.session_state.last_include_control)
            search = st.text_input(
                "Buscar en resultados",
                placeholder="Empresa, estado, correo, segmento…",
                key="result_filter",
                icon=":material/search:",
            )
            if search and search.strip():
                mask = df.astype(str).apply(lambda col: col.str.contains(search.strip(), case=False, na=False)).any(axis=1)
                shown = df.loc[mask]
            else:
                shown = df
            st.dataframe(shown, use_container_width=True, hide_index=True, height=455)
            st.caption(f"Mostrando {len(shown)} de {len(df)} registros.")

    with quality_col:
        with st.container(border=True):
            panel_header("Coverage", "Calidad de datos", "Cobertura sobre el total de empresas extraídas.")
            quality_bar("Correo", percent(with_email, total))
            quality_bar("Teléfono", percent(with_phone, total))
            quality_bar("Sitio web", percent(with_site, total))
            quality_bar("LinkedIn", percent(with_linkedin, total))
            complete_contacts = sum(bool(r.correo and r.telefono_1) for r in records)
            digital_complete = sum(bool(r.sitio_web and r.linkedin) for r in records)
            st.divider()
            st.metric("Correo + teléfono", complete_contacts, f"{percent(complete_contacts,total)}% de la base")
            st.metric("Web + LinkedIn", digital_complete, f"{percent(digital_complete,total)}% de la base")

    st.write("")
    with st.container(border=True):
        tab_results, tab_audit = st.tabs(["Exportación", "Auditoría"])
        with tab_results:
            panel_header("Deliverable", "Descargar resultado", "Generá el archivo Excel con el esquema definido y la configuración de esta ejecución.")
            safe_segment = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ_-]+", "_", st.session_state.last_segment).strip("_")
            filename = f"empresas_{safe_segment or 'segmento'}.xlsx"
            cta1, cta2 = st.columns([2.2, 0.8])
            with cta1:
                if st.session_state.excel_bytes:
                    st.download_button(
                        "Descargar Excel",
                        data=st.session_state.excel_bytes,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        icon=":material/download:",
                        use_container_width=True,
                    )
            with cta2:
                if st.button("Limpiar", icon=":material/refresh:", use_container_width=True):
                    st.session_state.records = []
                    st.session_state.excel_bytes = None
                    st.rerun()
        with tab_audit:
            error_records = [r for r in records if r.estado_extraccion != "OK" or r.observaciones]
            if error_records:
                audit_df = pd.DataFrame([
                    {
                        "Empresa": r.nombre_empresa,
                        "Estado": r.estado_extraccion,
                        "Observaciones": r.observaciones,
                        "URL fuente": r.url_fuente,
                    }
                    for r in error_records
                ])
                st.dataframe(audit_df, use_container_width=True, hide_index=True)
            else:
                st.success("La ejecución no registró errores u observaciones.", icon=":material/check_circle:")
else:
    st.write("")
    st.markdown(
        """
        <div class="step-grid">
          <div class="step-card"><div class="step-index">01 · Source</div><div class="step-title">Definí el segmento</div><div class="step-copy">Pegá la URL del directorio y validá el segmento y país detectados automáticamente.</div></div>
          <div class="step-card"><div class="step-index">02 · Process</div><div class="step-title">Elegí el alcance</div><div class="step-copy">Desde la barra lateral decidí si querés una cantidad específica de empresas o el segmento completo.</div></div>
          <div class="step-card"><div class="step-index">03 · Export</div><div class="step-title">Descargá la base</div><div class="step-copy">Revisá cobertura, filtrá resultados y obtené un Excel estructurado listo para tu flujo comercial.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="footer-note">B2B Data Extractor · Data Operations Workspace · Utilizá una frecuencia razonable de solicitudes y respetá los términos de los sitios fuente.</div>',
    unsafe_allow_html=True,
)
