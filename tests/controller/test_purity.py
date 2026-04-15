"""Controller purity guard (D-23).

src/mlb_park/controller.py MUST NOT import `streamlit` or reach for
`st.session_state`. UI code lives in app.py / views/, controller composes the
ViewModel in isolation so it can be unit-tested without a Streamlit runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

import mlb_park.controller as controller_module


def test_no_streamlit_in_controller_module():
    """Source-level guard — forbid `import streamlit`, `from streamlit`, `st.session_state`."""
    src_path = Path(controller_module.__file__)
    source = src_path.read_text(encoding="utf-8")
    assert "import streamlit" not in source, (
        f"controller.py must not `import streamlit` (D-23); found in {src_path}"
    )
    assert "from streamlit" not in source, (
        f"controller.py must not `from streamlit ...`; found in {src_path}"
    )
    assert "st.session_state" not in source, (
        f"controller.py must not read st.session_state (D-23); found in {src_path}"
    )


def test_controller_imports_have_no_streamlit():
    """Runtime-level guard — the imported module's namespace has no `streamlit` attr."""
    ns = sys.modules["mlb_park.controller"].__dict__
    for name, value in ns.items():
        mod_name = getattr(value, "__module__", "") or ""
        if mod_name.startswith("streamlit"):
            raise AssertionError(
                f"controller module namespace references streamlit via `{name}` "
                f"(from module {mod_name})"
            )
    # The top-level name itself must never be bound.
    assert "streamlit" not in ns, "controller must not bind `streamlit` in its namespace"
    assert "st" not in ns, "controller must not bind `st` (streamlit alias) in its namespace"
