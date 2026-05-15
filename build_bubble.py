"""
SSHRC funding trends by Area of Research (2020-2024), filterable by program.
Bubble chart: X = avg award, Y = 5-year trend, size = total FY2024 dollars.
"""

import csv, json, collections, math, textwrap
import plotly.graph_objects as go

YEARS = [2020, 2021, 2022, 2023, 2024]
FILES = {
    yr: rf"C:\Users\calvi\policy-deep-dive-workspace\SSHRC_FY{yr}_Expenditures.csv"
    for yr in YEARS
}

PROGRAMS = [
    "All Programs",
    "Insight Grants",
    "Insight Development Grants",
    "Partnership Grants",
    "Partnership Development Grants",
    "Connection Grants",
    "Partnership Engage Grants",
]

PROG_COLORS = {
    "Insight Grants":                "#1f6aa5",
    "Insight Development Grants":    "#2d8fc4",
    "Partnership Grants":            "#2a9d5c",
    "Partnership Development Grants":"#52b67a",
    "Connection Grants":             "#e07b39",
    "Partnership Engage Grants":     "#f0a860",
    "All Programs":                  "#6c757d",
}

# ── Load data ─────────────────────────────────────────────────────────────────
def load_year(path, fiscal_year):
    # Read all rows, then deduplicate per grant (file number) keeping the lead row
    # (highest amount row per file number, which is usually the lead applicant/institution)
    raw = collections.defaultdict(list)
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            prog = r["Program"]
            if prog not in PROGRAMS[1:]:
                continue
            area_key  = next(k for k in r if "Area_of_Research" in k and "CRSH" not in k)
            disc_key  = next(k for k in r if "Discipline_EN" in k)
            title_key = next(k for k in r if "Title" in k and "Titre" in k)
            try:
                amount = float(r["Amount-Montant"])
            except (ValueError, KeyError):
                amount = 0.0
            file_key = next(k for k in r if "File" in k and "Number" in k)
            raw[r[file_key]].append({
                "fiscal_year": fiscal_year,
                "program":     prog,
                "area":        r.get(area_key, "Not Specified") or "Not Specified",
                "discipline":  r.get(disc_key, "Not specified") or "Not specified",
                "title":       r.get(title_key, ""),
                "amount":      amount,
            })
    # Keep one row per grant: the row with the highest amount (lead role)
    rows = [max(v, key=lambda x: x["amount"]) for v in raw.values()]
    return rows

all_rows = []
for yr in YEARS:
    all_rows.extend(load_year(FILES[yr], yr))

print(f"Total rows loaded: {len(all_rows)}")

# ── Compute bubble data per (program_filter, area) ────────────────────────────
def compute_bubbles(rows, program_filter):
    if program_filter != "All Programs":
        rows = [r for r in rows if r["program"] == program_filter]

    YearArea = collections.defaultdict(lambda: {"total": 0.0, "count": 0, "grants": []})
    for r in rows:
        key = (r["fiscal_year"], r["area"])
        YearArea[key]["total"]  += r["amount"]
        YearArea[key]["count"]  += 1
        if r["fiscal_year"] == 2024:
            YearArea[key]["grants"].append(r)

    areas_2024 = sorted(set(r["area"] for r in rows if r["fiscal_year"] == 2024))

    bubbles = []
    for area in areas_2024:
        d2024 = YearArea[(2024, area)]
        if d2024["count"] == 0:
            continue

        total_2024 = d2024["total"]
        count_2024 = d2024["count"]
        avg_2024   = total_2024 / count_2024

        trend_pct = None
        for base_yr in [2020, 2021, 2022]:
            base = YearArea[(base_yr, area)]
            if base["count"] > 0 and base["total"] > 0:
                trend_pct = (total_2024 - base["total"]) / base["total"] * 100
                break
        if trend_pct is None:
            continue

        yearly = {yr: YearArea[(yr, area)]["total"] for yr in YEARS}

        disc_counts = collections.Counter(
            r["discipline"] for r in d2024["grants"]
        )

        top5 = sorted(d2024["grants"], key=lambda r: r["amount"], reverse=True)[:5]

        def wrap_title(title, amt, width=85):
            lines = textwrap.wrap(title, width=width)
            first = f"  – {lines[0]}"
            rest  = ["    " + l for l in lines[1:]]
            return "<br>".join([first] + rest) + f"  <i>(${amt/1000:.0f}K)</i>"

        yearly_str = "  |  ".join(
            f"{yr}: ${yearly[yr]/1e6:.1f}M" for yr in YEARS if yearly[yr] > 0
        )
        disc_str = "<br>".join(
            f"  • {d} ({n})" for d, n in disc_counts.most_common(6)
        )
        title_str = "<br>".join(wrap_title(r["title"], r["amount"]) for r in top5)
        trend_label = f"+{trend_pct:.0f}%" if trend_pct >= 0 else f"{trend_pct:.0f}%"

        hover = (
            f"<b>{area}</b><br>"
            f"FY2024: ${total_2024/1e6:.1f}M across {count_2024} grants "
            f"(avg ${avg_2024/1000:.0f}K)<br>"
            f"Trend (earliest year → 2024): <b>{trend_label}</b><br>"
            f"<br><b>Year-by-year:</b><br>{yearly_str}<br>"
            f"<br><b>Top disciplines funded:</b><br>{disc_str}<br>"
            f"<br><b>Top 5 largest 2024 projects:</b><br>{title_str}"
        )

        bubbles.append({
            "area":        area,
            "total_2024":  total_2024,
            "count_2024":  count_2024,
            "avg_2024":    avg_2024,
            "trend_pct":   trend_pct,
            "hover":       hover,
        })

    return bubbles

