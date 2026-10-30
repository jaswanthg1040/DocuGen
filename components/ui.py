"""Reusable UI helpers: theme CSS and small HTML components.

Only static strings and html.escape()d values are ever passed to
unsafe_allow_html, so document content can never inject markup.
"""
from __future__ import annotations

import html

import streamlit as st

LIGHT = {
    "bg": "linear-gradient(160deg,#eef2ff 0%,#f5f3ff 45%,#ffffff 100%)",
    "sidebar": "linear-gradient(180deg,#ffffff 0%,#eef2ff 100%)",
    "card": "#ffffff", "input": "#ffffff", "text": "#1e1b4b", "muted": "#5b6280",
    "border": "#dbe0ff", "hover": "#eef2ff", "primary": "#4f46e5", "shadow": "0 6px 20px rgba(79,70,229,.10)",
}
DARK = {
    "bg": "linear-gradient(160deg,#0b0c1f 0%,#17133a 50%,#10112a 100%)",
    "sidebar": "linear-gradient(180deg,#12132b 0%,#191648 100%)",
    "card": "#1a1b3a", "input": "#12132b", "text": "#e8eaff", "muted": "#a3a9d6",
    "border": "#35377a", "hover": "#252761", "primary": "#8b83ff", "shadow": "0 6px 20px rgba(0,0,0,.35)",
}

BASE_CSS = """
.stApp{background:var(--dg-bg);background-attachment:fixed;color:var(--dg-text);
  font-family:'Inter','Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif;}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2rem;padding-bottom:3rem;max-width:1180px;}
[data-testid="stSidebar"]{background:var(--dg-sidebar);border-right:1px solid var(--dg-border);}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6,.stApp p,.stApp li,
.stApp label,.stApp [data-testid="stWidgetLabel"] p,.stApp summary{color:var(--dg-text);}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p{color:var(--dg-muted);}
.stApp button p,.stApp button span{color:inherit !important;}

/* Inputs */
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"],.stApp [data-baseweb="textarea"]{
  background:var(--dg-input) !important;border-radius:12px !important;}
.stApp .stTextInput input,.stApp .stTextArea textarea{background:var(--dg-input) !important;
  color:var(--dg-text) !important;-webkit-text-fill-color:var(--dg-text);}
.stApp .stTextInput input::placeholder,.stApp .stTextArea textarea::placeholder{color:var(--dg-muted) !important;opacity:.8;}
.stApp [data-baseweb="input"],.stApp [data-baseweb="textarea"]{border:1px solid var(--dg-border) !important;}
.stApp [data-baseweb="select"]>div{background:var(--dg-input) !important;border-radius:12px !important;
  border-color:var(--dg-border) !important;}
.stApp [data-baseweb="select"] *{color:var(--dg-text) !important;}
[data-baseweb="popover"] [role="listbox"],[data-baseweb="popover"] ul,[data-baseweb="menu"]{
  background:var(--dg-card) !important;}
[data-baseweb="popover"] li,[data-baseweb="popover"] li *{color:var(--dg-text) !important;}
[data-baseweb="popover"] li:hover{background:var(--dg-hover) !important;}

/* Buttons */
.stApp .stButton>button,.stApp .stDownloadButton>button{width:100%;border-radius:12px;
  border:1px solid var(--dg-border);background:var(--dg-card);color:var(--dg-text);font-weight:600;
  padding:.5rem 1rem;transition:transform .12s ease,box-shadow .12s ease;}
.stApp .stButton>button:hover,.stApp .stDownloadButton>button:hover{transform:translateY(-1px);
  border-color:var(--dg-primary);box-shadow:var(--dg-shadow);color:var(--dg-primary);}
.stApp .stButton>button[kind="primary"],.stApp .stDownloadButton>button[kind="primary"],
.stApp button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#4f46e5,#7c3aed);
  color:#ffffff !important;border:none;}
.stApp .stButton>button[kind="primary"]:hover,.stApp .stDownloadButton>button[kind="primary"]:hover,
.stApp button[data-testid="stBaseButton-primary"]:hover{color:#ffffff !important;filter:brightness(1.08);}
.stApp button:focus-visible{outline:3px solid #a5b4fc;outline-offset:2px;}

/* Tabs, expanders, alerts */
.stApp .stTabs [data-baseweb="tab"]{color:var(--dg-muted);font-weight:600;}
.stApp .stTabs [aria-selected="true"]{color:var(--dg-primary) !important;}
.stApp [data-testid="stExpander"]{background:var(--dg-card);border:1px solid var(--dg-border);border-radius:14px;}
.stApp [data-testid="stAlert"]{border-radius:12px;}

/* Sidebar navigation */
.dg-brand{display:flex;align-items:center;gap:.65rem;padding:.4rem .2rem 1rem;}
.dg-logo{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#4f46e5,#7c3aed);font-size:1.3rem;}
.dg-brand b{display:block;font-size:1.15rem;color:var(--dg-text);}
.dg-brand small{color:var(--dg-muted);}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.25rem;}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:.55rem .85rem;border-radius:12px;width:100%;cursor:pointer;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:var(--dg-hover);}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){
  background:linear-gradient(135deg,#4f46e5,#7c3aed);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) *{color:#ffffff !important;}

/* Components */
.stApp .dg-hero{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#3b82f6 100%);border-radius:24px;
  padding:2.2rem 2rem;box-shadow:0 12px 32px rgba(79,70,229,.30);margin-bottom:1.2rem;}
.stApp .dg-hero h1{color:#ffffff;margin:0 0 .35rem;font-size:2.2rem;line-height:1.2;padding:0;}
.stApp .dg-hero p{color:rgba(255,255,255,.93);margin:0;font-size:1.05rem;}
.stApp .dg-pagehead{margin-bottom:1rem;}
.stApp .dg-pagehead h2{margin:0;padding:0;font-size:1.7rem;}
.stApp .dg-pagehead p{margin:.2rem 0 0;color:var(--dg-muted);}
.dg-stat{background:var(--dg-card);border:1px solid var(--dg-border);border-radius:18px;padding:1.1rem 1.2rem;
  box-shadow:var(--dg-shadow);height:100%;}
.stApp .dg-stat .v{font-size:2rem;font-weight:800;color:var(--dg-primary);line-height:1.1;}
.stApp .dg-stat .l{font-weight:600;color:var(--dg-text);}
.stApp .dg-stat .h{font-size:.85rem;color:var(--dg-muted);}
.dg-empty{text-align:center;background:var(--dg-card);border:2px dashed var(--dg-border);border-radius:20px;
  padding:2.2rem 1rem;margin:.6rem 0 1rem;}
.stApp .dg-empty .i{font-size:2.6rem;}
.stApp .dg-empty h3{margin:.3rem 0;}
.stApp .dg-empty p{color:var(--dg-muted);margin:0;}
.stApp .dg-doc-title{font-weight:700;font-size:1.05rem;word-break:break-word;}
.stApp .dg-doc-meta{font-size:.85rem;color:var(--dg-muted);}
.stApp .dg-doc-desc{font-size:.9rem;color:var(--dg-muted);margin-top:.15rem;}
.stApp .dg-tpl-icon{font-size:2rem;}
.stApp .dg-chip{display:inline-block;background:var(--dg-hover);color:var(--dg-primary);border-radius:999px;
  padding:.05rem .65rem;font-size:.75rem;font-weight:700;margin:.3rem .3rem 0 0;}
.stApp [data-testid="stFileUploaderDropzone"]{background:var(--dg-input);border:1px dashed var(--dg-border);
  border-radius:12px;}
.stApp [data-testid="stFileUploaderDropzone"] *{color:var(--dg-text);}
.stApp [data-testid="stFileUploaderDropzone"] button{color:var(--dg-text) !important;}
.dg-badge{display:inline-block;padding:.2rem .7rem;border-radius:999px;font-size:.8rem;font-weight:700;
  background:#dcfce7;color:#166534;}
.dg-badge.warn{background:#fef3c7;color:#92400e;}
.stApp .dg-badge{color:#166534;}
.stApp .dg-badge.warn{color:#92400e;}
[class*="st-key-dgcard"]{background:var(--dg-card);border:1px solid var(--dg-border);border-radius:18px;
  padding:1rem 1.1rem;box-shadow:var(--dg-shadow);margin-bottom:.4rem;}
.st-key-preview_paper{background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;padding:2rem 2.2rem;
  min-height:300px;box-shadow:var(--dg-shadow);}
.stApp .st-key-preview_paper *{color:#1f2937 !important;}
.stApp .st-key-preview_paper h1{color:#3730a3 !important;}

@media (max-width:640px){
  .block-container{padding:1rem .8rem 2rem;}
  .stApp .dg-hero{padding:1.4rem 1.1rem;}
  .stApp .dg-hero h1{font-size:1.6rem;}
  .st-key-preview_paper{padding:1.1rem;}
}
"""

