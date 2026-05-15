"""
SSHRC Insight Grants: funding trends by Area of Research (2020-2024).
Produces an interactive bubble chart where:
  X = average award size (FY2024)
  Y = 5-year funding trend (% change 2020->2024)
  Bubble size = total dollars awarded (FY2024)
  Color = broad thematic grouping
Clicking a bubble opens a drill-down panel of funded disciplines and titles.
"""

import csv, json, collections
import plotly.graph_objects as go

YEARS = [2020, 2021, 2022, 2023, 2024]
FILES = {
    yr: rf"C:\Users\calvi\policy-deep-dive-workspace\SSHRC_FY{yr}_Expenditures.csv"
    for yr in YEARS
}

# ── Load and filter data ──────────────────────────────────────────────────────
def load_year(path, fiscal_year):
    rows = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            if r["Program"] != "Insight Grants":
                continue
            role_key = next(k for k in r if "Role" in k)
            if r[role_key] != "Applicant":
                continue
            comp_key = next(k for k in r if "Competition" in k)
            area_key = next(k for k in r if "Area_of_Research" in k and "CRSH" not in k)
            disc_key = next(k for k in r if "Discipline_EN" in k)
            title_key = next(k for k in r if "Title" in k and "Titre" in k)
            try:
                amount = float(r["Amount-Montant"])
            except (ValueError, KeyError):
                amount = 0.0
            rows.append({
                "fiscal_year": fiscal_year,
                "comp_year": r.get(comp_key, ""),
                "area": r.get(area_key, "Not Specified") or "Not Specified",
                "discipline": r.get(disc_key, "Not specified") or "Not specified",
                "title": r.get(title_key, ""),
                "amount": amount,
            })
    return rows

all_rows = []
for yr in YEARS:
    all_rows.extend(load_year(FILES[yr], yr))

print(f"Total Insight Grant rows: {len(all_rows)}")

# ── Aggregate by area and year ────────────────────────────────────────────────
# Per year per area: total $, grant count
YearArea = collections.defaultdict(lambda: {"total": 0.0, "count": 0})
for r in all_rows:
    key = (r["fiscal_year"], r["area"])
    YearArea[key]["total"] += r["amount"]
    YearArea[key]["count"] += 1

# All areas present in FY2024
areas_2024 = sorted(set(r["area"] for r in all_rows if r["fiscal_year"] == 2024))
print(f"Areas in FY2024: {len(areas_2024)}")

# For each area: total $, grant count, avg award (FY2024) + trend
bubble_data = []
for area in areas_2024:
    d2024 = YearArea[(2024, area)]
    if d2024["count"] == 0:
        continue

    total_2024 = d2024["total"]
    count_2024 = d2024["count"]
    avg_2024 = total_2024 / count_2024

    # Trend: compare 2020 vs 2024 total (% change); use earliest year with data if 2020 missing
    trend_pct = None
    for base_yr in [2020, 2021, 2022]:
        base = YearArea[(base_yr, area)]
        if base["count"] > 0 and base["total"] > 0:
            trend_pct = (total_2024 - base["total"]) / base["total"] * 100
            break

    # Year-by-year totals for sparkline tooltip
    yearly = {yr: YearArea[(yr, area)]["total"] for yr in YEARS}

    # Disciplines funded in FY2024 for this area
    disc_counts = collections.Counter(
        r["discipline"] for r in all_rows
        if r["fiscal_year"] == 2024 and r["area"] == area
    )

    # Sample titles (FY2024, up to 8)
    sample_titles = [
        r["title"] for r in all_rows
        if r["fiscal_year"] == 2024 and r["area"] == area and r["title"]
    ][:8]

    bubble_data.append({
        "area": area,
        "total_2024": total_2024,
        "count_2024": count_2024,
        "avg_2024": avg_2024,
        "trend_pct": trend_pct,
        "yearly": yearly,
        "disciplines": dict(disc_counts.most_common(10)),
        "sample_titles": sample_titles,
    })

# Drop areas with no trend data (only appeared in 2024)
bubble_data = [b for b in bubble_data if b["trend_pct"] is not None]
print(f"Areas with trend data: {len(bubble_data)}")

# ── Colour groupings ──────────────────────────────────────────────────────────
COLOR_MAP = {
    "Health": "#e63946", "Mental Health": "#e63946", "Population studies": "#e63946",
    "Education": "#457b9d", "Post-Secondary Education and Research": "#457b9d",
    "Children": "#457b9d", "Youth": "#457b9d", "Literacy": "#457b9d",
    "Indigenous peoples": "#2d6a4f", "Multiculturalism and ethnic studies": "#2d6a4f",
    "Immigration": "#2d6a4f", "Gender Issues": "#2d6a4f", "Women": "#2d6a4f",
    "Environment and Sustainability": "#52b788", "Global/Climate Change": "#52b788",
    "Energy and natural resources": "#52b788", "Fisheries": "#52b788",
    "Agriculture": "#52b788", "Forestry, Sylviculture": "#52b788",
    "Economics": "#f4a261", "Financial and Monetary Systems": "#f4a261",
    "Employment and labour": "#f4a261", "Productivity": "#f4a261",
    "Economic and Regional Development": "#f4a261", "Poverty": "#f4a261",
    "Politics and government": "#9b5de5", "International Relations, Development and Trade": "#9b5de5",
    "Law and Justice": "#9b5de5",
    "Arts and culture": "#f72585", "Communication": "#f72585",
    "Information Technologies": "#3a86ff", "Science and technology": "#3a86ff",
    "Innovation, Industrial and Technological Development": "#3a86ff",
    "Social development and welfare": "#fb8500",
    "Family": "#fb8500", "Elderly": "#fb8500",
    "Violence": "#fb8500", "Housing": "#fb8500",
}
DEFAULT_COLOR = "#adb5bd"

