"""Obsidian Index theme for MedLit Agent dashboard.

Aesthetic: amber-gold accents on near-black, with Cormorant SC small-caps
headers, Crimson Pro body text, and Azeret Mono for all data / badges.
Evokes a high-end scientific reference book reimagined as a dark terminal.
"""

# ── CSS ─────────────────────────────────────────────────────────────────────

THEME_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   OBSIDIAN INDEX  ·  MedLit Agent
   Fonts  : Cormorant SC (headings) · Crimson Pro (body) · Azeret Mono (data)
   Palette: amber / teal / sage / rose on near-black
═══════════════════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Cormorant+SC:wght@300;400;500;600;700&family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Azeret+Mono:wght@300;400;500;600&display=swap');

/* ── Variables ──────────────────────────────────────────────────────────── */
:root {
  --bg:             #09090d;
  --bg-card:        #0f1018;
  --bg-card-2:      #141622;
  --bg-input:       #0d0e18;
  --bg-sidebar:     #0a0a11;

  --accent:         #c9a84c;
  --accent-dim:     #8a6e2e;
  --accent-glow:    rgba(201, 168, 76, 0.09);
  --accent-border:  rgba(201, 168, 76, 0.28);

  --teal:           #4aacc8;
  --teal-dim:       rgba(74, 172, 200, 0.13);
  --teal-border:    rgba(74, 172, 200, 0.30);

  --sage:           #52b788;
  --sage-dim:       rgba(82, 183, 136, 0.13);

  --rose:           #e05c5c;
  --rose-dim:       rgba(224, 92, 92, 0.13);

  --amber:          #e8894a;
  --amber-dim:      rgba(232, 137, 74, 0.13);

  --text:           #dde1eb;
  --text-dim:       #8b91ab;
  --text-faint:     #3d4160;

  --border:         #17182a;
  --border-2:       #22243a;

  --font-head:  'Cormorant SC', 'Palatino Linotype', Georgia, serif;
  --font-body:  'Crimson Pro', 'Palatino Linotype', Georgia, serif;
  --font-mono:  'Azeret Mono', 'Courier New', monospace;
  --r:          3px;
}

/* ── Base ───────────────────────────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main {
  background-color: var(--bg) !important;
  color: var(--text) !important;
}

/* Subtle dot-grid texture */
.stApp {
  background-image:
    radial-gradient(circle, rgba(34, 36, 58, 0.55) 1px, transparent 1px) !important;
  background-size: 28px 28px !important;
  background-attachment: fixed !important;
}