# ── Build one trace per program ───────────────────────────────────────────────
fig = go.Figure()

all_totals = []
for prog in PROGRAMS:
    bubbles = compute_bubbles(all_rows, prog)
    if not bubbles:
        fig.add_trace(go.Scatter(visible=(prog == "All Programs"),
                                 x=[], y=[], mode="markers", name=prog))
        continue

    totals = [b["total_2024"] for b in bubbles]
    all_totals.extend(totals)
    max_t  = max(totals)
    dsizes = [max(8, math.sqrt(t / max_t) * 60) for t in totals]
    color  = PROG_COLORS.get(prog, "#999")

    fig.add_trace(go.Scatter(
        x=[b["avg_2024"] / 1000  for b in bubbles],
        y=[b["trend_pct"]        for b in bubbles],
        mode="markers+text",
        name=prog,
        visible=(prog == "All Programs"),
        marker=dict(
            size=dsizes,
            color=color,
            opacity=0.8,
            line=dict(width=1, color="white"),
        ),
        text=[b["area"] for b in bubbles],
        textposition="top center",
        textfont=dict(size=11),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=[b["hover"] for b in bubbles],
    ))
    print(f"{prog}: {len(bubbles)} areas")

# ── Filter buttons ────────────────────────────────────────────────────────────
buttons = []
for i, prog in enumerate(PROGRAMS):
    visibility = [j == i for j in range(len(PROGRAMS))]
    buttons.append(dict(
        label=prog,
        method="update",
        args=[
            {"visible": visibility},
            {"title.text": (
                f"SSHRC {prog}: Funding by Area of Research (2020–2024)<br>"
                "<sup>X = average award size (FY2024) | Y = % change vs earliest available year | "
                "Bubble size = total FY2024 dollars | Click bubble to pin details</sup>"
            )}
        ],
    ))

fig.update_layout(
    updatemenus=[dict(
        type="buttons",
        direction="right",
        active=0,
        x=0.01, y=1.13,
        xanchor="left",
        buttons=buttons,
        bgcolor="#f8f9fa",
        bordercolor="#dee2e6",
        font=dict(size=12),
    )],
    title=dict(
        text=(
            "SSHRC All Programs: Funding by Area of Research (2020–2024)<br>"
            "<sup>X = average award size (FY2024) | Y = % change vs earliest available year | "
            "Bubble size = total FY2024 dollars | Click bubble to pin details</sup>"
        ),
        font=dict(size=14), x=0.01,
    ),
    xaxis=dict(title="Average Award Size FY2024 ($K)", gridcolor="#eee"),
    yaxis=dict(title="Funding Trend (% change, earliest year → FY2024)",
               gridcolor="#eee", ticksuffix="%"),
    plot_bgcolor="white",
    width=1400,
    height=850,
    margin=dict(t=140, l=80, r=40, b=80),
    showlegend=False,
)

fig.add_hline(y=0, line=dict(color="#666", dash="dash", width=1))

# ── Write HTML and inject click-to-pin JS ─────────────────────────────────────
out = r"C:\Users\calvi\policy-deep-dive-workspace\sshrc_bubble.html"
fig.write_html(out, include_plotlyjs=True)

click_js = """
<div id="sshrc-panel" style="position:fixed;top:80px;right:24px;width:420px;max-height:82vh;
overflow-y:auto;background:#fff;border:1px solid #d0d0d0;border-radius:10px;
padding:18px 20px;box-shadow:0 6px 28px rgba(0,0,0,0.18);font-size:13px;
line-height:1.65;display:none;z-index:9999;font-family:sans-serif;"></div>

<script>
(function() {
    var panel = document.getElementById('sshrc-panel');
    function closePanel() { panel.style.display = 'none'; }
    var myPlot = document.querySelectorAll('.plotly-graph-div')[0];
    myPlot.on('plotly_click', function(data) {
        var pt = data.points[0];
        var content = pt.customdata;
        panel.innerHTML =
            '<div style="text-align:right;margin-bottom:8px;">' +
            '<button id="sshrc-close-btn" style="border:none;background:#eee;' +
            'border-radius:5px;padding:3px 10px;cursor:pointer;font-size:15px;">&#x2715;</button>' +
            '</div>' + content;
        document.getElementById('sshrc-close-btn').onclick = closePanel;
        panel.style.display = 'block';
    });
})();
</script>
"""

with open(out, "r", encoding="utf-8") as f:
    html = f.read()
html = html.replace("</body>", click_js + "\n</body>")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print("Written:", out)
