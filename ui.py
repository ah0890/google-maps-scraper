"""
Streamlit UI components: layout, sidebar, metrics, AgGrid table, and styling.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode, JsCode

from utils import ASSETS_DIR, compute_metrics, estimate_eta_seconds, rows_to_dataframe

DISPLAY_COLUMNS = [
    "location",
    "keyword",
    "business_name",
    "address",
    "website",
    "phone",
    "rating",
    "reviews_count",
]


def load_css() -> None:
    css_path = ASSETS_DIR / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown(
        """
        <div class="app-hero">
            <h1>Google Maps Business Scraper</h1>
            <p>Extract business leads by keyword and location — export-ready CSV in minutes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(defaults: dict) -> dict:
    with st.sidebar:
        st.markdown('<p class="sidebar-brand">Maps Scraper Pro</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="sidebar-tagline">Premium lead extraction dashboard</p>',
            unsafe_allow_html=True,
        )

        with st.expander("About", expanded=False):
            st.markdown(
                """
                **Maps Scraper Pro** automates Google Maps business discovery.

                - Playwright-powered extraction
                - Multi-location CSV batch runs
                - Live dashboard & exports

                Use responsibly and comply with Google's Terms of Service.
                """
            )

        with st.expander("How to Use", expanded=False):
            st.markdown(
                """
                1. Enter a **business keyword** (e.g. `plumber`, `dentist`)
                2. Upload a **CSV** with a `location` column
                3. Adjust **Settings** if needed
                4. Click **Start Scraping**
                5. Monitor live results and **Export CSV**
                """
            )

        with st.expander("Extracted Data", expanded=False):
            st.markdown(
                """
                | Field | Description |
                |-------|-------------|
                | Business Name | Listing title |
                | Address | Street / area |
                | Website | External URL |
                | Phone | Contact number |
                | Rating | Star rating |
                | Reviews Count | Total reviews |
                """
            )

        st.markdown('<p class="sidebar-section-title">Settings</p>', unsafe_allow_html=True)

        max_results = st.slider(
            "Max Results Per Location",
            min_value=1,
            max_value=50,
            value=int(defaults.get("max_results", 10)),
        )
        headless = st.toggle("Headless Mode", value=bool(defaults.get("headless", True)))
        delay = st.slider(
            "Delay Between Requests (sec)",
            min_value=0.5,
            max_value=10.0,
            value=float(defaults.get("delay_mid", 2.5)),
            step=0.5,
        )
        concurrent_tabs = st.slider(
            "Concurrent Browser Tabs",
            min_value=1,
            max_value=3,
            value=int(defaults.get("concurrent_tabs", 1)),
        )
        proxy = st.text_input(
            "Proxy (optional)",
            value=defaults.get("proxy", ""),
            placeholder="http://user:pass@host:port",
        )
        export_format = st.selectbox("Export Format", ["CSV", "XLSX"], index=0)
        auto_save = st.toggle("Auto-save Results", value=True)

        delay_min = max(0.3, delay - 1.0)
        delay_max = delay + 1.0

    return {
        "max_results": max_results,
        "headless": headless,
        "delay_min": delay_min,
        "delay_max": delay_max,
        "concurrent_tabs": concurrent_tabs,
        "proxy": proxy,
        "export_format": export_format,
        "auto_save": auto_save,
        "max_retries": 3,
    }


