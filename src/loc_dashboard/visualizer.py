"""Generate an HTML dashboard with Plotly.js charts from LOC snapshots."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from loc_dashboard.extractor import LOCSnapshot

# Color palette for subdirectories and languages
COLORS = [
    "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899",
    "#06B6D4", "#84CC16", "#F97316", "#14B8A6", "#A855F7",
]
REPO_COLOR = "#4F46E5"


def _fmt(n: int) -> str:
    return f"{n:,}"


def _subdir_label(sd: str) -> str:
    """Turn 'apps/coral-web/' into 'apps/coral-web'."""
    return sd.strip("/")


def _build_loc_growth_chart(snapshots: List[LOCSnapshot], subdirs: List[str]) -> dict:
    months = [s.month for s in snapshots]
    repo = [s.repo_total for s in snapshots]

    traces = [
        {
            "x": months,
            "y": repo,
            "name": "Total repo",
            "type": "scatter",
            "mode": "lines",
            "fill": "tozeroy",
            "line": {"color": REPO_COLOR, "width": 2},
            "fillcolor": "rgba(79, 70, 229, 0.15)",
        }
    ]

    for i, sd in enumerate(subdirs):
        color = COLORS[i % len(COLORS)]
        vals = [s.subdir_totals.get(sd, 0) for s in snapshots]
        traces.append(
            {
                "x": months,
                "y": vals,
                "name": _subdir_label(sd),
                "type": "scatter",
                "mode": "lines",
                "fill": "tozeroy",
                "line": {"color": color, "width": 2},
                "fillcolor": color.replace(")", ", 0.15)").replace("rgb", "rgba")
                if color.startswith("rgb")
                else f"{color}26",
            }
        )

    return {
        "data": traces,
        "layout": {
            "title": "Lines of Code Over Time",
            "xaxis": {"title": "Month"},
            "yaxis": {"title": "Lines of Code"},
            "template": "plotly_white",
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": -0.2},
        },
    }


def _build_monthly_delta_chart(snapshots: List[LOCSnapshot], subdirs: List[str]) -> dict:
    if len(snapshots) < 2:
        return {"data": [], "layout": {"title": "Monthly LOC Growth"}}

    months = [s.month for s in snapshots[1:]]
    repo_delta = [
        snapshots[i].repo_total - snapshots[i - 1].repo_total
        for i in range(1, len(snapshots))
    ]

    traces = [
        {
            "x": months,
            "y": repo_delta,
            "name": "Total repo",
            "type": "bar",
            "marker": {"color": REPO_COLOR},
        }
    ]

    for i, sd in enumerate(subdirs):
        color = COLORS[i % len(COLORS)]
        delta = [
            snapshots[j].subdir_totals.get(sd, 0)
            - snapshots[j - 1].subdir_totals.get(sd, 0)
            for j in range(1, len(snapshots))
        ]
        traces.append(
            {
                "x": months,
                "y": delta,
                "name": _subdir_label(sd),
                "type": "bar",
                "marker": {"color": color},
            }
        )

    return {
        "data": traces,
        "layout": {
            "title": "Monthly LOC Growth (Delta)",
            "xaxis": {"title": "Month"},
            "yaxis": {"title": "Lines Added"},
            "template": "plotly_white",
            "barmode": "group",
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": -0.2},
        },
    }


def _build_subdir_pct_chart(snapshots: List[LOCSnapshot], subdirs: List[str]) -> dict:
    if not subdirs:
        return {"data": [], "layout": {"title": "Subdirectory % of Total"}}

    valid = [s for s in snapshots if s.repo_total > 0]
    months = [s.month for s in valid]

    traces = []
    for i, sd in enumerate(subdirs):
        color = COLORS[i % len(COLORS)]
        pcts = [round(s.subdir_pct(sd), 1) for s in valid]
        traces.append(
            {
                "x": months,
                "y": pcts,
                "name": f"{_subdir_label(sd)} %",
                "type": "scatter",
                "mode": "lines+markers",
                "line": {"color": color, "width": 2},
                "marker": {"size": 6},
            }
        )

    return {
        "data": traces,
        "layout": {
            "title": "Subdirectory as % of Total Codebase",
            "xaxis": {"title": "Month"},
            "yaxis": {"title": "%", "rangemode": "tozero"},
            "template": "plotly_white",
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": -0.2},
        },
    }


def _build_language_breakdown_chart(snapshots: List[LOCSnapshot]) -> dict:
    latest = snapshots[-1]
    langs = sorted(latest.repo_by_lang.items(), key=lambda x: x[1], reverse=True)
    top = langs[:12]
    top.reverse()

    labels = [t[0] for t in top]
    values = [t[1] for t in top]

    return {
        "data": [
            {
                "y": labels,
                "x": values,
                "type": "bar",
                "orientation": "h",
                "marker": {"color": REPO_COLOR},
                "name": "Lines of Code",
            }
        ],
        "layout": {
            "title": f"Language Breakdown (latest: {latest.month})",
            "xaxis": {"title": "Lines of Code"},
            "yaxis": {"title": ""},
            "template": "plotly_white",
            "height": 450,
            "margin": {"l": 120},
        },
    }


def _build_language_trend_chart(snapshots: List[LOCSnapshot], top_n: int = 6) -> dict:
    all_langs: Dict[str, int] = {}
    for s in snapshots:
        for lang, loc in s.repo_by_lang.items():
            all_langs[lang] = max(all_langs.get(lang, 0), loc)

    top_langs = [
        l[0]
        for l in sorted(all_langs.items(), key=lambda x: x[1], reverse=True)[:top_n]
    ]

    months = [s.month for s in snapshots]

    traces = []
    for i, lang in enumerate(top_langs):
        traces.append(
            {
                "x": months,
                "y": [s.repo_by_lang.get(lang, 0) for s in snapshots],
                "name": lang,
                "type": "scatter",
                "mode": "lines",
                "stackgroup": "one",
                "line": {"width": 0.5},
                "fillcolor": COLORS[i % len(COLORS)],
            }
        )

    return {
        "data": traces,
        "layout": {
            "title": f"Top {top_n} Languages Over Time",
            "xaxis": {"title": "Month"},
            "yaxis": {"title": "Lines of Code"},
            "template": "plotly_white",
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": -0.2},
        },
    }


def _build_growth_rate_chart(snapshots: List[LOCSnapshot], subdirs: List[str]) -> dict:
    if len(snapshots) < 2:
        return {"data": [], "layout": {"title": "Growth Rate"}}

    months = []
    repo_rates = []

    for i in range(1, len(snapshots)):
        months.append(snapshots[i].month)
        prev = snapshots[i - 1].repo_total
        curr = snapshots[i].repo_total
        repo_rates.append(round(((curr - prev) / max(prev, 1)) * 100, 1))

    traces = [
        {
            "x": months,
            "y": repo_rates,
            "name": "Total repo",
            "type": "scatter",
            "mode": "lines+markers",
            "line": {"color": REPO_COLOR, "width": 2},
            "marker": {"size": 5},
        }
    ]

    for j, sd in enumerate(subdirs):
        color = COLORS[j % len(COLORS)]
        rates = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1].subdir_totals.get(sd, 0)
            curr = snapshots[i].subdir_totals.get(sd, 0)
            if prev > 0:
                rates.append(round(((curr - prev) / prev) * 100, 1))
            else:
                rates.append(0)
        traces.append(
            {
                "x": months,
                "y": rates,
                "name": _subdir_label(sd),
                "type": "scatter",
                "mode": "lines+markers",
                "line": {"color": color, "width": 2},
                "marker": {"size": 5},
            }
        )

    return {
        "data": traces,
        "layout": {
            "title": "Month-over-Month Growth Rate",
            "xaxis": {"title": "Month"},
            "yaxis": {"title": "Growth %"},
            "template": "plotly_white",
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": -0.2},
        },
    }


def generate_report(
    snapshots: List[LOCSnapshot],
    output_path: str,
    subdirs: List[str] | None = None,
    repo_name: str = "",
) -> None:
    """Generate a self-contained HTML dashboard."""
    subdirs = subdirs or []
    latest = snapshots[-1] if snapshots else None
    first = snapshots[0] if snapshots else None

    if not repo_name and snapshots:
        repo_name = "Repository"

    charts = {
        "loc_growth": _build_loc_growth_chart(snapshots, subdirs),
        "monthly_delta": _build_monthly_delta_chart(snapshots, subdirs),
        "subdir_pct": _build_subdir_pct_chart(snapshots, subdirs),
        "lang_breakdown": _build_language_breakdown_chart(snapshots),
        "lang_trend": _build_language_trend_chart(snapshots),
        "growth_rate": _build_growth_rate_chart(snapshots, subdirs),
    }

    repo_loc = latest.repo_total if latest else 0
    num_months = len(snapshots)

    if len(snapshots) >= 2:
        recent_delta = latest.repo_total - snapshots[-2].repo_total
        recent_delta_str = (
            f"+{_fmt(recent_delta)}" if recent_delta >= 0 else _fmt(recent_delta)
        )
    else:
        recent_delta_str = "N/A"

    top_lang = ""
    if latest and latest.repo_by_lang:
        top_lang = max(latest.repo_by_lang.items(), key=lambda x: x[1])[0]

    # Build subdir metric cards
    subdir_cards = ""
    for sd in subdirs:
        sd_loc = latest.subdir_totals.get(sd, 0) if latest else 0
        sd_pct = latest.subdir_pct(sd) if latest else 0
        subdir_cards += f"""
        <div class="metric-card">
            <h3>{_subdir_label(sd)}</h3>
            <div class="value">{_fmt(sd_loc)}</div>
            <div class="sub">{sd_pct:.1f}% of total</div>
        </div>"""

    # Build subtitle listing subdirs
    subdir_list = ", ".join(_subdir_label(sd) for sd in subdirs)
    subtitle_parts = repo_name
    if subdir_list:
        subtitle_parts += f" &amp; {subdir_list}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LOC Dashboard &mdash; {repo_name}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f3f4f6;
            margin: 0;
            padding: 20px;
            color: #1f2937;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #111827; margin-bottom: 4px; }}
        .subtitle {{ text-align: center; color: #6b7280; margin-bottom: 30px; font-size: 14px; }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .metric-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .metric-card h3 {{
            margin: 0;
            color: #6b7280;
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-card .value {{
            font-size: 30px;
            font-weight: 700;
            color: #111827;
            margin-top: 6px;
        }}
        .metric-card .sub {{
            font-size: 12px;
            color: #9ca3af;
            margin-top: 4px;
        }}
        .chart-box {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(580px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .generated {{
            text-align: center;
            color: #9ca3af;
            font-size: 12px;
            margin-top: 40px;
        }}
        .chart-div {{ width: 100%; height: 420px; }}
        .chart-div-tall {{ width: 100%; height: 450px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>Codebase LOC Dashboard</h1>
    <p class="subtitle">
        {subtitle_parts} &mdash;
        {first.month if first else '?'} to {latest.month if latest else '?'}
        &mdash; measured with <code>cloc</code> at each month-end commit
    </p>

    <div class="metrics-grid">
        <div class="metric-card">
            <h3>Total LOC</h3>
            <div class="value">{_fmt(repo_loc)}</div>
            <div class="sub">Total lines of code</div>
        </div>{subdir_cards}
        <div class="metric-card">
            <h3>Last Month Delta</h3>
            <div class="value">{recent_delta_str}</div>
            <div class="sub">Repo LOC change</div>
        </div>
        <div class="metric-card">
            <h3>Top Language</h3>
            <div class="value" style="font-size:24px">{top_lang}</div>
            <div class="sub">{_fmt(latest.repo_by_lang.get(top_lang, 0)) if latest else 0} lines</div>
        </div>
        <div class="metric-card">
            <h3>Months Tracked</h3>
            <div class="value">{num_months}</div>
            <div class="sub">{first.month if first else '?'} &rarr; {latest.month if latest else '?'}</div>
        </div>
    </div>

    <div class="chart-box">
        <div id="chart-loc-growth" class="chart-div"></div>
    </div>

    <div class="chart-row">
        <div class="chart-box">
            <div id="chart-monthly-delta" class="chart-div"></div>
        </div>
        <div class="chart-box">
            <div id="chart-growth-rate" class="chart-div"></div>
        </div>
    </div>

    <div class="chart-row">
        <div class="chart-box">
            <div id="chart-subdir-pct" class="chart-div"></div>
        </div>
        <div class="chart-box">
            <div id="chart-lang-breakdown" class="chart-div-tall"></div>
        </div>
    </div>

    <div class="chart-box">
        <div id="chart-lang-trend" class="chart-div"></div>
    </div>

    <p class="generated">
        Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        &mdash; data from <code>cloc</code> snapshots via <code>git archive</code>
    </p>
</div>

<script>
    var cfg = {{responsive: true}};
"""

    for chart_id, spec in charts.items():
        div_id = f"chart-{chart_id.replace('_', '-')}"
        html += f"    Plotly.newPlot('{div_id}', {json.dumps(spec['data'])}, {json.dumps(spec['layout'])}, cfg);\n"

    html += """</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
