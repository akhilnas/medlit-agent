"""Dashboard authentication guard.

Set DASHBOARD_PASSWORD in the environment to enable password protection.
Leave it unset (or empty) to allow unauthenticated access in local dev.

Usage — call at the top of every page before rendering any content:

    from dashboard.auth import require_login
    require_login()
"""

from __future__ import annotations

import hmac
import os

import streamlit as st

_PASSWORD_ENV = "DASHBOARD_PASSWORD"
_SESSION_KEY = "_medlit_authenticated"


def require_login() -> None:
    """Redirect to login form if the user is not authenticated.

    No-ops when DASHBOARD_PASSWORD is not configured (local dev).
    Stores authenticated state in ``st.session_state`` so the check
    passes on subsequent reruns within the same browser session.
    """
    password = os.environ.get(_PASSWORD_ENV, "").strip()
    if not password:
        # Auth disabled — allow all access (local dev / CI)
        return

    if st.session_state.get(_SESSION_KEY):
        return

    _render_login_form(password)


def _render_login_form(correct_password: str) -> None:
    """Display a login form and halt page rendering until auth succeeds."""
    from dashboard.theme import apply_theme  # avoid circular import at module level

    apply_theme()

    st.markdown(
        """
        <div style="
          max-width: 360px;
          margin: 6rem auto 0;
          text-align: center;
        ">
          <div style="
            font-family: 'Cormorant SC', serif;
            font-size: 2.4rem;
            font-weight: 300;
            letter-spacing: 0.28em;
            color: var(--text);
            margin-bottom: 0.2rem;
          ">MEDLIT</div>
          <div style="
            font-family: 'Cormorant SC', serif;
            font-size: 1rem;
            letter-spacing: 0.42em;
            color: var(--accent);
            margin-bottom: 2rem;
          ">AGENT</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        password_input = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        # Constant-time comparison prevents timing-based enumeration
        if hmac.compare_digest(password_input, correct_password):
            st.session_state[_SESSION_KEY] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.markdown(
        """
        <div style="
          text-align: center;
          margin-top: 1.5rem;
          font-size: 0.8rem;
          color: var(--muted, #888);
          font-family: sans-serif;
        ">
          For access, contact
          <a href="mailto:eakhil.n@gmail.com" style="color: var(--accent, #888); text-decoration: none;">
            eakhil.n@gmail.com
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()
