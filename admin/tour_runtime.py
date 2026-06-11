"""Runtime helpers for the admin guided tour."""
import json
from collections.abc import Callable

import streamlit as st

PAGE_LABEL_KEYS = {
    "overview": "nav.overview",
    "users": "nav.users",
    "sessions": "nav.sessions",
    "audit_logs": "nav.audit_logs",
    "valkey_status": "nav.valkey_status",
    "db_schema": "nav.db_schema",
    "api_test": "nav.api_test",
}

PAGE_ORDER = list(PAGE_LABEL_KEYS.keys())

TOUR_STEPS = [
    {
        "pageId": "overview",
        "selector": '[data-tour-id="sidebar-navigation"]',
        "title": "tour.steps.navigation.title",
        "description": "tour.steps.navigation.description",
        "side": "right",
        "align": "start",
    },
    {
        "pageId": "overview",
        "selector": '[data-tour-id="overview-summary"]',
        "title": "tour.steps.overview.title",
        "description": "tour.steps.overview.description",
        "side": "bottom",
        "align": "start",
    },
    {
        "pageId": "users",
        "selector": '[data-tour-id="users-page"]',
        "title": "tour.steps.users.title",
        "description": "tour.steps.users.description",
        "side": "bottom",
        "align": "start",
    },
    {
        "pageId": "sessions",
        "selector": '[data-tour-id="sessions-page"]',
        "title": "tour.steps.sessions.title",
        "description": "tour.steps.sessions.description",
        "side": "bottom",
        "align": "start",
    },
    {
        "pageId": "audit_logs",
        "selector": '[data-tour-id="audit-page"]',
        "title": "tour.steps.audit.title",
        "description": "tour.steps.audit.description",
        "side": "bottom",
        "align": "start",
    },
    {
        "pageId": "valkey_status",
        "selector": '[data-tour-id="valkey-page"]',
        "title": "tour.steps.valkey.title",
        "description": "tour.steps.valkey.description",
        "side": "bottom",
        "align": "start",
    },
    {
        "pageId": "db_schema",
        "selector": '[data-tour-id="db-schema-page"]',
        "title": "tour.steps.db_schema.title",
        "description": "tour.steps.db_schema.description",
        "side": "bottom",
        "align": "start",
    },
    {
        "pageId": "api_test",
        "selector": '[data-tour-id="api-test-page"]',
        "title": "tour.steps.api_test.title",
        "description": "tour.steps.api_test.description",
        "side": "bottom",
        "align": "start",
    },
]


def sync_page_from_query() -> None:
    """Apply tour/page query params to Streamlit page state."""
    query_page = st.query_params.get("page")
    if query_page in PAGE_ORDER and st.session_state.get("page_id") != query_page:
        st.session_state.page_id = query_page


def set_page_query(page_id: str) -> None:
    """Persist the selected admin page in query params for the JS tour."""
    if st.query_params.get("page") != page_id:
        st.query_params["page"] = page_id


def page_label(page_id: str, t: Callable[[str], str]) -> str:
    return t(PAGE_LABEL_KEYS[page_id])


def render_tour_anchor(anchor_id: str) -> None:
    st.markdown(
        f'<span class="yesod-tour-anchor" data-tour-id="{anchor_id}" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_tour_assets(page_id: str, t: Callable[[str], str]) -> None:
    """Inject Driver.js assets and mount the admin tour in the parent Streamlit document."""
    translated_steps = [
        {
            **step,
            "title": t(step["title"]),
            "description": t(step["description"]),
        }
        for step in TOUR_STEPS
    ]
    config = {
        "pageId": page_id,
        "fallbackSelector": '[data-tour-id="app-title"]',
        "query": {
            "page": "page",
            "tour": "tour",
            "step": "tour_step",
        },
        "labels": {
            "launcher": t("tour.launcher"),
            "launcherAria": t("tour.launcher_aria"),
            "next": t("tour.next"),
            "previous": t("tour.previous"),
            "done": t("tour.done"),
            "progress": t("tour.progress"),
            "missingTarget": t("tour.missing_target"),
        },
        "steps": translated_steps,
    }
    payload = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
    st.html(
        f"""
        <script>
        (() => {{
          const config = {payload};
          const parentWindow = window.parent;
          const parentDocument = parentWindow.document;

          function ensureStylesheet(id, href) {{
            if (parentDocument.getElementById(id)) return;
            const link = parentDocument.createElement("link");
            link.id = id;
            link.rel = "stylesheet";
            link.href = href;
            parentDocument.head.appendChild(link);
          }}

          function ensureScript(id, src) {{
            return new Promise((resolve, reject) => {{
              const existing = parentDocument.getElementById(id);
              if (existing) {{
                if (existing.dataset.loaded === "true") resolve();
                else existing.addEventListener("load", () => resolve(), {{ once: true }});
                return;
              }}
              const script = parentDocument.createElement("script");
              script.id = id;
              script.src = src;
              script.async = false;
              script.onload = () => {{
                script.dataset.loaded = "true";
                resolve();
              }};
              script.onerror = reject;
              parentDocument.body.appendChild(script);
            }});
          }}

          ensureStylesheet("yesod-driver-css", "/app/static/tour/vendor/driver.css");
          ensureStylesheet("yesod-admin-tour-css", "/app/static/tour/admin-tour.css");
          ensureScript("yesod-driver-js", "/app/static/tour/vendor/driver.js")
            .then(() => ensureScript("yesod-admin-tour-js", "/app/static/tour/admin-tour.js"))
            .then(() => parentWindow.YesodAdminTour && parentWindow.YesodAdminTour.mount(config))
            .catch((error) => console.error("Failed to load YESOD admin tour", error));
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )
