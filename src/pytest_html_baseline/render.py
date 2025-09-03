from __future__ import annotations

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
        # Insert a placeholder so users see feature is active but no baseline loaded
        try:
            from py.xml import html  # type: ignore
            placeholder = html.div(class_="baseline-compare")
            placeholder.append(html.h2("Baseline Compare"))
            placeholder.append(html.p("No baseline diff available (provide --html-baseline)."))
            prefix.append(placeholder)
        except Exception:
            pass
        return
    try:
        render_baseline_section(prefix, diff)
    except Exception:  # swallow rendering errors
        pass


def pytest_html_results_table_row(report, cells):  # pragma: no cover - integration
    # Add inline badges next to test node id cell if enabled
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
    nodeid = getattr(report, "nodeid", None)
    if not nodeid:
        return
    # Build quick lookup sets
    nf = {r["id"] for r in diff.get("new_failures", [])}
    vf = {r["id"] for r in diff.get("vanished_failures", [])}
    fl = {r["id"] for r in diff.get("flaky_suspects", [])}
    sl = {r["id"] for r in diff.get("slower_tests", [])}
    badges = []
    if nodeid in nf:
        badges.append(("NEW", "#fff", "#d33"))
    if nodeid in vf:
        badges.append(("FIXED", "#fff", "#2d8"))
    if nodeid in fl:
        badges.append(("FLAKY?", "#222", "#fd3"))
    if nodeid in sl:
        badges.append(("SLOWER", "#fff", "#e67e22"))
    if not badges:
        return
    # First cell typically contains test id
    try:
        id_cell = cells[0]
        span = html.span(" ")
        for text, fg, bg in badges:
            span.append(
                html.span(
                    text,
                    style=(
                        "display:inline-block;margin-left:4px;padding:1px 4px;"
                        f"font-size:10px;border-radius:3px;background:{bg};color:{fg};font-weight:600;"
                    ),
                )
            )
        id_cell.append(span)
    except Exception:
        return