def render_step_cards(keyword: str, uploaded_name: str | None) -> tuple[str, object | None]:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="step-card">
                <span class="step-badge">1</span>
                <span class="step-title">Business Keyword</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        keyword_input = st.text_input(
            "Keyword",
            value=keyword,
            placeholder="e.g. coffee shop, dentist, plumber",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            """
            <div class="step-card">
                <span class="step-badge">2</span>
                <span class="step-title">Upload Locations CSV</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "CSV file",
            type=["csv"],
            label_visibility="collapsed",
            help="CSV must contain a `location` column.",
        )
        if uploaded_name and not uploaded:
            st.caption(f"Loaded: **{uploaded_name}**")

    st.markdown(
        """
        <div class="step-card">
            <span class="step-badge">3</span>
            <span class="step-title">Run Scraper</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return keyword_input, uploaded


def status_badge(is_running: bool, is_paused: bool, has_results: bool) -> str:
    if is_running and is_paused:
        cls, label = "status-paused", "Paused"
    elif is_running:
        cls, label = "status-running", "Scraping..."
    elif has_results:
        cls, label = "status-done", "Complete"
    else:
        cls, label = "status-idle", "Ready"
    return f'<span class="status-badge {cls}">{label}</span>'


def render_metrics(df: pd.DataFrame) -> None:
    metrics = compute_metrics(df)
    cols = st.columns(4)
    labels = [
        ("Total Records", metrics["total"]),
        ("Successful", metrics["successful"]),
        ("With Phone", metrics["with_phone"]),
        ("With Website", metrics["with_website"]),
    ]
    for col, (label, value) in zip(cols, labels):
        col.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{value:,}</div>
                <div class="metric-label">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_progress_panel(snapshot: dict) -> None:
    pct = snapshot.get("progress_pct", 0) / 100.0
    st.progress(min(1.0, max(0.0, pct)), text=f"{snapshot.get('progress_pct', 0):.0f}%")

    eta = estimate_eta_seconds(snapshot.get("started_at"), snapshot.get("progress_pct", 0))
    eta_text = f"{eta // 60}m {eta % 60}s" if eta is not None else "—"
    c1, c2, c3 = st.columns(3)
    c1.metric("Locations", f"{snapshot.get('locations_done', 0)} / {snapshot.get('locations_total', 0)}")
    c2.metric("Businesses", snapshot.get("businesses_scraped", 0))
    c3.metric("ETA", eta_text)

    msg = snapshot.get("last_message") or "Working..."
    loc = snapshot.get("current_location") or "—"
    st.caption(f"**Status:** {msg} · **Location:** {loc}")


def render_control_buttons(state_snapshot: dict) -> tuple[bool, bool, bool, bool]:
    """Returns (start_clicked, pause_clicked, stop_clicked, refresh_clicked)."""
    running = state_snapshot.get("is_running", False)
    paused = state_snapshot.get("is_paused", False)

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        start = st.button(
            "Start Scraping",
            type="primary",
            use_container_width=True,
            disabled=running,
        )
    with c2:
        pause = st.button(
            "Pause" if not paused else "Resume",
            use_container_width=True,
            disabled=not running,
        )
    with c3:
        stop = st.button("Stop", use_container_width=True, disabled=not running)
    with c4:
        refresh = st.button("Refresh", use_container_width=True)

    return start, pause, stop, refresh


def render_results_grid(df: pd.DataFrame, search: str) -> pd.DataFrame:
    if df.empty:
        st.info("No results yet. Start scraping to populate the table.")
        return df

    display_df = df.copy()
    for col in DISPLAY_COLUMNS:
        if col not in display_df.columns:
            display_df[col] = ""

    if search.strip():
        mask = display_df.astype(str).apply(
            lambda row: row.str.contains(search.strip(), case=False, na=False).any(),
            axis=1,
        )
        display_df = display_df[mask]

    gb = GridOptionsBuilder.from_dataframe(display_df[DISPLAY_COLUMNS])
    gb.configure_default_column(
        filterable=True,
        sortable=True,
        resizable=True,
        wrapText=True,
        autoHeight=True,
    )
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_side_bar(filters_panel=True, columns_panel=True)
    gb.configure_grid_options(domLayout="normal", rowHeight=48)

    cell_style = JsCode(
        """
        function(params) {
            if (params.colDef.field === 'rating' && params.value) {
                return {color: '#22d3ee', fontWeight: '600'};
            }
            return null;
        }
        """
    )
    gb.configure_column("rating", cellStyle=cell_style)

    grid_options = gb.build()

    AgGrid(
        display_df[DISPLAY_COLUMNS],
        gridOptions=grid_options,
        theme="streamlit",
        height=420,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.NO_UPDATE,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=True,
        custom_css={
            ".ag-root-wrapper": {
                "border-radius": "12px",
                "border": "1px solid rgba(99, 132, 199, 0.18)",
            },
            ".ag-header": {"background-color": "#1e293b"},
            ".ag-row": {"background-color": "#151f32"},
        },
    )
    return display_df


def render_export_section(df: pd.DataFrame, export_format: str) -> None:
    if df.empty:
        return
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Export CSV",
        data=csv_bytes,
        file_name="gmaps_scrape_results.csv",
        mime="text/csv",
        use_container_width=True,
    )


def init_session_state() -> None:
    defaults = {
        "keyword": "",
        "uploaded_filename": None,
        "locations": [],
        "settings": {},
        "results_df": pd.DataFrame(),
        "scraper_thread": None,
        "toast_queue": [],
        "auto_refresh": True,
        "table_search": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
