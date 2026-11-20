from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Any, Callable

import streamlit as st

from services.profile_store import (
    COOKIE_TTL_DAYS,
    ProfileStore,
    ProfileStoreError,
    profile_is_fresh,
)
from ui.state import PROFILE_COOKIE_KEY, PROFILE_EDIT_KEY, PROFILE_KEY, init_state

PROFILE_COOKIE = "analytics_user_profile"
COOKIE_MAX_AGE = COOKIE_TTL_DAYS * 24 * 60 * 60
PROFILE_FORM_FIELDS = ("nome", "email", "cargo", "setor")

if hasattr(st, "dialog"):
    profile_dialog = st.dialog("Seus dados")
else:

    def profile_dialog(function: Callable[[], None]) -> Callable[[], None]:
        return function


def _read_cookie() -> str | None:
    context = getattr(st, "context", None)
    cookies = getattr(context, "cookies", None)
    if not isinstance(cookies, Mapping):
        return None
    value = cookies.get(PROFILE_COOKIE)
    return str(value).strip() if value else None


def current_profile() -> dict[str, Any] | None:
    init_state()
    cookie_id = _read_cookie()
    if not cookie_id:
        return None

    cached_id = st.session_state.get(PROFILE_COOKIE_KEY)
    cached_profile = st.session_state.get(PROFILE_KEY)
    if cached_id == cookie_id and isinstance(cached_profile, dict):
        return cached_profile if profile_is_fresh(cached_profile) else None

    try:
        profile = ProfileStore().get_profile(cookie_id)
    except ProfileStoreError:
        return None
    if not profile or not profile_is_fresh(profile):
        return None

    st.session_state[PROFILE_COOKIE_KEY] = cookie_id
    st.session_state[PROFILE_KEY] = profile
    return profile


def _render_iframe(html: str) -> None:
    renderer = getattr(st, "iframe", None)
    if callable(renderer):
        renderer(html, height=1, width=1)
        return
    from streamlit.components.v1 import html as legacy_html

    legacy_html(html, height=1, width=1)


def build_cookie_script(profile_id: str) -> str:
    cookie_name = json.dumps(PROFILE_COOKIE)
    cookie_value = json.dumps(profile_id)
    return f"""
<script>
(function() {{
  var secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = {cookie_name} + '=' + encodeURIComponent({cookie_value}) +
    '; Max-Age={COOKIE_MAX_AGE}; Path=/; SameSite=Lax' + secure;
  setTimeout(function() {{ window.parent.location.reload(); }}, 200);
}})();
</script>
"""


@profile_dialog
def _render_dialog() -> None:
    st.write(
        "Informe seus dados uma vez para personalizar a experiência. "
        "O preenchimento fica salvo neste navegador por 7 dias."
    )
    with st.form("user_profile_form"):
        nome = st.text_input("Nome", key="profile_nome")
        email = st.text_input("E-mail", key="profile_email")
        cargo = st.text_input("Cargo", key="profile_cargo")
        setor = st.text_input("Setor", key="profile_setor")
        submitted = st.form_submit_button("Salvar dados", type="primary", width="stretch")

    if not submitted:
        return

    profile_id = str(
        st.session_state.get(PROFILE_COOKIE_KEY) or _read_cookie() or uuid.uuid4()
    )
    try:
        profile = ProfileStore().save_profile(
            profile_id=profile_id,
            nome=nome,
            email=email,
            cargo=cargo,
            setor=setor,
        )
    except (ProfileStoreError, ValueError) as exc:
        st.error(str(exc))
        return

    st.session_state[PROFILE_COOKIE_KEY] = profile_id
    st.session_state[PROFILE_KEY] = profile
    st.session_state[PROFILE_EDIT_KEY] = False
    st.success("Dados salvos. Atualizando a página...")
    _render_iframe(build_cookie_script(profile_id))
    st.stop()


def _render_sidebar_profile(profile: dict[str, Any]) -> None:
    with st.sidebar:
        st.divider()
        st.subheader("Meus dados")
        st.write(profile.get("nome") or "—")
        st.caption(profile.get("email") or "—")
        st.write(f"Cargo: {profile.get('cargo') or '—'}")
        st.write(f"Setor: {profile.get('setor') or '—'}")
        if st.button("Editar dados", key="profile_edit_button", width="stretch"):
            st.session_state[PROFILE_EDIT_KEY] = True
            st.rerun()


def render_profile_popup() -> dict[str, Any] | None:
    profile = current_profile()
    if profile:
        _render_sidebar_profile(profile)
        if st.session_state.get(PROFILE_EDIT_KEY):
            st.session_state[PROFILE_EDIT_KEY] = False
            for field in PROFILE_FORM_FIELDS:
                st.session_state[f"profile_{field}"] = profile.get(field, "")
            _render_dialog()
        return profile
    _render_dialog()
    return None