/* Faint top-center glow */
[data-testid="stAppViewContainer"]::before {
  content: '';
  position: fixed;
  top: -120px;
  left: 50%;
  transform: translateX(-50%);
  width: 600px;
  height: 250px;
  background: radial-gradient(ellipse, rgba(201,168,76,0.04) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* ── Header bar ─────────────────────────────────────────────────────────── */
[data-testid="stHeader"] {
  background: rgba(9, 9, 13, 0.90) !important;
  backdrop-filter: blur(10px) !important;
  border-bottom: 1px solid var(--border-2) !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child {
  background: var(--bg-sidebar) !important;
  border-right: 1px solid var(--border-2) !important;
}

[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNav"] a span {
  font-family: var(--font-body) !important;
  font-size: 1rem !important;
  color: var(--text-dim) !important;
  letter-spacing: 0.02em !important;
  transition: color 0.18s ease !important;
  border-radius: var(--r) !important;
}

[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNav"] a[aria-current="page"] {
  color: var(--accent) !important;
  background: var(--accent-glow) !important;
}

/* ── Typography ─────────────────────────────────────────────────────────── */
h1 {
  font-family: var(--font-head) !important;
  font-weight: 500 !important;
  font-size: 2.3rem !important;
  letter-spacing: 0.12em !important;
  color: var(--text) !important;
  border-bottom: 1px solid var(--border-2) !important;
  padding-bottom: 0.55rem !important;
  margin-bottom: 1.6rem !important;
  line-height: 1.2 !important;
}

h2 {
  font-family: var(--font-head) !important;
  font-weight: 500 !important;
  font-size: 1.55rem !important;
  letter-spacing: 0.09em !important;
  color: var(--accent) !important;
  margin-bottom: 0.8rem !important;
}

h3 {
  font-family: var(--font-head) !important;
  font-weight: 400 !important;
  font-size: 1.1rem !important;
  letter-spacing: 0.06em !important;
  color: var(--text-dim) !important;
}

p, li {
  font-family: var(--font-body) !important;
  font-size: 1.05rem !important;
  line-height: 1.75 !important;
  color: var(--text) !important;
}

/* ── Markdown ───────────────────────────────────────────────────────────── */
.stMarkdown p,
.stMarkdown li {
  font-family: var(--font-body) !important;
  font-size: 1.05rem !important;
  line-height: 1.75 !important;
}

.stMarkdown code, code {
  font-family: var(--font-mono) !important;
  font-size: 0.82rem !important;
  background: var(--bg-card-2) !important;
  color: var(--teal) !important;
  padding: 0.15em 0.45em !important;
  border-radius: 2px !important;
  border: 1px solid var(--border-2) !important;
}

/* ── Form labels ────────────────────────────────────────────────────────── */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
label {
  font-family: var(--font-mono) !important;
  font-size: 0.67rem !important;
  letter-spacing: 0.17em !important;
  text-transform: uppercase !important;
  color: var(--text-faint) !important;
  font-weight: 400 !important;
}

/* Checkboxes / radios: restore normal label style */
.stCheckbox [data-testid="stWidgetLabel"] p,
.stRadio [data-testid="stWidgetLabel"] p {
  font-family: var(--font-body) !important;
  font-size: 1rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  color: var(--text-dim) !important;
}

/* ── Metrics ────────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-2) !important;
  border-top: 2px solid var(--accent-border) !important;
  border-radius: var(--r) !important;
  padding: 1rem 1.25rem !important;
}

[data-testid="stMetricLabel"] label,
[data-testid="stMetricLabel"] p {
  font-family: var(--font-mono) !important;
  font-size: 0.64rem !important;
  letter-spacing: 0.20em !important;
  text-transform: uppercase !important;
  color: var(--text-faint) !important;
}

[data-testid="stMetricValue"] {
  font-family: var(--font-mono) !important;
  color: var(--teal) !important;
  font-size: 2.1rem !important;
  font-weight: 300 !important;
}

[data-testid="stMetricDelta"] {
  font-family: var(--font-mono) !important;
  font-size: 0.70rem !important;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.stButton > button {
  font-family: var(--font-mono) !important;
  font-size: 0.70rem !important;
  letter-spacing: 0.15em !important;
  text-transform: uppercase !important;
  background: transparent !important;
  border: 1px solid var(--border-2) !important;
  color: var(--text-dim) !important;
  border-radius: var(--r) !important;
  padding: 0.45rem 1.1rem !important;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease !important;
}

.stButton > button:hover {
  border-color: var(--accent-border) !important;
  color: var(--accent) !important;
  background: var(--accent-glow) !important;
}

.stButton > button[kind="primary"] {
  border-color: var(--accent-border) !important;
  color: var(--accent) !important;
  background: var(--accent-glow) !important;
}

.stButton > button[kind="primary"]:hover {
  background: rgba(201, 168, 76, 0.18) !important;
  border-color: var(--accent) !important;
}

/* ── Link buttons ───────────────────────────────────────────────────────── */
.stLinkButton a {
  font-family: var(--font-mono) !important;
  font-size: 0.70rem !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
  color: var(--teal) !important;
  border-color: var(--teal-border) !important;
  border-radius: var(--r) !important;
  transition: background 0.18s ease !important;
}

.stLinkButton a:hover {
  background: var(--teal-dim) !important;
}

/* ── Inputs ─────────────────────────────────────────────────────────────── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
  background: var(--bg-input) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--r) !important;
  color: var(--text) !important;
  font-family: var(--font-body) !important;
  font-size: 1rem !important;
  transition: border-color 0.18s ease !important;
}

.stTextInput input:focus,
.stTextArea textarea:focus {
  border-color: var(--accent-border) !important;
  box-shadow: 0 0 0 2px var(--accent-glow) !important;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
  color: var(--text-faint) !important;
  font-style: italic;
}

/* ── Selectbox ──────────────────────────────────────────────────────────── */
.stSelectbox > div > div,
.stSelectbox [data-baseweb="select"] > div {
  background: var(--bg-input) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--r) !important;
  color: var(--text) !important;
  font-family: var(--font-body) !important;
}

/* ── Slider ─────────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] {
  font-family: var(--font-mono) !important;
  font-size: 0.65rem !important;
  color: var(--text-faint) !important;
}

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--r) !important;
}

[data-testid="stExpander"] summary {
  font-family: var(--font-body) !important;
  font-size: 1rem !important;
  color: var(--text) !important;
  letter-spacing: 0.02em !important;
}

[data-testid="stExpander"] summary:hover {
  color: var(--accent) !important;
}

/* ── Containers with borders ────────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--border-2) !important;
  border-left: 3px solid var(--border-2) !important;
  border-radius: 0 var(--r) var(--r) 0 !important;
  background: var(--bg-card) !important;
  transition: border-left-color 0.22s ease !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-left-color: var(--accent-border) !important;
}

/* ── Alerts ─────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  background: var(--bg-card) !important;
  border-radius: var(--r) !important;
}

[data-testid="stAlert"] p {
  font-family: var(--font-body) !important;
  font-size: 0.98rem !important;
}

/* ── Captions ───────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p,
.stCaption p {
  font-family: var(--font-mono) !important;
  font-size: 0.68rem !important;
  color: var(--text-faint) !important;
  letter-spacing: 0.07em !important;
}

/* ── Code blocks ────────────────────────────────────────────────────────── */
[data-testid="stCodeBlock"] pre,
[data-testid="stCodeBlock"] code {
  background: var(--bg-card-2) !important;
  border: 1px solid var(--border-2) !important;
  color: var(--teal) !important;
  font-family: var(--font-mono) !important;
  font-size: 0.82rem !important;
  border-radius: var(--r) !important;
}

/* ── Dividers ───────────────────────────────────────────────────────────── */
hr {
  border-color: var(--border-2) !important;
  margin: 1.5rem 0 !important;
}

/* ── Spinner ────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div > div {
  border-top-color: var(--accent) !important;
}

/* ── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar           { width: 5px; height: 5px; }
::-webkit-scrollbar-track     { background: var(--bg); }
::-webkit-scrollbar-thumb     { background: var(--border-2); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-dim); }

/* ── Page-link cards ────────────────────────────────────────────────────── */
[data-testid="stPageLink"] a {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-2) !important;
  border-left: 3px solid var(--accent-border) !important;
  border-radius: 0 var(--r) var(--r) 0 !important;
  color: var(--text-dim) !important;
  font-family: var(--font-body) !important;
  font-size: 1rem !important;
  letter-spacing: 0.02em !important;
  transition: border-left-color 0.18s ease, color 0.18s ease, background 0.18s ease !important;
  padding: 0.85rem 1.2rem !important;
  display: block !important;
}

[data-testid="stPageLink"] a:hover {
  border-left-color: var(--accent) !important;
  color: var(--accent) !important;
  background: var(--accent-glow) !important;
}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {
  font-family: var(--font-mono) !important;
  font-size: 0.70rem !important;
  letter-spacing: 0.15em !important;
  text-transform: uppercase !important;
  color: var(--text-faint) !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
  color: var(--accent) !important;
}

.stTabs [data-baseweb="tab-border"] {
  background-color: var(--accent) !important;
}

/* ── Selection ──────────────────────────────────────────────────────────── */
::selection {
  background: rgba(201, 168, 76, 0.18);
  color: var(--accent);
}

</style>
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def apply_theme() -> None:
    """Inject the Obsidian Index CSS into the current Streamlit page."""
    import streamlit as st
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def _badge(text: str, color: str, bg: str) -> str:
    return (
        f'<span style="'
        f'font-family:var(--font-mono);'
        f'font-size:0.64rem;'
        f'letter-spacing:0.15em;'
        f'text-transform:uppercase;'
        f'color:{color};'
        f'background:{bg};'
        f'padding:0.2em 0.7em;'
        f'border-radius:2px;'
        f'border:1px solid {color};'
        f'white-space:nowrap;'
        f'">{text}</span>'
    )


def grade_badge(grade: str | None) -> str:
    """Coloured badge for evidence grade."""
    g = (grade or "unknown").lower()
    palette = {
        "strong":       ("var(--sage)",  "var(--sage-dim)"),
        "moderate":     ("var(--teal)",  "var(--teal-dim)"),
        "weak":         ("var(--amber)", "var(--amber-dim)"),
        "insufficient": ("var(--rose)",  "var(--rose-dim)"),
    }
    color, bg = palette.get(g, ("var(--text-faint)", "transparent"))
    return _badge(g, color, bg)


def status_badge(status: str | None) -> str:
    """Coloured badge for processing / pipeline status."""
    s = (status or "unknown").lower()
    palette = {
        "extracted":    ("var(--sage)",        "var(--sage-dim)"),
        "completed":    ("var(--sage)",        "var(--sage-dim)"),
        "pending":      ("var(--amber)",       "var(--amber-dim)"),
        "running":      ("var(--teal)",        "var(--teal-dim)"),
        "failed":       ("var(--rose)",        "var(--rose-dim)"),
        "cancelled":    ("var(--text-faint)",  "transparent"),
        "consensus":    ("var(--sage)",        "var(--sage-dim)"),
        "conflicting":  ("var(--amber)",       "var(--amber-dim)"),
        "insufficient": ("var(--rose)",        "var(--rose-dim)"),
        "active":       ("var(--sage)",        "var(--sage-dim)"),
        "inactive":     ("var(--text-faint)",  "transparent"),
    }
    color, bg = palette.get(s, ("var(--text-faint)", "transparent"))
    return _badge(s, color, bg)


def section_header(title: str, subtitle: str = "") -> str:
    """HTML section header in Cormorant SC with optional subtitle."""
    sub = (
        f'<div style="'
        f'font-family:var(--font-mono);'
        f'font-size:0.62rem;'
        f'letter-spacing:0.18em;'
        f'text-transform:uppercase;'
        f'color:var(--text-faint);'
        f'margin-top:0.25rem;'
        f'">{subtitle}</div>'
        if subtitle else ""
    )
    return (
        f'<div style="margin-bottom:1rem;">'
        f'<div style="'
        f'font-family:var(--font-head);'
        f'font-size:1.45rem;'
        f'font-weight:500;'
        f'letter-spacing:0.09em;'
        f'color:var(--accent);'
        f'border-bottom:1px solid var(--border-2);'
        f'padding-bottom:0.4rem;'
        f'">{title}</div>'
        f'{sub}'
        f'</div>'
    )


def pico_grid(population: str, intervention: str, comparison: str, outcome: str) -> str:
    """Four-cell PICO display rendered as HTML."""
    def cell(label: str, value: str) -> str:
        return (
            f'<div style="'
            f'background:var(--bg-card-2);'
            f'border:1px solid var(--border-2);'
            f'border-top:2px solid var(--border-2);'
            f'border-radius:var(--r);'
            f'padding:0.7rem 0.9rem;'
            f'flex:1;'
            f'min-width:0;'
            f'">'
            f'<div style="'
            f'font-family:var(--font-mono);'
            f'font-size:0.60rem;'
            f'letter-spacing:0.20em;'
            f'color:var(--accent);'
            f'margin-bottom:0.35rem;'
            f'">{label}</div>'
            f'<div style="'
            f'font-family:var(--font-body);'
            f'font-size:0.92rem;'
            f'color:var(--text-dim);'
            f'line-height:1.5;'
            f'">{value or "—"}</div>'
            f'</div>'
        )
    return (
        f'<div style="display:flex;gap:0.5rem;margin-top:0.75rem;">'
        f'{cell("P · Population", population)}'
        f'{cell("I · Intervention", intervention)}'
        f'{cell("C · Comparison", comparison)}'
        f'{cell("O · Outcome", outcome)}'
        f'</div>'
    )


# Plotly layout defaults matching the theme
PLOTLY_LAYOUT = {
    "paper_bgcolor": "#0f1018",
    "plot_bgcolor":  "#0f1018",
    "font": {
        "family": "Azeret Mono, monospace",
        "color":  "#8b91ab",
        "size":   10,
    },
    "xaxis": {
        "gridcolor":  "#22243a",
        "linecolor":  "#22243a",
        "tickfont":   {"family": "Azeret Mono, monospace", "size": 9},
        "title_font": {"family": "Azeret Mono, monospace", "size": 9},
    },
    "yaxis": {
        "gridcolor":  "#22243a",
        "linecolor":  "#22243a",
        "tickfont":   {"family": "Azeret Mono, monospace", "size": 9},
        "title_font": {"family": "Azeret Mono, monospace", "size": 9},
    },
    "legend": {
        "font":    {"family": "Azeret Mono, monospace", "size": 9},
        "bgcolor": "#0f1018",
        "bordercolor": "#22243a",
        "borderwidth": 1,
    },
    "title_font": {
        "family": "Cormorant SC, Georgia, serif",
        "size":   14,
        "color":  "#c9a84c",
    },
    "margin": {"t": 48, "b": 32, "l": 40, "r": 20},
}
