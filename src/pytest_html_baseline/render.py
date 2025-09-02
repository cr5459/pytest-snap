from __future__ import annotations

from .diff import diff_snapshots  # noqa: F401  # (may be used later)


def render_baseline_section(report, diff: dict):  # pragma: no cover - simple formatting
    from py.xml import html  # type: ignore

    summ = diff.get("summary", {})
    panel = html.div(class_="baseline-compare")
    panel.append(html.h2("Baseline Compare"))
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
        for r in rows[:50]:  # cap for brevity
            body_rows.append(html.tr([html.td(str(r.get(c.lower()) or r.get(c) or r.get(c.split()[0].lower()) or r.get(c.split()[0])) ) for c in cols]))
        panel.append(html.table([head] + body_rows))

    table("New Failures", diff.get("new_failures", []), ["id", "from", "to"])
    table("Vanished Failures", diff.get("vanished_failures", []), ["id"])
    table("Flaky Suspects", diff.get("flaky_suspects", []), ["id", "from", "to"])
    table("Slower Tests", diff.get("slower_tests", []), ["id", "prev", "curr", "ratio"])
    report.append(panel)


def pytest_html_results_summary(prefix, summary, postfix):  # pragma: no cover - integration
    # Called by pytest-html if installed
    config = getattr(summary, "config", None) or getattr(prefix, "config", None)
    if not config:
        return
    diff = getattr(config, "_html_baseline_diff", None)
    if not diff:
        return
    try:
        render_baseline_section(prefix, diff)
    except Exception:  # swallow rendering errors
        pass