DARK_EXTRA = """
.stApp [data-testid="stAlert"]{background:rgba(139,131,255,.16);}
.stApp [data-testid="stAlert"] *{color:var(--dg-text) !important;}
.stApp .stTabs [data-baseweb="tab-border"]{background:var(--dg-border);}
.stApp hr{border-color:var(--dg-border);}
"""


def inject_css(theme: str) -> None:
    palette = DARK if theme == "dark" else LIGHT
    variables = ":root{" + "".join(f"--dg-{k}:{v};" for k, v in palette.items()) + "}"
    css = variables + BASE_CSS + (DARK_EXTRA if theme == "dark" else "")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def sidebar_brand() -> None:
    st.markdown(
        '<div class="dg-brand"><div class="dg-logo">📄</div>'
        "<div><b>DocuGen</b><small>AI Document Studio</small></div></div>",
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="dg-hero"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    sub = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="dg-pagehead"><h2>{html.escape(icon)} {html.escape(title)}</h2>{sub}</div>',
        unsafe_allow_html=True,
    )


def stat_card(icon: str, label: str, value: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="dg-stat"><div class="l">{html.escape(icon)} {html.escape(label)}</div>'
        f'<div class="v">{html.escape(str(value))}</div><div class="h">{html.escape(hint)}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(icon: str, title: str, message: str) -> None:
    st.markdown(
        f'<div class="dg-empty"><div class="i">{html.escape(icon)}</div>'
        f"<h3>{html.escape(title)}</h3><p>{html.escape(message)}</p></div>",
        unsafe_allow_html=True,
    )


def doc_summary(title: str, meta: str, description: str = "", tags: str = "", pinned: bool = False) -> None:
    desc = f'<div class="dg-doc-desc">{html.escape(description)}</div>' if description else ""
    chips = "".join(f'<span class="dg-chip">{html.escape(t)}</span>' for t in tags.split(",") if t)
    icon = "⭐" if pinned else "📄"
    st.markdown(
        f'<div class="dg-doc-title">{icon} {html.escape(title)}</div>'
        f'<div class="dg-doc-meta">{html.escape(meta)}</div>{desc}'
        + (f"<div>{chips}</div>" if chips else ""),
        unsafe_allow_html=True,
    )


def badge(text: str, warn: bool = False) -> None:
    cls = "dg-badge warn" if warn else "dg-badge"
    st.markdown(f'<span class="{cls}">{html.escape(text)}</span>', unsafe_allow_html=True)
