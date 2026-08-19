from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from src.engine import analyze_source, discover_companies, fetch_company, source_profile, validate_source_url
from src.enrichment import enrich_record
from src.exporter import BASE_COLUMNS, CONTROL_COLUMNS, records_to_excel
from src.http_client import build_session
from src.models import CompanyRecord
from src.settings import BRAND_NAME, CONTACT_EMAIL, PRODUCT_NAME, TAGLINE


APP_VERSION = "4.0"
DEFAULT_URL = "https://directoriodecarga.com/mexico/agentes-navieros"

st.set_page_config(
    page_title=f"{BRAND_NAME} · {PRODUCT_NAME}",
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
        "last_mode": "Directorio",
        "last_volume": "Todas las empresas",
        "last_source": "",
        "compatibility": None,
        "compatibility_url": "",
        "theme_mode": "Oscuro",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def palette(mode: str) -> dict[str, str]:
    if mode == "Claro":
        return {
            "bg": "#F4F7FB", "bg2": "#FFFFFF", "surface": "#FFFFFF", "surface2": "#F8FAFD",
            "surface3": "#EEF3F8", "text": "#08131F", "text2": "#2A3B4E", "muted": "#68788A",
            "line": "rgba(8,19,31,.09)", "line2": "rgba(8,19,31,.14)", "accent": "#007EAA",
            "accent2": "#6558FF", "cyan": "#04BFE6", "green": "#009A72", "warning": "#9A6A12",
            "danger": "#CF3E59", "glass": "rgba(255,255,255,.78)", "grid": "rgba(8,19,31,.026)",
            "shadow": "0 28px 80px rgba(29,47,68,.10)", "shadow2": "0 14px 42px rgba(29,47,68,.075)",
            "button_text": "#FFFFFF", "sidebar": "#FFFFFF",
        }
    return {
        "bg": "#05070C", "bg2": "#080C13", "surface": "#0B111B", "surface2": "#0E1622",
        "surface3": "#141E2C", "text": "#F8FAFC", "text2": "#C9D3DF", "muted": "#7D8A9B",
        "line": "rgba(255,255,255,.075)", "line2": "rgba(255,255,255,.125)", "accent": "#66E2F5",
        "accent2": "#8276FF", "cyan": "#24D8FF", "green": "#42D7A2", "warning": "#F4C76B",
        "danger": "#FF7586", "glass": "rgba(10,16,25,.78)", "grid": "rgba(255,255,255,.025)",
        "shadow": "0 32px 90px rgba(0,0,0,.34)", "shadow2": "0 14px 46px rgba(0,0,0,.22)",
        "button_text": "#031014", "sidebar": "#070B12",
    }


def inject_styles(mode: str, *, landing: bool) -> None:
    p = palette(mode)
    sidebar_css = """
    [data-testid="stSidebar"] {display:none !important;}
    [data-testid="collapsedControl"] {display:none !important;}
    """ if landing else f"""
    [data-testid="stSidebar"] {{
      width:348px !important; min-width:348px !important;
      background:{p['sidebar']} !important; border-right:1px solid {p['line']} !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{background:{p['sidebar']} !important; padding-top:1.2rem;}}
    """

    st.markdown(
        f"""
<style>
:root {{
  --bg:{p['bg']}; --bg2:{p['bg2']}; --surface:{p['surface']}; --surface2:{p['surface2']};
  --surface3:{p['surface3']}; --text:{p['text']}; --text2:{p['text2']}; --muted:{p['muted']};
  --line:{p['line']}; --line2:{p['line2']}; --accent:{p['accent']}; --accent2:{p['accent2']};
  --cyan:{p['cyan']}; --green:{p['green']}; --warning:{p['warning']}; --danger:{p['danger']};
  --glass:{p['glass']}; --grid:{p['grid']}; --shadow:{p['shadow']}; --shadow2:{p['shadow2']};
  --button-text:{p['button_text']};
}}
html, body, [class*="css"] {{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}}
#MainMenu, footer, [data-testid="stToolbar"] {{visibility:hidden !important;}}
header[data-testid="stHeader"] {{background:transparent !important;height:0 !important;}}
[data-testid="stAppViewContainer"] {{
  color:var(--text);
  background:
    radial-gradient(circle at 83% -2%, rgba(130,118,255,.11), transparent 32rem),
    radial-gradient(circle at 11% 2%, rgba(36,216,255,.075), transparent 28rem),
    linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px),var(--bg);
  background-size:auto,auto,36px 36px,36px 36px,auto;
}}
.block-container {{max-width:1540px;padding:1.45rem 2.35rem 4rem;}}
{sidebar_css}
[data-testid="stSidebar"] * {{color:var(--text);}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{color:var(--muted);}}
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
[data-testid="stNumberInput"] > div > div {{background:var(--surface2) !important;border-color:var(--line2) !important;border-radius:13px !important;box-shadow:none !important;}}
input,textarea {{color:var(--text) !important;-webkit-text-fill-color:var(--text) !important;}}
input::placeholder,textarea::placeholder {{color:var(--muted) !important;opacity:.75;}}
label,[data-testid="stWidgetLabel"] p {{color:var(--text2) !important;font-weight:670 !important;}}
[data-baseweb="popover"] > div,[role="listbox"] {{background:var(--surface) !important;color:var(--text) !important;}}
[data-testid="stSegmentedControl"] button {{border-color:var(--line) !important;background:var(--surface2) !important;color:var(--muted) !important;min-height:39px;font-weight:760;}}
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {{background:var(--text) !important;color:var(--bg) !important;border-color:var(--text) !important;}}
div[data-testid="stButton"] button,div[data-testid="stDownloadButton"] button,div[data-testid="stLinkButton"] a {{min-height:48px;border-radius:12px !important;font-weight:800 !important;letter-spacing:-.01em;transition:all .18s ease;}}
div[data-testid="stButton"] button[kind="primary"],div[data-testid="stDownloadButton"] button[kind="primary"] {{background:linear-gradient(105deg,var(--accent),var(--accent2)) !important;color:var(--button-text) !important;border:none !important;box-shadow:0 14px 34px rgba(100,130,255,.16) !important;}}
div[data-testid="stButton"] button[kind="primary"] p,div[data-testid="stDownloadButton"] button[kind="primary"] p {{color:var(--button-text) !important;}}
div[data-testid="stButton"] button:hover,div[data-testid="stDownloadButton"] button:hover,div[data-testid="stLinkButton"] a:hover {{transform:translateY(-1px);filter:brightness(1.04);}}
div[data-testid="stButton"] button[kind="secondary"],div[data-testid="stLinkButton"] a {{background:var(--surface) !important;color:var(--text) !important;border-color:var(--line2) !important;}}
div[data-testid="stVerticalBlockBorderWrapper"] {{border:1px solid var(--line) !important;border-radius:21px !important;background:linear-gradient(180deg,var(--surface),var(--surface2)) !important;box-shadow:var(--shadow2);overflow:hidden;}}
[data-testid="stExpander"] {{border:1px solid var(--line) !important;background:var(--surface2) !important;border-radius:13px !important;}}
[data-testid="stExpander"] details summary p {{color:var(--text2) !important;font-weight:720 !important;}}
[data-testid="stDataFrame"] {{border:1px solid var(--line);border-radius:15px;overflow:hidden;}}
[data-baseweb="tab-list"] {{gap:8px;border-bottom:1px solid var(--line);}}
[data-baseweb="tab"] {{color:var(--muted) !important;font-weight:740;}}
[aria-selected="true"][data-baseweb="tab"] {{color:var(--text) !important;}}
[data-baseweb="tab-highlight"] {{background:var(--accent) !important;}}
[data-testid="stProgress"] > div > div > div > div {{background:linear-gradient(90deg,var(--accent),var(--accent2)) !important;}}

.brand {{display:flex;align-items:center;gap:12px;}}
.brand-mark {{position:relative;width:41px;height:41px;border-radius:13px;background:linear-gradient(145deg,var(--accent),var(--accent2));box-shadow:0 13px 30px rgba(90,120,255,.18);}}
.brand-mark:before {{content:"";position:absolute;inset:9px;border:1.5px solid rgba(255,255,255,.9);border-radius:6px;}}
.brand-mark:after {{content:"";position:absolute;width:6px;height:6px;border-radius:2px;background:#fff;right:8px;top:8px;box-shadow:-11px 11px 0 rgba(255,255,255,.62);}}
.brand-name {{font-size:15px;font-weight:880;letter-spacing:-.025em;color:var(--text);line-height:1.15;}}
.brand-sub {{font-size:9px;font-weight:780;letter-spacing:.14em;color:var(--muted);text-transform:uppercase;margin-top:4px;}}

.nav-shell {{display:flex;align-items:center;justify-content:space-between;padding:5px 0 22px;border-bottom:1px solid var(--line);margin-bottom:28px;}}
.nav-links {{display:flex;gap:22px;color:var(--muted);font-size:11px;font-weight:720;align-items:center;}}
.nav-pill {{padding:8px 12px;border:1px solid var(--line);border-radius:99px;background:var(--surface);color:var(--text2);}}
.live-dot {{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px rgba(66,215,162,.11);margin-right:8px;}}

.landing-hero {{position:relative;border:1px solid var(--line);border-radius:30px;padding:70px 64px 64px;overflow:hidden;background:linear-gradient(125deg,var(--surface),var(--surface2));box-shadow:var(--shadow);}}
.landing-hero:before {{content:"";position:absolute;width:560px;height:560px;border-radius:50%;right:-190px;top:-280px;background:radial-gradient(circle,rgba(102,226,245,.18),transparent 66%);}}
.landing-hero:after {{content:"";position:absolute;width:520px;height:520px;border-radius:50%;right:40px;bottom:-410px;background:radial-gradient(circle,rgba(130,118,255,.18),transparent 65%);}}
.eyebrow {{display:flex;align-items:center;gap:10px;font-size:10px;text-transform:uppercase;letter-spacing:.16em;font-weight:830;color:var(--accent);position:relative;z-index:1;}}
.eyebrow-line {{width:28px;height:1px;background:linear-gradient(90deg,var(--accent),var(--accent2));}}
.landing-hero h1 {{font-size:clamp(3rem,6.2vw,6.5rem);line-height:.93;letter-spacing:-.062em;max-width:1050px;margin:24px 0 25px;color:var(--text);position:relative;z-index:1;font-weight:870;}}
.landing-hero h1 span {{background:linear-gradient(95deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent;}}
.landing-hero p {{max-width:780px;font-size:18px;line-height:1.65;color:var(--muted);position:relative;z-index:1;margin-bottom:0;}}
.hero-proof {{display:flex;gap:10px;flex-wrap:wrap;margin-top:35px;position:relative;z-index:1;}}
.proof-pill {{padding:10px 13px;border:1px solid var(--line);border-radius:99px;background:var(--glass);font-size:10px;font-weight:730;color:var(--text2);backdrop-filter:blur(12px);}}

.section-kicker {{font-size:9px;font-weight:850;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin-bottom:8px;}}
.section-title {{font-size:clamp(1.8rem,3.3vw,3.2rem);font-weight:850;letter-spacing:-.048em;color:var(--text);line-height:1.05;max-width:880px;}}
.section-copy {{font-size:13px;line-height:1.75;color:var(--muted);max-width:760px;margin-top:14px;}}
.section-space {{height:82px;}}

.value-grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:27px;}}
.value-card {{border:1px solid var(--line);border-radius:19px;padding:23px;background:var(--surface);box-shadow:var(--shadow2);min-height:178px;}}
.value-icon {{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;border:1px solid var(--line2);background:var(--surface2);color:var(--accent);font-size:16px;font-weight:850;}}
.value-title {{font-size:14px;font-weight:820;color:var(--text);letter-spacing:-.02em;margin:19px 0 8px;}}
.value-copy {{font-size:11px;line-height:1.68;color:var(--muted);}}

.split-panel {{display:grid;grid-template-columns:1.02fr .98fr;gap:16px;margin-top:28px;}}
.story-card {{border:1px solid var(--line);border-radius:23px;padding:30px;background:var(--surface);box-shadow:var(--shadow2);}}
.story-card.accent {{background:linear-gradient(145deg,var(--surface),rgba(102,226,245,.055));}}
.story-label {{font-size:9px;text-transform:uppercase;letter-spacing:.15em;color:var(--muted);font-weight:820;}}
.story-card h3 {{font-size:25px;line-height:1.12;letter-spacing:-.035em;color:var(--text);margin:15px 0 20px;}}
.story-row {{display:flex;gap:12px;margin:13px 0;color:var(--text2);font-size:11px;line-height:1.5;}}
.story-num {{width:25px;height:25px;flex:0 0 25px;border:1px solid var(--line2);border-radius:8px;display:grid;place-items:center;font-size:9px;color:var(--accent);font-weight:850;background:var(--surface2);}}

.workflow {{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:28px;}}
.workflow-card {{position:relative;border:1px solid var(--line);border-radius:20px;background:var(--surface);padding:25px;min-height:205px;overflow:hidden;}}
.workflow-card:after {{content:"";position:absolute;width:150px;height:150px;right:-75px;bottom:-95px;background:radial-gradient(circle,rgba(130,118,255,.13),transparent 70%);}}
.workflow-index {{font-size:10px;color:var(--accent);font-weight:850;letter-spacing:.12em;}}
.workflow-card h4 {{font-size:18px;color:var(--text);letter-spacing:-.025em;margin:24px 0 11px;}}
.workflow-card p {{font-size:11px;color:var(--muted);line-height:1.7;margin:0;}}

.output-shell {{border:1px solid var(--line);border-radius:25px;background:linear-gradient(135deg,var(--surface),var(--surface2));padding:31px;margin-top:28px;box-shadow:var(--shadow2);}}
.output-grid {{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:22px;}}
.output-item {{padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--surface);font-size:10px;color:var(--text2);font-weight:700;}}
.output-index {{color:var(--accent);font-size:8px;letter-spacing:.12em;margin-bottom:5px;font-weight:850;}}

.service-grid {{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:28px;}}
.service-card {{border:1px solid var(--line);border-radius:22px;padding:27px;background:var(--surface);min-height:245px;}}
.service-card.featured {{border-color:rgba(102,226,245,.28);background:linear-gradient(145deg,var(--surface),rgba(102,226,245,.055));box-shadow:0 18px 55px rgba(70,180,230,.08);}}
.service-tag {{font-size:9px;text-transform:uppercase;letter-spacing:.14em;color:var(--accent);font-weight:850;}}
.service-title {{font-size:19px;color:var(--text);font-weight:830;letter-spacing:-.03em;margin:15px 0 9px;}}
.service-copy {{font-size:11px;color:var(--muted);line-height:1.65;}}
.service-list {{font-size:10px;color:var(--text2);line-height:1.8;margin-top:18px;}}

.cta {{border:1px solid var(--line);border-radius:28px;padding:42px;margin-top:82px;background:linear-gradient(120deg,rgba(102,226,245,.085),rgba(130,118,255,.085)),var(--surface);position:relative;overflow:hidden;}}
.cta h2 {{font-size:clamp(2rem,4vw,3.8rem);letter-spacing:-.052em;line-height:1;color:var(--text);max-width:850px;margin:0 0 16px;}}
.cta p {{font-size:13px;line-height:1.7;color:var(--muted);max-width:720px;}}
.footer {{display:flex;justify-content:space-between;gap:20px;border-top:1px solid var(--line);padding:22px 0 2px;margin-top:64px;color:var(--muted);font-size:9px;letter-spacing:.03em;}}

.side-label {{font-size:9px;font-weight:850;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin:21px 0 9px;}}
.side-summary {{border:1px solid var(--line);background:var(--surface);border-radius:15px;padding:15px;margin-top:17px;}}
.side-row {{display:flex;justify-content:space-between;gap:10px;padding:5px 0;font-size:10px;}}
.side-row span:first-child {{color:var(--muted);font-weight:690;}} .side-row span:last-child {{color:var(--text);font-weight:780;text-align:right;}}
.side-rule {{height:1px;background:var(--line);margin:7px 0;}}
.system-line {{font-size:9px;color:var(--muted);margin:17px 2px 0;}}

.workspace-top {{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding:2px 0 19px;margin-bottom:24px;}}
.breadcrumb {{font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.14em;}}
.workspace-status {{font-size:9px;color:var(--text2);font-weight:700;}}
.workspace-hero {{border:1px solid var(--line);border-radius:24px;padding:31px 34px;background:linear-gradient(125deg,var(--surface),var(--surface2));box-shadow:var(--shadow2);margin-bottom:22px;}}
.workspace-hero h1 {{font-size:42px;line-height:1.02;letter-spacing:-.048em;color:var(--text);margin:12px 0 12px;}}
.workspace-hero p {{font-size:12px;line-height:1.7;color:var(--muted);max-width:780px;margin:0;}}
.panel-head {{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px;}}
.kicker {{font-size:9px;color:var(--accent);font-weight:850;text-transform:uppercase;letter-spacing:.14em;}}
.title {{font-size:21px;color:var(--text);font-weight:835;letter-spacing:-.035em;margin:7px 0 7px;}}
.copy {{font-size:11px;color:var(--muted);line-height:1.65;max-width:690px;}}
.mini-badge {{font-size:9px;color:var(--text2);font-weight:760;border:1px solid var(--line);border-radius:99px;padding:8px 10px;background:var(--surface2);white-space:nowrap;}}
.engine-card {{border:1px solid var(--line);border-radius:14px;padding:13px 15px;background:var(--surface2);display:flex;justify-content:space-between;gap:12px;align-items:center;margin:4px 0 17px;}}
.engine-label {{font-size:10px;color:var(--muted);font-weight:700;}} .engine-value {{font-size:10px;color:var(--text);font-weight:800;}}
.compat {{display:grid;grid-template-columns:1fr auto;gap:15px;align-items:center;border:1px solid var(--line);border-radius:15px;padding:15px 16px;background:var(--surface2);}}
.compat-title {{font-size:11px;color:var(--text);font-weight:820;}} .compat-copy {{font-size:9px;color:var(--muted);margin-top:4px;line-height:1.5;}}
.compat-score {{font-size:23px;color:var(--accent);font-weight:860;letter-spacing:-.04em;}}
.schema {{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.schema-item {{display:flex;gap:8px;align-items:center;padding:10px;border:1px solid var(--line);border-radius:11px;background:var(--surface2);font-size:9px;color:var(--text2);font-weight:690;}}
.schema-icon {{font-size:8px;color:var(--accent);font-weight:850;letter-spacing:.08em;}}
.metric-card {{border:1px solid var(--line);background:var(--surface);border-radius:17px;padding:16px 17px 14px;box-shadow:var(--shadow2);min-height:118px;}}
.metric-label {{font-size:9px;color:var(--muted);font-weight:780;letter-spacing:.06em;text-transform:uppercase;}}
.metric-value {{font-size:2rem;color:var(--text);font-weight:860;letter-spacing:-.045em;margin:7px 0 5px;}}
.metric-foot {{font-size:9px;color:var(--muted);font-weight:650;}} .metric-foot b {{color:var(--green);}}
.metric-track {{height:4px;background:var(--surface3);border-radius:99px;overflow:hidden;margin-top:12px;}}
.metric-fill {{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2));}}
.quality-item {{margin:13px 0 16px;}} .quality-head {{display:flex;justify-content:space-between;gap:12px;margin-bottom:7px;}}
.quality-label {{font-size:10px;font-weight:750;color:var(--text2);}} .quality-value {{font-size:10px;font-weight:830;color:var(--text);}}
.quality-track {{height:7px;background:var(--surface3);border-radius:99px;overflow:hidden;}} .quality-fill {{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:99px;}}
.note-box {{border:1px solid var(--line);border-radius:13px;padding:12px 14px;background:var(--surface2);font-size:9px;color:var(--muted);line-height:1.6;}}

@media(max-width:1050px){{.value-grid,.service-grid{{grid-template-columns:1fr 1fr;}}.workflow{{grid-template-columns:1fr;}}.split-panel{{grid-template-columns:1fr;}}.output-grid{{grid-template-columns:1fr 1fr;}}.landing-hero{{padding:46px 34px;}}}}
@media(max-width:760px){{.block-container{{padding:1.1rem .9rem 3rem;}}.value-grid,.service-grid{{grid-template-columns:1fr;}}.nav-links{{display:none;}}.landing-hero{{padding:36px 24px;}}.landing-hero h1{{font-size:3.2rem;}}.output-grid{{grid-template-columns:1fr;}}}}
</style>
        """,
        unsafe_allow_html=True,
    )


def go(view: str) -> None:
    st.query_params["view"] = view
    st.rerun()


def titleize(value: str) -> str:
    value = re.sub(r"[-_]+", " ", value.strip())
    return " ".join(part.capitalize() for part in value.split())


def infer_from_url(url: str) -> tuple[str, str]:
    try:
        path = [p for p in urlparse(url).path.split("/") if p]
        segment = titleize(path[-1]) if path else ""
        country = ""
        country_map = {"mexico": "México", "peru": "Perú", "panama": "Panamá", "argentina": "Argentina", "chile": "Chile", "colombia": "Colombia", "uruguay": "Uruguay", "brasil": "Brasil", "brazil": "Brasil"}
        for part in path[:2]:
            if part.casefold() in country_map:
                country = country_map[part.casefold()]
                break
        return segment, country
    except Exception:
        return "", ""


def rows_dataframe(records: list[CompanyRecord], include_control: bool) -> pd.DataFrame:
    columns = BASE_COLUMNS + (CONTROL_COLUMNS if include_control else [])
    return pd.DataFrame([{label: record.as_dict().get(key, "") for label, key in columns} for record in records])


def percent(count: int, total: int) -> int:
    return round((count / total) * 100) if total else 0


def panel_header(kicker: str, title: str, copy: str, badge: str | None = None) -> None:
    badge_html = f'<div class="mini-badge">{html.escape(badge)}</div>' if badge else ""
    st.markdown(
        f'<div class="panel-head"><div><div class="kicker">{html.escape(kicker)}</div><div class="title">{html.escape(title)}</div><div class="copy">{html.escape(copy)}</div></div>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str | int, pct: int, foot: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{html.escape(label)}</div><div class="metric-value">{html.escape(str(value))}</div><div class="metric-foot">{foot}</div><div class="metric-track"><div class="metric-fill" style="width:{max(0,min(100,pct))}%"></div></div></div>',
        unsafe_allow_html=True,
    )


def quality_bar(label: str, pct: int) -> None:
    st.markdown(
        f'<div class="quality-item"><div class="quality-head"><span class="quality-label">{html.escape(label)}</span><span class="quality-value">{pct}%</span></div><div class="quality-track"><div class="quality-fill" style="width:{pct}%"></div></div></div>',
        unsafe_allow_html=True,
    )


def brand_html(subtitle: str = "Directory Intelligence") -> str:
    return f'<div class="brand"><div class="brand-mark"></div><div><div class="brand-name">{html.escape(BRAND_NAME)}</div><div class="brand-sub">{html.escape(subtitle)}</div></div></div>'


def render_landing(theme_mode: str) -> None:
    inject_styles(theme_mode, landing=True)

    nav_left, nav_mid, nav_right = st.columns([1.15, 1.55, .72], vertical_alignment="center")
    with nav_left:
        st.markdown(brand_html(), unsafe_allow_html=True)
    with nav_mid:
        st.markdown('<div class="nav-links"><span>Producto</span><span>Cómo funciona</span><span>Casos de uso</span><span>Servicio</span><span class="nav-pill"><span class="live-dot"></span>Plataforma online</span></div>', unsafe_allow_html=True)
    with nav_right:
        a, b = st.columns([.9, 1.1])
        with a:
            selected = st.segmented_control("Tema", ["Claro", "Oscuro"], default=theme_mode, label_visibility="collapsed", key="landing_theme", width="stretch")
            if selected and selected != st.session_state.theme_mode:
                st.session_state.theme_mode = selected
                st.rerun()
        with b:
            if st.button("Abrir plataforma", type="primary", use_container_width=True):
                go("extractor")

    st.markdown(
        """
<section class="landing-hero">
  <div class="eyebrow"><span class="eyebrow-line"></span> Data acquisition infrastructure</div>
  <h1>Transformamos directorios en <span>datos B2B accionables.</span></h1>
  <p>Una plataforma de extracción y enriquecimiento que convierte listados empresariales públicos en bases estructuradas, trazables y listas para ventas, investigación de mercado y operaciones de datos.</p>
  <div class="hero-proof">
    <span class="proof-pill">Motor universal</span><span class="proof-pill">Enriquecimiento web</span><span class="proof-pill">Excel listo para usar</span><span class="proof-pill">Trazabilidad por registro</span><span class="proof-pill">Sin copiar y pegar</span>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )

    cta1, cta2, spacer = st.columns([.21, .21, .58])
    with cta1:
        if st.button("Probar extractor", type="primary", use_container_width=True, key="hero_cta"):
            go("extractor")
    with cta2:
        if CONTACT_EMAIL:
            st.link_button("Solicitar propuesta", f"mailto:{CONTACT_EMAIL}", use_container_width=True)

    st.markdown('<div class="section-space"></div><div class="section-kicker">El problema</div><div class="section-title">Los directorios tienen valor. El problema es convertirlos en una base utilizable.</div><div class="section-copy">Investigar empresa por empresa, copiar teléfonos, buscar correos, identificar el sitio oficial y luego limpiar el Excel consume horas y agrega errores. La plataforma automatiza esa capa operativa y deja el resultado en una estructura consistente.</div>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="value-grid">
  <div class="value-card"><div class="value-icon">01</div><div class="value-title">Descubrimiento automático</div><div class="value-copy">Analiza la estructura del directorio, identifica fichas empresariales y recorre la paginación sin depender de una única fuente.</div></div>
  <div class="value-card"><div class="value-icon">02</div><div class="value-title">Datos estructurados</div><div class="value-copy">Normaliza empresa, correo, teléfonos, ubicación, web, LinkedIn y segmento en un esquema listo para operar.</div></div>
  <div class="value-card"><div class="value-icon">03</div><div class="value-title">Enriquecimiento inteligente</div><div class="value-copy">Cuando un dato no aparece en la ficha, puede buscar el sitio oficial y completar contactos públicos disponibles.</div></div>
  <div class="value-card"><div class="value-icon">04</div><div class="value-title">Auditoría y trazabilidad</div><div class="value-copy">Conserva URL fuente, origen del dato, observaciones y estado de extracción para revisar la calidad de cada registro.</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-space"></div><div class="section-kicker">Antes / Después</div><div class="section-title">De una web difícil de explotar a una base comercial consistente.</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="split-panel">
  <div class="story-card"><div class="story-label">Proceso manual</div><h3>Horas navegando, copiando y validando.</h3><div class="story-row"><span class="story-num">1</span><span>Abrir cada empresa del directorio y copiar campos a mano.</span></div><div class="story-row"><span class="story-num">2</span><span>Buscar correo, web o LinkedIn cuando la ficha está incompleta.</span></div><div class="story-row"><span class="story-num">3</span><span>Corregir formatos, duplicados y datos sin fuente clara.</span></div></div>
  <div class="story-card accent"><div class="story-label">Directory Intelligence</div><h3>Una URL entra. Un dataset estructurado sale.</h3><div class="story-row"><span class="story-num">1</span><span>Pegás el segmento o listado que querés procesar.</span></div><div class="story-row"><span class="story-num">2</span><span>El motor detecta las empresas, extrae fichas y enriquece faltantes.</span></div><div class="story-row"><span class="story-num">3</span><span>Descargás un Excel trazable y listo para cruzar con CRM, BI o campañas.</span></div></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-space"></div><div class="section-kicker">Cómo funciona</div><div class="section-title">Tres pasos. Sin flujos técnicos para el usuario.</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="workflow">
  <div class="workflow-card"><div class="workflow-index">STEP 01</div><h4>Definí la fuente</h4><p>Pegá la URL del directorio, categoría o segmento. La plataforma identifica qué motor usar y analiza la compatibilidad.</p></div>
  <div class="workflow-card"><div class="workflow-index">STEP 02</div><h4>Elegí el alcance</h4><p>Procesá una cantidad concreta para validar o extraé todas las empresas detectadas. Podés activar enriquecimiento cuando necesites más cobertura.</p></div>
  <div class="workflow-card"><div class="workflow-index">STEP 03</div><h4>Descargá la inteligencia</h4><p>Revisá cobertura, buscá registros, auditá incidencias y exportá el dataset completo a Excel.</p></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-space"></div><div class="section-kicker">Output estandarizado</div><div class="section-title">Misma estructura, aunque cambie la fuente.</div><div class="section-copy">El objetivo no es solamente extraer texto: es transformar distintas fuentes en un modelo de datos único que se pueda integrar a procesos comerciales y analíticos.</div>', unsafe_allow_html=True)
    output_items = ["Nombre de empresa", "Correo", "Teléfono 1", "Teléfono 2", "Dirección", "Estado", "País", "Sitio web", "LinkedIn", "Segmento"]
    items = "".join(f'<div class="output-item"><div class="output-index">{i:02}</div>{html.escape(label)}</div>' for i, label in enumerate(output_items, 1))
    st.markdown(f'<div class="output-shell"><div class="output-grid">{items}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-space"></div><div class="section-kicker">Casos de uso</div><div class="section-title">Construido para equipos que necesitan convertir información dispersa en oportunidades.</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="service-grid">
  <div class="service-card"><div class="service-tag">Sales & Growth</div><div class="service-title">Prospección B2B</div><div class="service-copy">Construcción de universos de empresas por industria, geografía o asociación.</div><div class="service-list">• List building<br>• Market mapping<br>• Preparación para CRM<br>• Cobertura de contactos</div></div>
  <div class="service-card featured"><div class="service-tag">Data Operations</div><div class="service-title">Adquisición de datos</div><div class="service-copy">Automatización de tareas repetitivas de extracción, validación y estructuración.</div><div class="service-list">• Fuentes múltiples<br>• Trazabilidad<br>• Normalización<br>• Excel operativo</div></div>
  <div class="service-card"><div class="service-tag">Research</div><div class="service-title">Inteligencia de mercado</div><div class="service-copy">Transformación de directorios sectoriales en datasets comparables para investigación.</div><div class="service-list">• Mapeo competitivo<br>• Ecosistemas sectoriales<br>• Proveedores<br>• Segmentación geográfica</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="cta"><div class="section-kicker">Ready to extract</div><h2>Una fuente pública puede convertirse en una base lista para trabajar.</h2><p>Probá la plataforma con un directorio real. Empezá con una muestra pequeña, validá el resultado y escalá a todo el segmento cuando estés conforme.</p></div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([.24, .22, .54])
    with c1:
        if st.button("Abrir plataforma", type="primary", use_container_width=True, key="bottom_cta"):
            go("extractor")
    with c2:
        if CONTACT_EMAIL:
            st.link_button("Hablar con ventas", f"mailto:{CONTACT_EMAIL}", use_container_width=True)

    st.markdown(f'<div class="footer"><span>{html.escape(BRAND_NAME)} · {html.escape(PRODUCT_NAME)}</span><span>Extracción responsable de información pública · v{APP_VERSION}</span></div>', unsafe_allow_html=True)


def render_sidebar() -> dict:
    with st.sidebar:
        st.markdown(brand_html(f"Workspace · v{APP_VERSION}"), unsafe_allow_html=True)
        st.write("")
        if st.button("← Volver al inicio", use_container_width=True):
            go("home")

        st.markdown('<div class="side-label">Apariencia</div>', unsafe_allow_html=True)
        selected = st.segmented_control("Apariencia", ["Claro", "Oscuro"], default=st.session_state.theme_mode, label_visibility="collapsed", key="workspace_theme", width="stretch")
        if selected and selected != st.session_state.theme_mode:
            st.session_state.theme_mode = selected
            st.rerun()

        st.markdown('<div class="side-label">Volumen de extracción</div>', unsafe_allow_html=True)
        volume_mode = st.segmented_control("Volumen", ["Todas", "Cantidad"], default="Todas", label_visibility="collapsed", width="stretch", key="volume_mode") or "Todas"
        if volume_mode == "Cantidad":
            quantity = int(st.number_input("Cantidad de empresas", min_value=1, max_value=50000, value=100, step=25, help="La extracción se detiene al alcanzar este número."))
            max_records = quantity
            volume_summary = f"{quantity:,}".replace(",", ".") + " empresas"
        else:
            max_records = 0
            volume_summary = "Todas las empresas"

        st.markdown('<div class="side-label">Profundidad</div>', unsafe_allow_html=True)
        extraction_mode = st.selectbox("Profundidad", ["Directorio", "Enriquecida"], index=0, label_visibility="collapsed", help="Enriquecida intenta completar sitio web, contactos y LinkedIn cuando faltan.")
        find_site = crawl_site = find_linkedin = extraction_mode == "Enriquecida"

        with st.expander("Compatibilidad avanzada"):
            st.caption("Usalo solamente si el motor universal no detecta correctamente las fichas.")
            company_selector = st.text_input("Selector CSS de empresa", placeholder="Ej.: .company-card a", help="Selector CSS del enlace o tarjeta que lleva a la ficha de cada empresa.")
            next_selector = st.text_input("Selector CSS de siguiente página", placeholder="Ej.: a.next", help="Opcional. Permite indicar manualmente el botón de paginación.")

        with st.expander("Configuración técnica"):
            include_control = st.toggle("Trazabilidad de fuentes", value=True)
            delay_seconds = st.slider("Pausa entre solicitudes", 0.0, 3.0, 0.25, 0.05)

        st.markdown(
            f'<div class="side-summary"><div class="side-row"><span>Alcance</span><span>{html.escape(volume_summary)}</span></div><div class="side-rule"></div><div class="side-row"><span>Modo</span><span>{html.escape(extraction_mode)}</span></div><div class="side-rule"></div><div class="side-row"><span>Salida</span><span>Excel · 10 campos</span></div></div><div class="system-line"><span class="live-dot"></span>Sistema disponible</div>',
            unsafe_allow_html=True,
        )

    return {
        "max_records": max_records,
        "volume_summary": volume_summary,
        "extraction_mode": extraction_mode,
        "find_site": find_site,
        "crawl_site": crawl_site,
        "find_linkedin": find_linkedin,
        "include_control": include_control,
        "delay_seconds": delay_seconds,
        "company_selector": company_selector,
        "next_selector": next_selector,
    }


def render_workspace() -> None:
    cfg = render_sidebar()
    inject_styles(st.session_state.theme_mode, landing=False)

    st.markdown('<div class="workspace-top"><div class="breadcrumb">Data Operations / Universal Extraction</div><div class="workspace-status"><span class="live-dot"></span>Ready for extraction</div></div>', unsafe_allow_html=True)
    st.markdown('<section class="workspace-hero"><div class="eyebrow"><span class="eyebrow-line"></span> Universal Directory Engine</div><h1>Una interfaz. Múltiples directorios.</h1><p>Ingresá la URL de un directorio público, categoría o segmento. El sistema utiliza un adaptador optimizado cuando reconoce la fuente y, para el resto, aplica detección automática de fichas empresariales y paginación.</p></section>', unsafe_allow_html=True)

    main_col, info_col = st.columns([1.7, .72], gap="large")
    with main_col:
        with st.container(border=True):
            panel_header("Nueva extracción", "Definí la fuente", "Pegá la URL exacta del listado que querés procesar. Puede ser una categoría, asociación, cámara, marketplace B2B o directorio sectorial.", "Motor automático")
            source_url = st.text_input("URL del directorio / segmento", value=st.session_state.get("source_url", DEFAULT_URL), placeholder="https://sitio.com/directorio/segmento", icon=":material/link:", key="source_url")
            inferred_segment, inferred_country = infer_from_url(source_url)
            c1, c2 = st.columns(2)
            with c1:
                segmento = st.text_input("Segmento", value=st.session_state.get("segment_input", inferred_segment), placeholder="Ej.: Agentes Navieros", icon=":material/category:", key="segment_input")
            with c2:
                pais_forzado = st.text_input("País", value=st.session_state.get("country_input", inferred_country), placeholder="Ej.: México", icon=":material/public:", key="country_input")

            profile = source_profile(source_url)
            st.markdown(f'<div class="engine-card"><span class="engine-label">Motor seleccionado</span><span class="engine-value">{html.escape(profile.label)}</span></div>', unsafe_allow_html=True)

            analyze_col, spacer = st.columns([.34, .66])
            with analyze_col:
                analyze_clicked = st.button("Analizar compatibilidad", use_container_width=True, icon=":material/radar:")
            if analyze_clicked:
                try:
                    session = build_session()
                    with st.spinner("Analizando estructura del directorio…"):
                        st.session_state.compatibility = analyze_source(session, source_url, company_selector=cfg["company_selector"])
                        st.session_state.compatibility_url = source_url
                except Exception as exc:
                    st.session_state.compatibility = {"error": f"{type(exc).__name__}: {exc}"}
                    st.session_state.compatibility_url = source_url

            comp = st.session_state.compatibility if st.session_state.compatibility_url == source_url else None
            if comp:
                if comp.get("error"):
                    st.warning(comp["error"])
                else:
                    detail = comp["engine"]
                    if comp.get("companies_on_page") is not None:
                        detail += f" · {comp['companies_on_page']} fichas candidatas en la primera página"
                    if comp.get("pagination_detected"):
                        detail += " · paginación detectada"
                    st.markdown(f'<div class="compat"><div><div class="compat-title">Compatibilidad {html.escape(comp["level"])}</div><div class="compat-copy">{html.escape(detail)}</div></div><div class="compat-score">{comp["score"]}%</div></div>', unsafe_allow_html=True)

            st.write("")
            st.markdown('<div class="note-box">El motor universal funciona mejor con directorios públicos donde las empresas tienen fichas o enlaces individuales. Sitios con login, CAPTCHA, bloqueos anti-bot o contenido renderizado exclusivamente con JavaScript pueden requerir un adaptador específico.</div>', unsafe_allow_html=True)
            st.write("")
            start = st.button("Iniciar extracción", type="primary", icon=":material/arrow_forward:", use_container_width=True)

    with info_col:
        with st.container(border=True):
            panel_header("Output", "Un solo modelo de datos", "La fuente puede cambiar; la estructura final se mantiene estable.")
            schema_items = [("01", "Nombre de empresa"), ("02", "Correo"), ("03", "Teléfono 1"), ("04", "Teléfono 2"), ("05", "Dirección"), ("06", "Estado"), ("07", "País"), ("08", "Sitio web"), ("09", "LinkedIn"), ("10", "Segmento")]
            schema_html = "".join(f'<div class="schema-item"><span class="schema-icon">{i}</span>{html.escape(label)}</div>' for i, label in schema_items)
            st.markdown(f'<div class="schema">{schema_html}</div>', unsafe_allow_html=True)

    if start:
        try:
            clean_url = validate_source_url(source_url)
            if not segmento.strip():
                raise ValueError("Ingresá un nombre de segmento para identificar la extracción.")

            session = build_session()
            st.write("")
            with st.container(border=True):
                panel_header("Procesamiento", "Extracción en curso", "Estamos descubriendo fichas, recorriendo el directorio y estructurando los registros.", cfg["volume_summary"])
                with st.status("Preparando motor…", expanded=True) as status:
                    status_line = st.empty()
                    progress_bar = st.progress(0, text="Analizando la fuente…")

                    def listing_progress(message: str) -> None:
                        status_line.markdown(f"**Descubrimiento:** {message}")

                    profile, companies = discover_companies(
                        session,
                        clean_url,
                        max_records=int(cfg["max_records"]),
                        delay_seconds=float(cfg["delay_seconds"]),
                        progress=listing_progress,
                        company_selector=cfg["company_selector"],
                        next_selector=cfg["next_selector"],
                    )
                    if not companies:
                        raise RuntimeError("No se encontraron empresas en la fuente.")

                    records: list[CompanyRecord] = []
                    total = len(companies)
                    for idx, company in enumerate(companies, start=1):
                        display_name = getattr(company, "listing_text", "") or company.url
                        status_line.markdown(f"**{idx}/{total}** · Extrayendo **{display_name}**")
                        record = fetch_company(session, profile, company, segmento.strip(), delay_seconds=float(cfg["delay_seconds"]))
                        if not record.pais:
                            record.pais = pais_forzado.strip()

                        if record.estado_extraccion == "OK" and (cfg["find_site"] or cfg["crawl_site"] or cfg["find_linkedin"]):
                            status_line.markdown(f"**{idx}/{total}** · Enriqueciendo **{record.nombre_empresa or display_name}**")
                            record = enrich_record(session, record, find_site=cfg["find_site"], crawl_site=cfg["crawl_site"], find_linkedin_search=cfg["find_linkedin"])

                        records.append(record)
                        progress_bar.progress(idx / total, text=f"Procesadas {idx} de {total}")

                    st.session_state.records = records
                    st.session_state.excel_bytes = records_to_excel(records, include_control=cfg["include_control"])
                    st.session_state.last_segment = segmento.strip()
                    st.session_state.last_mode = cfg["extraction_mode"]
                    st.session_state.last_volume = cfg["volume_summary"]
                    st.session_state.last_source = profile.label
                    status.update(label=f"Extracción completada · {len(records)} empresas", state="complete", expanded=False)
        except Exception as exc:
            st.error(f"No se pudo completar la extracción: {type(exc).__name__}: {exc}", icon=":material/error:")

    records: list[CompanyRecord] = st.session_state.records
    if records:
        st.write("")
        panel_header("Intelligence snapshot", "Resumen de ejecución", "Cobertura de los campos más importantes y acceso directo al dataset procesado.", st.session_state.last_source or st.session_state.last_volume)
        total = len(records)
        ok = sum(r.estado_extraccion == "OK" for r in records)
        with_email = sum(bool(r.correo) for r in records)
        with_phone = sum(bool(r.telefono_1) for r in records)
        with_site = sum(bool(r.sitio_web) for r in records)
        with_linkedin = sum(bool(r.linkedin) for r in records)

        m1, m2, m3, m4, m5 = st.columns(5, gap="small")
        with m1: metric_card("Empresas", total, percent(ok, total), f"<b>{percent(ok,total)}%</b> procesadas OK")
        with m2: metric_card("Correo", with_email, percent(with_email, total), f"<b>{percent(with_email,total)}%</b> cobertura")
        with m3: metric_card("Teléfono", with_phone, percent(with_phone, total), f"<b>{percent(with_phone,total)}%</b> cobertura")
        with m4: metric_card("Sitio web", with_site, percent(with_site, total), f"<b>{percent(with_site,total)}%</b> cobertura")
        with m5: metric_card("LinkedIn", with_linkedin, percent(with_linkedin, total), f"<b>{percent(with_linkedin,total)}%</b> cobertura")

        st.write("")
        data_col, quality_col = st.columns([1.72, .55], gap="large")
        with data_col:
            with st.container(border=True):
                panel_header("Dataset", "Base procesada", "Buscá, revisá y descargá el resultado.")
                df = rows_dataframe(records, cfg["include_control"])
                search = st.text_input("Buscar en resultados", placeholder="Empresa, correo, estado, país…", icon=":material/search:", key="results_search")
                shown = df
                if search.strip():
                    mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False, regex=False)).any(axis=1)
                    shown = df[mask]
                st.dataframe(shown, hide_index=True, use_container_width=True, height=430)
                filename_segment = re.sub(r"[^A-Za-z0-9_-]+", "_", st.session_state.last_segment).strip("_") or "empresas"
                st.download_button("Descargar Excel", data=st.session_state.excel_bytes, file_name=f"{filename_segment}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", icon=":material/download:", use_container_width=True)

        with quality_col:
            with st.container(border=True):
                panel_header("Data quality", "Cobertura", "Lectura rápida de completitud.")
                quality_bar("Correo", percent(with_email, total))
                quality_bar("Teléfono", percent(with_phone, total))
                quality_bar("Sitio web", percent(with_site, total))
                quality_bar("LinkedIn", percent(with_linkedin, total))
                errors = total - ok
                st.markdown(f'<div class="note-box"><b style="color:var(--text)">{errors}</b> registros con incidencia de extracción. Activá la trazabilidad para ver el detalle en el Excel.</div>', unsafe_allow_html=True)

        with st.expander("Auditoría y errores"):
            audit = pd.DataFrame([r.as_dict() for r in records])
            cols = ["nombre_empresa", "url_fuente", "estado_extraccion", "observaciones", "fuente_correo", "fuente_telefono", "fuente_sitio_web", "fuente_linkedin"]
            st.dataframe(audit[[c for c in cols if c in audit.columns]], hide_index=True, use_container_width=True)


init_state()
view = st.query_params.get("view", "home")
if isinstance(view, list):
    view = view[0] if view else "home"

if view == "extractor":
    render_workspace()
else:
    render_landing(st.session_state.theme_mode)
