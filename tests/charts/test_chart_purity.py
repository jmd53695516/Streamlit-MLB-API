"""Chart purity guard (D-09).

src/mlb_park/chart.py MUST NOT import `streamlit` or reach for
`st.session_state`. The chart is called BY app.py (which does the Streamlit
wiring); chart.py itself stays UI-free so it can be unit-tested without a
Streamlit runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

import mlb_park.chart as chart_module


def test_no_streamlit_in_chart_module():
    src_path = Path(chart_module.__file__)
    source = src_path.read_text(encoding="utf-8")
    assert "import streamlit" not in source, (
        f"chart.py must not `import streamlit` (D-09); found in {src_path}"
    )
    assert "from streamlit" not in source, (
        f"chart.py must not `from streamlit ...`; found in {src_path}"
    )
    assert "st.session_state" not in source, (
        f"chart.py must not read st.session_state (D-09); found in {src_path}"
    )


def test_chart_imports_have_no_streamlit():
    ns = sys.modules["mlb_park.chart"].__dict__
    for name, value in ns.items():
        mod_name = getattr(value, "__module__", "") or ""
        if mod_name.startswith("streamlit"):
            raise AssertionError(
                f"chart module namespace references streamlit via `{name}` "
                f"(from module {mod_name})"
            )
    assert "streamlit" not in ns, "chart must not bind `streamlit` in its namespace"
    assert "st" not in ns, "chart must not bind `st` (streamlit alias) in its namespace"
