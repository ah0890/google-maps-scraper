"""
Google Maps Business Scraper — Streamlit dashboard entry point.
"""

from __future__ import annotations

import threading
import time
from datetime import timedelta

import pandas as pd
import streamlit as st

from scraper import run_scraper_in_thread
from ui import (
    init_session_state,
    load_css,
    render_control_buttons,
    render_export_section,
    render_hero,
    render_metrics,
    render_progress_panel,
    render_results_grid,
    render_sidebar,
    render_step_cards,
    status_badge,
)
from utils import (
    LOGGER,
    ScraperState,
    load_locations_csv,
    rows_to_dataframe,
    save_export,
)

st.set_page_config(
    page_title="Maps Scraper Pro",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Shared scraper state (module-level singleton for thread + UI)
if "scraper_state" not in st.session_state:
    st.session_state.scraper_state = ScraperState()


def show_toasts() -> None:
    queue = st.session_state.get("toast_queue", [])
    while queue:
        kind, message = queue.pop(0)
        if kind == "success":
            st.toast(message, icon="✅")
        elif kind == "error":
            st.toast(message, icon="⚠️")
        else:
            st.toast(message)


def queue_toast(message: str, kind: str = "info") -> None:
    st.session_state.toast_queue.append((kind, message))


def sync_results_from_state() -> None:
    snap = st.session_state.scraper_state.snapshot()
    if snap["results"]:
        st.session_state.results_df = rows_to_dataframe(snap["results"])


def start_scraping(keyword: str, locations: list[str], settings: dict) -> None:
    state: ScraperState = st.session_state.scraper_state
    if state.snapshot()["is_running"]:
        queue_toast("Scraper is already running.", "error")
        return

    thread = threading.Thread(
        target=run_scraper_in_thread,
        args=(keyword, locations, settings, state),
        daemon=True,
    )
    st.session_state.scraper_thread = thread
    thread.start()
    queue_toast(f"Started scraping {len(locations)} location(s).", "success")
    LOGGER.info("Scrape started: keyword=%s locations=%d", keyword, len(locations))


@st.fragment(run_every=timedelta(seconds=2))
def live_dashboard_fragment() -> None:
    """Auto-refresh results while scraping is active."""
    state: ScraperState = st.session_state.scraper_state
    snap = state.snapshot()

    if not snap["is_running"] and not st.session_state.get("auto_refresh"):
        return

    sync_results_from_state()
    df = st.session_state.results_df

    st.markdown(
        f'<p class="dashboard-section-title">Result Dashboard {status_badge(snap["is_running"], snap["is_paused"], not df.empty)}</p>',
        unsafe_allow_html=True,
    )

    if snap["is_running"]:
        render_progress_panel(snap)

    render_metrics(df)

    search = st.session_state.get("table_search", "")
    filtered = render_results_grid(df, search)
    render_export_section(filtered if not filtered.empty else df, st.session_state.settings.get("export_format", "CSV"))


def main() -> None:
    init_session_state()
    load_css()
    show_toasts()

    defaults = st.session_state.get("settings") or {
        "max_results": 10,
        "headless": True,
        "delay_mid": 2.5,
        "concurrent_tabs": 1,
        "proxy": "",
    }
    settings = render_sidebar(defaults)
    st.session_state.settings = settings

    render_hero()

    keyword, uploaded = render_step_cards(
        st.session_state.keyword,
        st.session_state.uploaded_filename,
    )
    st.session_state.keyword = keyword

    if uploaded is not None:
        try:
            locations = load_locations_csv(uploaded.getvalue())
            st.session_state.locations = locations
            st.session_state.uploaded_filename = uploaded.name
            st.success(f"Loaded **{len(locations)}** locations from `{uploaded.name}`.")
        except ValueError as exc:
            st.error(str(exc))
            st.session_state.locations = []

    state: ScraperState = st.session_state.scraper_state
    snap = state.snapshot()

    start, pause, stop, refresh = render_control_buttons(snap)

    if refresh:
        sync_results_from_state()
        st.rerun()

    if stop:
        state.request_stop()
        queue_toast("Stop requested — finishing current item...", "info")

    if pause:
        if snap["is_paused"]:
            state.request_resume()
            queue_toast("Scraping resumed.", "success")
        else:
            state.request_pause()
            queue_toast("Scraping paused.", "info")

    if start:
        if not keyword.strip():
            st.error("Please enter a business keyword.")
        elif not st.session_state.locations:
            st.error("Please upload a valid locations CSV.")
        else:
            st.session_state.results_df = pd.DataFrame()
            with state._lock:
                state.results.clear()
            start_scraping(keyword.strip(), st.session_state.locations, settings)

    # Control panel: search + auto refresh
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1:
        st.session_state.table_search = st.text_input(
            "Search results",
            value=st.session_state.table_search,
            placeholder="Filter by name, address, phone...",
        )
    with c2:
        st.session_state.auto_refresh = st.toggle(
            "Auto refresh",
            value=st.session_state.get("auto_refresh", True),
        )

    snap = state.snapshot()
    if snap["is_running"] or st.session_state.get("auto_refresh"):
        live_dashboard_fragment()
    else:
        sync_results_from_state()
        df = st.session_state.results_df
        st.markdown(
            f'<p class="dashboard-section-title">Result Dashboard {status_badge(False, False, not df.empty)}</p>',
            unsafe_allow_html=True,
        )
        render_metrics(df)
        filtered = render_results_grid(df, st.session_state.table_search)
        render_export_section(
            filtered if not filtered.empty else df,
            settings.get("export_format", "CSV"),
        )

    # Manual save to exports when idle and results exist
    if not snap["is_running"] and not st.session_state.results_df.empty:
        if st.button("Save to exports folder", use_container_width=False):
            path = save_export(st.session_state.results_df, settings.get("export_format", "CSV"))
            queue_toast(f"Saved to {path.name}", "success")
            st.rerun()

    # Activity log tab
    with st.expander("Activity Log", expanded=False):
        errors = snap.get("errors", [])
        if errors:
            for err in errors[-20:]:
                st.warning(err)
        else:
            st.caption("No errors logged.")

    # Footer
    st.markdown(
        '<p style="text-align:center;color:#64748b;font-size:0.75rem;margin-top:2rem;">'
        "Maps Scraper Pro · Playwright · Use in compliance with applicable terms"
        "</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
