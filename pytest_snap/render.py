from __future__ import annotations

"""pytest-html integration renderers (migrated)."""

import pytest
from .diff import diff_snapshots  # noqa: F401  # (may be used later)


def render_baseline_section(report, diff: dict):  # pragma: no cover - simple formatting
    from py.xml import html  # type: ignore

    summ = diff.get("summary", {})
    panel = html.div(class_="baseline-compare")
    panel.append(html.h2("Baseline Compare", style="margin-top:1em;border-top:1px solid #ddd;padding-top:0.5em;"))
    panel.append(
        html.p(
            f"New Failures: {summ.get('n_new',0)} | Vanished: {summ.get('n_vanished',0)} | Flaky: {summ.get('n_flaky',0)} | Slower: {summ.get('n_slower',0)}"
        )
    )

    def table(bucket_name: str, rows: list, cols):
        if not rows:
            return
        panel.append(html.h3(bucket_name))
        head = html.tr([html.th(c) for c in cols])
        body_rows = []
        for r in rows[:50]:
            body_rows.append(html.tr([html.td(str(r.get(c.lower()) or r.get(c) or r.get(c.split()[0].lower()) or r.get(c.split()[0])) ) for c in cols]))
        panel.append(html.table([head] + body_rows))

    table("New Failures", diff.get("new_failures", []), ["id", "from", "to"])
    table("Vanished Failures", diff.get("vanished_failures", []), ["id"])
    table("Flaky Suspects", diff.get("flaky_suspects", []), ["id", "from", "to"])
    table("Slower Tests", diff.get("slower_tests", []), ["id", "prev", "curr", "ratio"])
    report.append(panel)


@pytest.hookimpl(tryfirst=True)  # pragma: no cover - integration
def pytest_html_results_summary(prefix, summary, postfix, session):  # pragma: no cover - integration
    config = getattr(summary, "config", None) or getattr(prefix, "config", None)
    if not config:
        return
    diff = getattr(config, "_html_baseline_diff", None)
    if not diff:
        try:
            from py.xml import html  # type: ignore
            placeholder = html.div(class_="baseline-compare")
            placeholder.append(html.h2("Baseline Compare"))
            placeholder.append(html.p("No baseline diff available (provide --snap-baseline)."))
            prefix.append(placeholder)
        except Exception:
            pass
        return
    try:
        render_baseline_section(prefix, diff)
    except Exception:  # swallow rendering errors
        pass


@pytest.hookimpl(tryfirst=True)  # pragma: no cover - integration
def pytest_html_results_table_row(report, cells):  # pragma: no cover - integration
    config = getattr(report, "config", None)
    if not config:
        return
    if not getattr(config, "_html_baseline_badges", False):
        return
    diff = getattr(config, "_html_baseline_diff", None)
    if not diff:
        return
    try:
        from py.xml import html  # type: ignore
    except Exception:
        return


@pytest.hookimpl(tryfirst=True)  # pragma: no cover - integration
def pytest_html_report_header(config):
    diff = getattr(config, "_html_baseline_diff", None)
    if not diff:
        return ["Baseline Compare: (no diff – supply --snap-baseline)"]
    s = diff.get("summary", {})
    return [
        (
            f"Baseline Compare: new={s.get('n_new',0)} "
            f"vanished={s.get('n_vanished',0)} flaky={s.get('n_flaky',0)} "
            f"slower={s.get('n_slower',0)} budgets={s.get('n_budget',0)}"
        )
    ]

__all__ = [
    "render_baseline_section",
]
