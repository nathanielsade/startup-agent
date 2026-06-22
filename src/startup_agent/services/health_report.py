from collections import Counter

from startup_agent.domain.models import CompanyHealth

# display/sort order: most-actionable issues are easy to find, ok last
_ORDER = ["failed", "filtered_foreign", "empty", "unsupported", "ok"]


def render_health_report(results: list[CompanyHealth], generated_at: str) -> str:
    """Render a per-company integration-status report as Markdown."""
    tally = Counter(r.status for r in results)
    lines = [
        "# Integration Status",
        "",
        f"_Generated: {generated_at}_",
        "",
        f"**{len(results)} companies** scanned.",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|---|---|",
    ]
    for status in _ORDER:
        lines.append(f"| {status} | {tally.get(status, 0)} |")
    lines.append("")

    broken = sorted((r for r in results if r.status == "failed"), key=lambda r: r.name)
    if broken:
        lines += ["## ⚠️ Broken feeds (fix the seed config)", "",
                  "| Company | ATS | Error |", "|---|---|---|"]
        lines += [f"| {r.name} | {r.ats_type} | {(r.error or '')[:90]} |" for r in broken]
        lines.append("")

    foreign = sorted((r for r in results if r.status == "filtered_foreign"),
                     key=lambda r: r.name)
    if foreign:
        lines += ["## 🌍 Foreign-only (consider pruning from the seed)", "",
                  "| Company | ATS | Jobs (all non-Israel) |", "|---|---|---|"]
        lines += [f"| {r.name} | {r.ats_type} | {r.job_count} |" for r in foreign]
        lines.append("")

    lines += ["## All companies", "",
              "| Company | ATS | Status | Jobs | Israeli |", "|---|---|---|---|---|"]
    ordered = sorted(results, key=lambda r: (
        _ORDER.index(r.status) if r.status in _ORDER else 99, r.name))
    lines += [f"| {r.name} | {r.ats_type} | {r.status} | {r.job_count} | {r.israeli_count} |"
              for r in ordered]
    return "\n".join(lines) + "\n"