# ── Build figure ──────────────────────────────────────────────────────────────
xs, ys, sizes, colors, texts, hovers = [], [], [], [], [], []

for b in bubble_data:
    xs.append(b["avg_2024"] / 1000)          # avg award in $K
    ys.append(b["trend_pct"])
    sizes.append(b["total_2024"] / 1_000_000) # bubble size = $M
    colors.append(COLOR_MAP.get(b["area"], DEFAULT_COLOR))
    texts.append(b["area"])

    # Hover card
    yearly_str = "  |  ".join(
        f"{yr}: ${b['yearly'][yr]/1e6:.1f}M" for yr in YEARS if b['yearly'][yr] > 0
    )
    disc_str = "<br>".join(
        f"  • {d} ({n})" for d, n in list(b["disciplines"].items())[:6]
    )
    title_str = "<br>".join(f"  – {t[:75]}…" if len(t) > 75 else f"  – {t}"
                             for t in b["sample_titles"][:5])
    trend_label = f"+{b['trend_pct']:.0f}%" if b["trend_pct"] >= 0 else f"{b['trend_pct']:.0f}%"
    hover = (
        f"<b>{b['area']}</b><br>"
        f"FY2024: ${b['total_2024']/1e6:.1f}M across {b['count_2024']} grants "
        f"(avg ${b['avg_2024']/1000:.0f}K)<br>"
        f"Trend (earliest year → 2024): <b>{trend_label}</b><br>"
        f"<br><b>Year-by-year:</b><br>{yearly_str}<br>"
        f"<br><b>Top disciplines funded:</b><br>{disc_str}<br>"
        f"<br><b>Sample 2024 projects:</b><br>{title_str}"
    )
    hovers.append(hover)

# Normalise bubble sizes for display
import math
max_size = max(sizes)
display_sizes = [max(8, math.sqrt(s / max_size) * 60) for s in sizes]

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=xs, y=ys,
    mode="markers+text",
    marker=dict(
        size=display_sizes,
        color=colors,
        opacity=0.8,
        line=dict(width=1, color="white"),
    ),
    text=texts,
    textposition="top center",
    textfont=dict(size=11),
    hovertemplate="%{customdata}<extra></extra>",
    customdata=hovers,
))

# Quadrant lines
fig.add_hline(y=0, line=dict(color="#666", dash="dash", width=1))
fig.add_vline(x=sum(xs)/len(xs), line=dict(color="#666", dash="dash", width=1))

# Quadrant labels
avg_x = sum(xs) / len(xs)
fig.add_annotation(x=avg_x * 0.3, y=max(ys) * 0.92,
    text="<b>Low award, Growing</b>", showarrow=False,
    font=dict(size=11, color="#555"), bgcolor="rgba(255,255,255,0.7)")
fig.add_annotation(x=max(xs) * 0.85, y=max(ys) * 0.92,
    text="<b>High award, Growing</b>", showarrow=False,
    font=dict(size=11, color="#555"), bgcolor="rgba(255,255,255,0.7)")
fig.add_annotation(x=avg_x * 0.3, y=min(ys) * 0.92,
    text="<b>Low award, Shrinking</b>", showarrow=False,
    font=dict(size=11, color="#555"), bgcolor="rgba(255,255,255,0.7)")
fig.add_annotation(x=max(xs) * 0.85, y=min(ys) * 0.92,
    text="<b>High award, Shrinking</b>", showarrow=False,
    font=dict(size=11, color="#555"), bgcolor="rgba(255,255,255,0.7)")

fig.update_layout(
    title=dict(
        text=(
            "SSHRC Insight Grants: Where is the money going? (2020–2024)<br>"
            "<sup>X = average award size (FY2024) | Y = % change in total funding vs earliest available year | "
            "Bubble size = total FY2024 dollars | Hover for disciplines & sample projects</sup>"
        ),
        font=dict(size=15), x=0.01
    ),
    xaxis=dict(title="Average Award Size FY2024 ($K)", gridcolor="#eee"),
    yaxis=dict(title="Funding Trend (% change, earliest year → FY2024)", gridcolor="#eee",
               ticksuffix="%"),
    plot_bgcolor="white",
    width=1400,
    height=850,
    margin=dict(t=110, l=80, r=40, b=80),
    showlegend=False,
)

out = r"C:\Users\calvi\policy-deep-dive-workspace\sshrc_bubble.html"
fig.write_html(out, include_plotlyjs=True)
print("Written:", out)

# Print summary table
print(f"\n{'Area':<45} {'FY2024 $M':>9} {'Grants':>7} {'Avg $K':>7} {'Trend':>8}")
print("-" * 80)
for b in sorted(bubble_data, key=lambda x: -x["total_2024"]):
    t = f"+{b['trend_pct']:.0f}%" if b["trend_pct"] >= 0 else f"{b['trend_pct']:.0f}%"
    print(f"{b['area']:<45} {b['total_2024']/1e6:>9.1f} {b['count_2024']:>7} "
          f"{b['avg_2024']/1000:>7.0f} {t:>8}")
