"""
SSHRC 5-Tab Interactive Dashboard
Generates sshrc_dashboard.html from FY2020-FY2024 expenditure CSVs.

Tabs:
  1. Funding Landscape  — bubble chart by area of research
  2. Strategic Alignment — heatmap vs federal / BC priorities
  3. Provincial Distribution — horizontal bar chart
  4. Institutional Landscape — top-25 institutions
  5. 5-Year Trajectories — multi-line area trends
"""

import csv
import json
import math
import os
import textwrap
import collections

import plotly
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

# ── Constants ──────────────────────────────────────────────────────────────────

YEARS = [2020, 2021, 2022, 2023, 2024]
BASE_DIR = r"C:\Users\calvi\policy-deep-dive-workspace"
FILES = {yr: os.path.join(BASE_DIR, f"SSHRC_FY{yr}_Expenditures.csv") for yr in YEARS}
OUT_HTML = os.path.join(BASE_DIR, "sshrc_dashboard.html")

PROGRAMS = [
    "Insight Grants",
    "Insight Development Grants",
    "Partnership Grants",
    "Partnership Development Grants",
    "Connection Grants",
    "Partnership Engage Grants",
]

PROG_COLORS = {
    "Insight Grants":                 "#1f6aa5",
    "Insight Development Grants":     "#2d8fc4",
    "Partnership Grants":             "#2a9d5c",
    "Partnership Development Grants": "#52b67a",
    "Connection Grants":              "#e07b39",
    "Partnership Engage Grants":      "#f0a860",
    "All Programs":                   "#6c757d",
}

# ── Data loading ───────────────────────────────────────────────────────────────

def load_year(path, fiscal_year):
    """
    Load one fiscal-year CSV. Deduplicate by File_Number, keeping the row with
    the highest Amount-Montant (lead applicant / institution row).
    Returns a list of dicts.
    """
    raw = collections.defaultdict(list)
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            prog = r.get("Program", "")
            if prog not in PROGRAMS:
                continue
            # Locate mangled column names
            area_key  = next((k for k in r if "Area_of_Research" in k and "CRSH" not in k), None)
            disc_key  = next((k for k in r if "Discipline_EN" in k), None)
            title_key = next((k for k in r if "Title" in k and "Titre" in k), None)
            role_key  = next((k for k in r if "Role" in k), None)
            comp_key  = next((k for k in r if "Competition" in k), None)
            file_key  = next((k for k in r if "File" in k and "Number" in k), None)

            if not file_key:
                continue
            try:
                amount = float(r["Amount-Montant"])
            except (ValueError, KeyError):
                amount = 0.0

            raw[r[file_key]].append({
                "fiscal_year":   fiscal_year,
                "program":       prog,
                "area":          (r.get(area_key, "") or "Not Specified") if area_key else "Not Specified",
                "discipline":    (r.get(disc_key, "") or "Not specified") if disc_key else "Not specified",
                "title":         (r.get(title_key, "") or "") if title_key else "",
                "role":          (r.get(role_key, "") or "") if role_key else "",
                "institution":   r.get("Institution", "") or "",
                "province":      r.get("Province_EN", "") or "",
                "comp_year":     (r.get(comp_key, "") or "") if comp_key else "",
                "amount":        amount,
            })

    # Keep lead row per grant (highest amount)
    rows = [max(v, key=lambda x: x["amount"]) for v in raw.values()]
    return rows


def load_all():
    """Load all fiscal years and return combined list."""
    all_rows = []
    for yr in YEARS:
        yr_rows = load_year(FILES[yr], yr)
        print(f"  FY{yr}: {len(yr_rows)} grants loaded")
        all_rows.extend(yr_rows)
    print(f"  Total: {len(all_rows)} grant-year records\n")
    return all_rows


# ── Tab 1: Funding Landscape (bubble chart) ────────────────────────────────────

def compute_bubbles(rows, program_filter):
    """
    For a given program filter, compute per-area metrics for the bubble chart.
    Returns list of bubble dicts or empty list.
    """
    if program_filter != "All Programs":
        rows = [r for r in rows if r["program"] == program_filter]

    # Accumulate by (year, area)
    YearArea = collections.defaultdict(lambda: {"total": 0.0, "count": 0, "grants": []})
    for r in rows:
        key = (r["fiscal_year"], r["area"])
        YearArea[key]["total"] += r["amount"]
        YearArea[key]["count"] += 1
        if r["fiscal_year"] == 2024:
            YearArea[key]["grants"].append(r)

    areas_2024 = sorted(set(r["area"] for r in rows if r["fiscal_year"] == 2024))

    def wrap_title(title, amt, width=85):
        lines = textwrap.wrap(title, width=width)
        first = f"  – {lines[0]}" if lines else "  – (untitled)"
        rest  = ["    " + l for l in lines[1:]]
        return "<br>".join([first] + rest) + f"  <i>(${amt/1000:.0f}K)</i>"

    bubbles = []
    for area in areas_2024:
        d2024 = YearArea[(2024, area)]
        if d2024["count"] == 0:
            continue

        total_2024 = d2024["total"]
        count_2024 = d2024["count"]
        avg_2024   = total_2024 / count_2024

        # Trend from earliest available base year
        trend_pct = None
        for base_yr in [2020, 2021, 2022]:
            base = YearArea[(base_yr, area)]
            if base["count"] > 0 and base["total"] > 0:
                trend_pct = (total_2024 - base["total"]) / base["total"] * 100
                break
        if trend_pct is None:
            continue

        yearly = {yr: YearArea[(yr, area)]["total"] for yr in YEARS}

        disc_counts = collections.Counter(r["discipline"] for r in d2024["grants"])
        top5 = sorted(d2024["grants"], key=lambda r: r["amount"], reverse=True)[:5]

        yearly_str = "  |  ".join(
            f"{yr}: ${yearly[yr]/1e6:.1f}M" for yr in YEARS if yearly[yr] > 0
        )
        disc_str = "<br>".join(f"  • {d} ({n})" for d, n in disc_counts.most_common(6))
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
            "area":       area,
            "total_2024": total_2024,
            "count_2024": count_2024,
            "avg_2024":   avg_2024,
            "trend_pct":  trend_pct,
            "hover":      hover,
        })

    return bubbles


def build_tab1(all_rows):
    """Build Tab 1: Funding Landscape bubble chart."""
    prog_list = ["All Programs"] + PROGRAMS
    fig = go.Figure()

    area_count = 0
    for prog in prog_list:
        bubbles = compute_bubbles(all_rows, prog)
        if not bubbles:
            fig.add_trace(go.Scatter(
                visible=(prog == "All Programs"),
                x=[], y=[], mode="markers", name=prog
            ))
            continue

        if prog == "All Programs":
            area_count = len(bubbles)

        totals = [b["total_2024"] for b in bubbles]
        max_t  = max(totals)
        dsizes = [max(8, math.sqrt(t / max_t) * 60) for t in totals]
        color  = PROG_COLORS.get(prog, "#999")

        fig.add_trace(go.Scatter(
            x=[b["avg_2024"] / 1000 for b in bubbles],
            y=[b["trend_pct"]       for b in bubbles],
            mode="markers+text",
            name=prog,
            visible=(prog == "All Programs"),
            marker=dict(
                size=dsizes, color=color, opacity=0.8,
                line=dict(width=1, color="white"),
            ),
            text=[b["area"] for b in bubbles],
            textposition="top center",
            textfont=dict(size=11),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=[b["hover"] for b in bubbles],
        ))

    # Program filter buttons
    buttons = []
    for i, prog in enumerate(prog_list):
        visibility = [j == i for j in range(len(prog_list))]
        buttons.append(dict(
            label=prog,
            method="update",
            args=[
                {"visible": visibility},
                {"title.text": (
                    f"SSHRC {prog}: Funding by Area of Research (2020–2024)<br>"
                    "<sup>X = avg award size (FY2024) | Y = % change vs earliest year | "
                    "Bubble size = total FY2024 dollars | Click to pin details</sup>"
                )}
            ],
        ))

    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="right", active=0,
            x=0.01, y=1.13, xanchor="left",
            buttons=buttons,
            bgcolor="#f8f9fa", bordercolor="#dee2e6", font=dict(size=11),
        )],
        title=dict(
            text=(
                "SSHRC All Programs: Funding by Area of Research (2020–2024)<br>"
                "<sup>X = avg award size (FY2024) | Y = % change vs earliest year | "
                "Bubble size = total FY2024 dollars | Click bubble to pin details</sup>"
            ),
            font=dict(size=14), x=0.01,
        ),
        xaxis=dict(title="Average Award Size FY2024 ($K)", gridcolor="#eee"),
        yaxis=dict(
            title="Funding Trend (% change, earliest year → FY2024)",
            gridcolor="#eee", ticksuffix="%",
        ),
        plot_bgcolor="white",
        height=780,
        margin=dict(t=150, l=80, r=40, b=80),
        showlegend=False,
    )
    fig.add_hline(y=0, line=dict(color="#666", dash="dash", width=1))

    return fig, area_count


# ── Tab 2: Strategic Alignment (heatmap) ──────────────────────────────────────

FEDERAL_PRIORITIES = [
    "Economic Sovereignty & Trade",
    "Defence & National Security",
    "AI & Digital Technology",
    "Clean Economy & Climate",
    "Housing & Communities",
    "Indigenous Peoples",
    "Health & Wellbeing",
    "Labour & Workforce",
]

BC_PRIORITIES = [
    "Mental Health & Substance Use",
    "Clean Energy & Climate Adaptation",
    "Look West — Economic Diversification",
    "Life Sciences & Health Innovation",
    "Technology & Innovation",
    "Poverty Reduction & Social Equity",
    "Indigenous Reconciliation",
]

FEDERAL_ALIGNMENT = {
    # Economic Sovereignty & Trade
    ("Economic Sovereignty & Trade", "Financial and Monetary Systems"): 3,
    ("Economic Sovereignty & Trade", "International Relations, Development and Trade"): 3,
    ("Economic Sovereignty & Trade", "Economic and Regional Development"): 2,
    ("Economic Sovereignty & Trade", "Management"): 2,
    ("Economic Sovereignty & Trade", "Globalization"): 2,
    ("Economic Sovereignty & Trade", "Employment and labour"): 1,
    ("Economic Sovereignty & Trade", "Productivity"): 2,
    ("Economic Sovereignty & Trade", "Innovation, Industrial and Technological Development"): 2,
    # Defence & National Security
    ("Defence & National Security", "Politics and government"): 2,
    ("Defence & National Security", "Law and Justice"): 2,
    ("Defence & National Security", "International Relations, Development and Trade"): 2,
    ("Defence & National Security", "Communication"): 1,
    # AI & Digital Technology
    ("AI & Digital Technology", "Information Technologies"): 3,
    ("AI & Digital Technology", "Science and technology"): 2,
    ("AI & Digital Technology", "Innovation, Industrial and Technological Development"): 2,
    ("AI & Digital Technology", "Communication"): 2,
    ("AI & Digital Technology", "Management"): 1,
    ("AI & Digital Technology", "Education"): 1,
    # Clean Economy & Climate
    ("Clean Economy & Climate", "Global/Climate Change"): 3,
    ("Clean Economy & Climate", "Environment and Sustainability"): 3,
    ("Clean Economy & Climate", "Energy and natural resources"): 3,
    ("Clean Economy & Climate", "Agriculture"): 2,
    ("Clean Economy & Climate", "Fisheries"): 2,
    ("Clean Economy & Climate", "Northern development"): 2,
    ("Clean Economy & Climate", "Economic and Regional Development"): 1,
    # Housing & Communities
    ("Housing & Communities", "Housing"): 3,
    ("Housing & Communities", "Social development and welfare"): 2,
    ("Housing & Communities", "Poverty"): 2,
    ("Housing & Communities", "Economic and Regional Development"): 2,
    ("Housing & Communities", "Family"): 1,
    ("Housing & Communities", "Children"): 1,
    ("Housing & Communities", "Immigration"): 2,
    # Indigenous Peoples
    ("Indigenous Peoples", "Indigenous peoples"): 3,
    ("Indigenous Peoples", "Multiculturalism and ethnic studies"): 2,
    ("Indigenous Peoples", "Northern development"): 2,
    ("Indigenous Peoples", "Law and Justice"): 1,
    ("Indigenous Peoples", "Arts and culture"): 1,
    # Health & Wellbeing
    ("Health & Wellbeing", "Health"): 3,
    ("Health & Wellbeing", "Mental Health"): 3,
    ("Health & Wellbeing", "Population studies"): 3,
    ("Health & Wellbeing", "Children"): 2,
    ("Health & Wellbeing", "Elderly"): 2,
    ("Health & Wellbeing", "Family"): 2,
    ("Health & Wellbeing", "Violence"): 2,
    ("Health & Wellbeing", "Gender Issues"): 1,
    # Labour & Workforce
    ("Labour & Workforce", "Employment and labour"): 3,
    ("Labour & Workforce", "Education"): 2,
    ("Labour & Workforce", "Gender Issues"): 2,
    ("Labour & Workforce", "Youth"): 2,
    ("Labour & Workforce", "Immigration"): 2,
    ("Labour & Workforce", "Social development and welfare"): 1,
    ("Labour & Workforce", "Post-Secondary Education and Research"): 2,
}

BC_ALIGNMENT = {
    # Mental Health & Substance Use
    ("Mental Health & Substance Use", "Mental Health"): 3,
    ("Mental Health & Substance Use", "Health"): 2,
    ("Mental Health & Substance Use", "Violence"): 2,
    ("Mental Health & Substance Use", "Social development and welfare"): 2,
    ("Mental Health & Substance Use", "Population studies"): 2,
    ("Mental Health & Substance Use", "Children"): 1,
    ("Mental Health & Substance Use", "Family"): 1,
    ("Mental Health & Substance Use", "Indigenous peoples"): 1,
    # Clean Energy & Climate Adaptation
    ("Clean Energy & Climate Adaptation", "Global/Climate Change"): 3,
    ("Clean Energy & Climate Adaptation", "Environment and Sustainability"): 3,
    ("Clean Energy & Climate Adaptation", "Energy and natural resources"): 3,
    ("Clean Energy & Climate Adaptation", "Agriculture"): 2,
    ("Clean Energy & Climate Adaptation", "Fisheries"): 2,
    ("Clean Energy & Climate Adaptation", "Northern development"): 1,
    ("Clean Energy & Climate Adaptation", "Science and technology"): 1,
    # Look West — Economic Diversification
    ("Look West — Economic Diversification", "International Relations, Development and Trade"): 3,
    ("Look West — Economic Diversification", "Financial and Monetary Systems"): 3,
    ("Look West — Economic Diversification", "Economic and Regional Development"): 3,
    ("Look West — Economic Diversification", "Management"): 2,
    ("Look West — Economic Diversification", "Innovation, Industrial and Technological Development"): 2,
    ("Look West — Economic Diversification", "Globalization"): 2,
    ("Look West — Economic Diversification", "Employment and labour"): 1,
    # Life Sciences & Health Innovation
    ("Life Sciences & Health Innovation", "Health"): 3,
    ("Life Sciences & Health Innovation", "Biotechnology"): 3,
    ("Life Sciences & Health Innovation", "Population studies"): 2,
    ("Life Sciences & Health Innovation", "Science and technology"): 2,
    ("Life Sciences & Health Innovation", "Ethics"): 1,
    ("Life Sciences & Health Innovation", "Environment and Sustainability"): 1,
    # Technology & Innovation
    ("Technology & Innovation", "Information Technologies"): 3,
    ("Technology & Innovation", "Innovation, Industrial and Technological Development"): 3,
    ("Technology & Innovation", "Science and technology"): 2,
    ("Technology & Innovation", "Communication"): 2,
    ("Technology & Innovation", "Management"): 1,
    ("Technology & Innovation", "Education"): 1,
    # Poverty Reduction & Social Equity
    ("Poverty Reduction & Social Equity", "Poverty"): 3,
    ("Poverty Reduction & Social Equity", "Social development and welfare"): 3,
    ("Poverty Reduction & Social Equity", "Housing"): 2,
    ("Poverty Reduction & Social Equity", "Immigration"): 2,
    ("Poverty Reduction & Social Equity", "Gender Issues"): 2,
    ("Poverty Reduction & Social Equity", "Children"): 2,
    ("Poverty Reduction & Social Equity", "Employment and labour"): 2,
    ("Poverty Reduction & Social Equity", "Education"): 1,
    ("Poverty Reduction & Social Equity", "Multiculturalism and ethnic studies"): 1,
    # Indigenous Reconciliation
    ("Indigenous Reconciliation", "Indigenous peoples"): 3,
    ("Indigenous Reconciliation", "Multiculturalism and ethnic studies"): 2,
    ("Indigenous Reconciliation", "Law and Justice"): 2,
    ("Indigenous Reconciliation", "Northern development"): 2,
    ("Indigenous Reconciliation", "Arts and culture"): 1,
    ("Indigenous Reconciliation", "Education"): 1,
}

# Short one-sentence explanation per priority
PRIORITY_DESCRIPTIONS = {
    "Economic Sovereignty & Trade": "SSHRC research on trade systems and economic governance directly supports Canada's sovereign economic strategy.",
    "Defence & National Security": "SSHRC funds social-science research on governance, law, and communications relevant to national security.",
    "AI & Digital Technology": "Information technology and innovation research aligns with federal AI and digital economy investments.",
    "Clean Economy & Climate": "Climate, environment, and energy research underpins the science base for clean-economy transitions.",
    "Housing & Communities": "Housing, poverty, and community development research informs policies on affordability and urban resilience.",
    "Indigenous Peoples": "Indigenous peoples research supports reconciliation, self-determination, and culturally grounded policy.",
    "Health & Wellbeing": "Health, mental health, and population studies provide the social-science evidence base for wellbeing policy.",
    "Labour & Workforce": "Employment, education, and workforce research helps design inclusive labour-market and skills policies.",
    "Mental Health & Substance Use": "Mental health and violence research addresses BC's highest-profile public-health crisis.",
    "Clean Energy & Climate Adaptation": "Climate-change and energy research supports BC's leading role in clean-energy transition.",
    "Look West — Economic Diversification": "Trade, regional development, and globalization research supports BC's Pacific-facing economic strategy.",
    "Life Sciences & Health Innovation": "Health and biotechnology research anchors BC's life-sciences cluster ambitions.",
    "Technology & Innovation": "IT and innovation research supports BC's growing technology sector.",
    "Poverty Reduction & Social Equity": "Poverty, welfare, and equity research guides BC's poverty-reduction and inclusion agenda.",
    "Indigenous Reconciliation": "Indigenous peoples research directly supports BC's constitutional and policy commitments to reconciliation.",
}


def build_tab2(all_rows):
    """Build Tab 2: Strategic Alignment heatmap (Federal + BC views)."""
    # Get all unique areas from FY2024 data
    rows_2024 = [r for r in all_rows if r["fiscal_year"] == 2024]

    # Compute area-level FY2024 totals and 5-year trend
    area_stats = collections.defaultdict(lambda: {yr: 0.0 for yr in YEARS})
    area_counts = collections.defaultdict(int)
    for r in all_rows:
        area_stats[r["area"]][r["fiscal_year"]] += r["amount"]
    for r in rows_2024:
        area_counts[r["area"]] += 1

    areas_2024 = sorted(area_stats.keys(), key=lambda a: area_stats[a][2024], reverse=True)

    max_funding = max((area_stats[a][2024] for a in areas_2024), default=1)

    def build_heatmap_data(priorities, alignment_dict):
        """
        Build z matrix (weighted score), text matrix (raw score), and hover matrix.
        Rows = priorities, Cols = areas_2024
        """
        z_matrix   = []
        text_matrix = []
        hover_matrix = []

        for prio in priorities:
            z_row    = []
            text_row = []
            hover_row = []
            for area in areas_2024:
                raw_score = alignment_dict.get((prio, area), 0)
                funding   = area_stats[area][2024]
                # Weighted: score × (funding / max_funding), scaled to 0–3
                weighted  = raw_score * (funding / max_funding) if raw_score > 0 else 0.0

                strength_label = {1: "Weak", 2: "Medium", 3: "Strong"}.get(raw_score, "")
                trend_str = ""
                for base_yr in [2020, 2021, 2022]:
                    base_f = area_stats[area][base_yr]
                    if base_f > 0:
                        pct = (funding - base_f) / base_f * 100
                        trend_str = f"{pct:+.0f}% vs FY{base_yr}"
                        break

                count  = area_counts[area]
                desc   = PRIORITY_DESCRIPTIONS.get(prio, "")

                hover  = (
                    f"<b>{prio}</b> × <b>{area}</b><br>"
                    f"Alignment: {strength_label if raw_score else 'None'} ({raw_score}/3)<br>"
                    f"FY2024 funding: ${funding/1e6:.1f}M ({count} grants)<br>"
                    f"5-year trend: {trend_str}<br>"
                    f"<i>{desc}</i>"
                )

                z_row.append(round(weighted, 3))
                text_row.append(str(raw_score) if raw_score > 0 else "")
                hover_row.append(hover)

            z_matrix.append(z_row)
            text_matrix.append(text_row)
            hover_matrix.append(hover_row)

        return z_matrix, text_matrix, hover_matrix

    z_fed, txt_fed, hov_fed = build_heatmap_data(FEDERAL_PRIORITIES, FEDERAL_ALIGNMENT)
    z_bc,  txt_bc,  hov_bc  = build_heatmap_data(BC_PRIORITIES, BC_ALIGNMENT)

    # Shorten area labels for display (max 28 chars)
    short_areas = [a if len(a) <= 30 else a[:27] + "…" for a in areas_2024]

    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        z=z_fed,
        x=short_areas,
        y=FEDERAL_PRIORITIES,
        text=txt_fed,
        texttemplate="%{text}",
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hov_fed,
        colorscale="Blues",
        zmin=0, zmax=3,
        showscale=True,
        colorbar=dict(
            title="Weighted<br>Score",
            tickvals=[0, 1, 2, 3],
            ticktext=["0 – None", "1 – Weak", "2 – Medium", "3 – Strong"],
        ),
        visible=True,
        name="Federal",
        xgap=2, ygap=2,
    ))

    fig.add_trace(go.Heatmap(
        z=z_bc,
        x=short_areas,
        y=BC_PRIORITIES,
        text=txt_bc,
        texttemplate="%{text}",
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hov_bc,
        colorscale="Blues",
        zmin=0, zmax=3,
        showscale=True,
        colorbar=dict(
            title="Weighted<br>Score",
            tickvals=[0, 1, 2, 3],
            ticktext=["0 – None", "1 – Weak", "2 – Medium", "3 – Strong"],
        ),
        visible=False,
        name="BC",
        xgap=2, ygap=2,
    ))

    fig.update_layout(
        updatemenus=[dict(
            type="buttons",
            direction="right",
            active=0,
            x=0.01, y=1.10,
            xanchor="left",
            buttons=[
                dict(
                    label="Federal (Budget 2026)",
                    method="update",
                    args=[
                        {"visible": [True, False]},
                        {"title.text": "Strategic Alignment: SSHRC Research Areas × Federal Budget 2026 Priorities<br><sup>Cell colour = alignment strength × FY2024 funding share; number = raw alignment score (1–3)</sup>"},
                    ],
                ),
                dict(
                    label="British Columbia",
                    method="update",
                    args=[
                        {"visible": [False, True]},
                        {"title.text": "Strategic Alignment: SSHRC Research Areas × British Columbia Priorities<br><sup>Cell colour = alignment strength × FY2024 funding share; number = raw alignment score (1–3)</sup>"},
                    ],
                ),
            ],
            bgcolor="#f8f9fa",
            bordercolor="#dee2e6",
            font=dict(size=12),
        )],
        title=dict(
            text="Strategic Alignment: SSHRC Research Areas × Federal Budget 2026 Priorities<br><sup>Cell colour = alignment strength × FY2024 funding share; number = raw alignment score (1–3)</sup>",
            font=dict(size=14), x=0.01,
        ),
        xaxis=dict(
            tickangle=-45, tickfont=dict(size=9),
            title="SSHRC Area of Research",
        ),
        yaxis=dict(tickfont=dict(size=11)),
        height=520,
        margin=dict(t=140, l=260, r=40, b=200),
        plot_bgcolor="white",
    )

    return fig, len(areas_2024)


# ── Tab 3: Provincial Distribution ────────────────────────────────────────────

def build_tab3(all_rows):
    """Build Tab 3: Provincial distribution horizontal bar chart + BC share panel."""
    prog_list = ["All Programs"] + PROGRAMS
    fig = go.Figure()

    # We'll need two sub-panels: province totals (main), BC share by program (secondary)
    # Encode both as separate traces that we toggle via updatemenus

    # For each program filter, build:
    #  (a) province bars (FY2024)
    #  (b) BC-share bars by program (FY2024, always across all programs)

    provinces_all = set()
    for r in all_rows:
        if r["fiscal_year"] == 2024 and r["province"]:
            provinces_all.add(r["province"])

    bc_share_rows = [r for r in all_rows if r["fiscal_year"] == 2024]
    bc_share_by_prog = {}
    nat_total_by_prog = {}
    for prog in PROGRAMS:
        bc_total  = sum(r["amount"] for r in bc_share_rows if r["program"] == prog and r["province"] == "British Columbia")
        nat_total = sum(r["amount"] for r in bc_share_rows if r["program"] == prog)
        bc_share_by_prog[prog]  = bc_total
        nat_total_by_prog[prog] = nat_total

    for i_prog, prog_filter in enumerate(prog_list):
        rows_2024 = [r for r in all_rows if r["fiscal_year"] == 2024]
        if prog_filter != "All Programs":
            rows_2024 = [r for r in rows_2024 if r["program"] == prog_filter]

        # Aggregate by province
        prov_totals = collections.defaultdict(lambda: {"total": 0.0, "count": 0})
        for r in rows_2024:
            pv = r["province"] or "Unknown"
            prov_totals[pv]["total"] += r["amount"]
            prov_totals[pv]["count"] += 1

        sorted_provs = sorted(prov_totals.keys(), key=lambda p: prov_totals[p]["total"], reverse=True)
        national_total = sum(prov_totals[p]["total"] for p in sorted_provs)

        bar_colors = [
            "#1f6aa5" if p == "British Columbia" else "#adb5bd"
            for p in sorted_provs
        ]

        hover_texts = []
        for pv in sorted_provs:
            t = prov_totals[pv]["total"]
            c = prov_totals[pv]["count"]
            avg_k = (t / c / 1000) if c else 0
            bc_context = (
                f"<br>BC share of national: {t/national_total*100:.1f}%"
                if pv == "British Columbia" else ""
            )
            hover_texts.append(
                f"<b>{pv}</b><br>Total: ${t/1e6:.1f}M<br>"
                f"Grants: {c}<br>Avg award: ${avg_k:.0f}K{bc_context}"
            )

        fig.add_trace(go.Bar(
            x=[prov_totals[p]["total"] / 1e6 for p in sorted_provs],
            y=sorted_provs,
            orientation="h",
            marker_color=bar_colors,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            visible=(prog_filter == "All Programs"),
            name=prog_filter,
            showlegend=False,
        ))

    buttons = []
    for i, prog in enumerate(prog_list):
        visibility = [j == i for j in range(len(prog_list))]
        buttons.append(dict(
            label=prog,
            method="update",
            args=[
                {"visible": visibility},
                {"title.text": f"Provincial Distribution – FY2024 SSHRC Funding ({prog})<br><sup>BC highlighted in blue; hover for details</sup>"},
            ],
        ))

    # BC share annotation panel (static inset as shapes/annotations for the default view)
    # Render as a second subplot using domain approach with subplots module would be complex;
    # instead, add a static annotation block with BC share by program
    bc_share_lines = []
    nat_total_all = sum(nat_total_by_prog[p] for p in PROGRAMS)
    bc_total_all  = sum(bc_share_by_prog[p] for p in PROGRAMS)
    bc_share_lines.append(f"<b>BC Share of National FY2024 Total:</b> {bc_total_all/nat_total_all*100:.1f}%")
    for prog in PROGRAMS:
        nt = nat_total_by_prog[prog]
        bt = bc_share_by_prog[prog]
        share = (bt / nt * 100) if nt > 0 else 0
        bc_share_lines.append(f"  • {prog[:30]}: {share:.1f}%")

    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="right", active=0,
            x=0.01, y=1.10, xanchor="left",
            buttons=buttons,
            bgcolor="#f8f9fa", bordercolor="#dee2e6", font=dict(size=11),
        )],
        title=dict(
            text="Provincial Distribution – FY2024 SSHRC Funding (All Programs)<br><sup>BC highlighted in blue; hover for details</sup>",
            font=dict(size=14), x=0.01,
        ),
        xaxis=dict(title="Total Funding FY2024 ($M)", gridcolor="#eee"),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="white",
        height=600,
        margin=dict(t=140, l=200, r=280, b=60),
        annotations=[dict(
            x=1.01, y=0.98,
            xref="paper", yref="paper",
            text="<br>".join(bc_share_lines),
            showarrow=False,
            align="left",
            font=dict(size=11),
            bgcolor="rgba(248,249,250,0.9)",
            bordercolor="#dee2e6",
            borderwidth=1,
            borderpad=8,
        )],
    )

    n_provinces = len(provinces_all)
    return fig, n_provinces


# ── Tab 4: Institutional Landscape ────────────────────────────────────────────

def build_tab4(all_rows):
    """Build Tab 4: Top-25 institutions by FY2024 funding."""
    prog_list = ["All Programs"] + PROGRAMS
    fig = go.Figure()

    # We need institution → province mapping
    inst_province = {}
    for r in all_rows:
        if r["institution"] and r["province"]:
            inst_province[r["institution"]] = r["province"]

    n_institutions = 0

    for i_prog, prog_filter in enumerate(prog_list):
        rows_2024 = [r for r in all_rows if r["fiscal_year"] == 2024]
        if prog_filter != "All Programs":
            rows_2024 = [r for r in rows_2024 if r["program"] == prog_filter]

        # Aggregate by institution
        inst_stats = collections.defaultdict(lambda: {"total": 0.0, "count": 0, "areas": []})
        for r in rows_2024:
            inst = r["institution"] or "Unknown"
            inst_stats[inst]["total"] += r["amount"]
            inst_stats[inst]["count"] += 1
            inst_stats[inst]["areas"].append(r["area"])

        top25 = sorted(inst_stats.keys(), key=lambda i: inst_stats[i]["total"], reverse=True)[:25]

        if prog_filter == "All Programs":
            n_institutions = len(inst_stats)

        bc_insts = {i for i in top25 if inst_province.get(i, "") == "British Columbia"}

        bar_colors = ["#1f6aa5" if i in bc_insts else "#adb5bd" for i in top25]

        hover_texts = []
        for inst in top25:
            t     = inst_stats[inst]["total"]
            c     = inst_stats[inst]["count"]
            avg_k = (t / c / 1000) if c else 0
            prov  = inst_province.get(inst, "Unknown")
            top3  = [a for a, _ in collections.Counter(inst_stats[inst]["areas"]).most_common(3)]
            areas_str = ", ".join(top3) if top3 else "N/A"
            hover_texts.append(
                f"<b>{inst}</b><br>Province: {prov}<br>Total: ${t/1e6:.1f}M<br>"
                f"Grants: {c}<br>Avg award: ${avg_k:.0f}K<br>"
                f"Top areas: {areas_str}"
            )

        fig.add_trace(go.Bar(
            x=[inst_stats[i]["total"] / 1e6 for i in top25],
            y=top25,
            orientation="h",
            marker_color=bar_colors,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            visible=(prog_filter == "All Programs"),
            name=prog_filter,
            showlegend=False,
        ))

    buttons = []
    for i, prog in enumerate(prog_list):
        visibility = [j == i for j in range(len(prog_list))]
        buttons.append(dict(
            label=prog,
            method="update",
            args=[
                {"visible": visibility},
                {"title.text": f"Top 25 Institutions – FY2024 SSHRC Funding ({prog})<br><sup>BC institutions in blue; hover for details</sup>"},
            ],
        ))

    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="right", active=0,
            x=0.01, y=1.10, xanchor="left",
            buttons=buttons,
            bgcolor="#f8f9fa", bordercolor="#dee2e6", font=dict(size=11),
        )],
        title=dict(
            text="Top 25 Institutions – FY2024 SSHRC Funding (All Programs)<br><sup>BC institutions in blue; hover for details</sup>",
            font=dict(size=14), x=0.01,
        ),
        xaxis=dict(title="Total Funding FY2024 ($M)", gridcolor="#eee"),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="white",
        height=750,
        margin=dict(t=140, l=280, r=60, b=60),
    )

    return fig, n_institutions


# ── Tab 5: 5-Year Trajectories ────────────────────────────────────────────────

# Areas with strong federal / BC priority alignment (score >= 2 in any priority)
FEDERAL_PRIORITY_AREAS = {
    a for (_, a), s in FEDERAL_ALIGNMENT.items() if s >= 2
}
BC_PRIORITY_AREAS = {
    a for (_, a), s in BC_ALIGNMENT.items() if s >= 2
}


def build_tab5(all_rows):
    """Build Tab 5: 5-Year Trajectories multi-line chart."""
    prog_list = ["All Programs"] + PROGRAMS

    # Compute all area × year funding
    area_year_totals = collections.defaultdict(lambda: collections.defaultdict(float))
    area_year_counts = collections.defaultdict(lambda: collections.defaultdict(int))

    for r in all_rows:
        area_year_totals[r["area"]][r["fiscal_year"]] += r["amount"]
        area_year_counts[r["area"]][r["fiscal_year"]] += 1

    # Top 10 areas by FY2024 funding (across all programs)
    areas_by_2024 = sorted(
        area_year_totals.keys(),
        key=lambda a: area_year_totals[a][2024],
        reverse=True,
    )
    top10_areas = set(areas_by_2024[:10])
    all_areas   = areas_by_2024

    # Per-program-filter: compute separate dicts
    def get_area_totals_for_program(prog_filter):
        filtered = all_rows if prog_filter == "All Programs" else [r for r in all_rows if r["program"] == prog_filter]
        ayt = collections.defaultdict(lambda: collections.defaultdict(float))
        ayc = collections.defaultdict(lambda: collections.defaultdict(int))
        for r in filtered:
            ayt[r["area"]][r["fiscal_year"]] += r["amount"]
            ayc[r["area"]][r["fiscal_year"]] += 1
        return ayt, ayc

    fig = go.Figure()

    # Color coding for areas
    def area_color(area):
        if area in FEDERAL_PRIORITY_AREAS and area in BC_PRIORITY_AREAS:
            return "#6a0dad"   # purple = both
        elif area in FEDERAL_PRIORITY_AREAS:
            return "#1f6aa5"   # blue = federal priority
        elif area in BC_PRIORITY_AREAS:
            return "#2a9d5c"   # green = BC priority
        else:
            return "#adb5bd"   # grey = no priority

    # We build one set of traces per (program_filter, show_mode) combo.
    # show_mode: "top10" vs "all" — encode as two sets of traces, toggle via buttons.
    # Total traces = len(prog_list) * 2 (top10 + all) * len(all_areas) — too many.
    # Simpler: build one line per area per program, with visibility arrays.
    # We'll create traces for "All Programs" only and use program updatemenus that
    # recalculate (via restyle, providing new y data is not easily done in pure Plotly).
    # Instead, create all traces upfront:
    #   - For each program_filter, for each area: one trace
    # Toggle via buttons that set visibility arrays.

    n_areas = len(all_areas)
    n_progs = len(prog_list)
    all_traces = []  # list of (prog_idx, area_idx, is_top10_mode)

    for p_idx, prog_filter in enumerate(prog_list):
        ayt, ayc = get_area_totals_for_program(prog_filter)
        # Compute top10 for this program
        top10_this = set(
            sorted(ayt.keys(), key=lambda a: ayt[a][2024], reverse=True)[:10]
        )

        for a_idx, area in enumerate(all_areas):
            is_top10 = area in top10_this
            color = area_color(area)
            dash  = "solid"
            width = 2.5 if area in top10_this else 1.2

            y_vals   = [ayt[area].get(yr, 0) / 1e6 for yr in YEARS]
            c_vals   = [ayc[area].get(yr, 0)        for yr in YEARS]
            hover_pts = [
                f"<b>{area}</b><br>FY{yr}: ${y:.1f}M ({c} grants)"
                for yr, y, c in zip(YEARS, y_vals, c_vals)
            ]

            # Determine initial visibility: show only "All Programs" + top10
            visible = (p_idx == 0 and is_top10)

            fig.add_trace(go.Scatter(
                x=YEARS,
                y=y_vals,
                mode="lines+markers",
                name=area,
                line=dict(color=color, width=width, dash=dash),
                marker=dict(size=5),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_pts,
                visible=visible,
                showlegend=True,
                legendgroup=area,
            ))
            all_traces.append((p_idx, a_idx, is_top10))

    total_traces = len(all_traces)

    def make_visibility(target_prog_idx, show_all):
        vis = []
        for p_idx, a_idx, is_top10 in all_traces:
            area = all_areas[a_idx]
            # Recompute top10 for this program
            ayt, _ = get_area_totals_for_program(prog_list[target_prog_idx])
            top10_this = set(
                sorted(ayt.keys(), key=lambda a: ayt[a][2024], reverse=True)[:10]
            )
            if p_idx == target_prog_idx:
                if show_all:
                    vis.append("legendonly" if area not in top10_this else True)
                else:
                    vis.append(True if area in top10_this else False)
            else:
                vis.append(False)
        return vis

    # Pre-compute visibility arrays (expensive but necessary)
    vis_cache = {}
    for p_idx in range(n_progs):
        vis_cache[(p_idx, False)] = make_visibility(p_idx, False)
        vis_cache[(p_idx, True)]  = make_visibility(p_idx, True)

    # Program buttons
    prog_buttons = []
    for p_idx, prog in enumerate(prog_list):
        prog_buttons.append(dict(
            label=prog,
            method="update",
            args=[
                {"visible": vis_cache[(p_idx, False)]},
                {"title.text": f"5-Year Funding Trajectories: {prog} (Top 10 Areas)<br><sup>Blue=federal priority | Green=BC priority | Purple=both | Grey=neither</sup>"},
            ],
        ))

    # Show all / Show top 10 buttons — default to "All Programs" + top10
    toggle_buttons = [
        dict(
            label="Show Top 10",
            method="update",
            args=[
                {"visible": vis_cache[(0, False)]},
                {"title.text": "5-Year Funding Trajectories: All Programs (Top 10 Areas)<br><sup>Blue=federal priority | Green=BC priority | Purple=both | Grey=neither</sup>"},
            ],
        ),
        dict(
            label="Show All Areas",
            method="update",
            args=[
                {"visible": vis_cache[(0, True)]},
                {"title.text": "5-Year Funding Trajectories: All Programs (All Areas)<br><sup>Blue=federal priority | Green=BC priority | Purple=both | Grey=neither</sup>"},
            ],
        ),
    ]

    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons", direction="right", active=0,
                x=0.01, y=1.13, xanchor="left",
                buttons=prog_buttons,
                bgcolor="#f8f9fa", bordercolor="#dee2e6", font=dict(size=10),
            ),
            dict(
                type="buttons", direction="right", active=0,
                x=0.01, y=1.06, xanchor="left",
                buttons=toggle_buttons,
                bgcolor="#e8f4fd", bordercolor="#1f6aa5", font=dict(size=11),
            ),
        ],
        title=dict(
            text="5-Year Funding Trajectories: All Programs (Top 10 Areas)<br><sup>Blue=federal priority | Green=BC priority | Purple=both | Grey=neither</sup>",
            font=dict(size=14), x=0.01,
        ),
        xaxis=dict(
            title="Fiscal Year", tickvals=YEARS, ticktext=[str(y) for y in YEARS],
            gridcolor="#eee",
        ),
        yaxis=dict(title="Total Funding ($M)", gridcolor="#eee"),
        plot_bgcolor="white",
        height=720,
        margin=dict(t=160, l=80, r=200, b=60),
        legend=dict(
            x=1.01, y=1.0,
            font=dict(size=9),
            tracegroupgap=2,
        ),
    )

    return fig, n_areas


# ── HTML Assembly ──────────────────────────────────────────────────────────────

CLICK_PIN_JS = """
<div id="sshrc-panel" style="position:fixed;top:80px;right:24px;width:420px;max-height:82vh;
overflow-y:auto;background:#fff;border:1px solid #d0d0d0;border-radius:10px;
padding:18px 20px;box-shadow:0 6px 28px rgba(0,0,0,0.18);font-size:13px;
line-height:1.65;display:none;z-index:9999;font-family:system-ui,sans-serif;"></div>

<script>
(function() {
    var panel = document.getElementById('sshrc-panel');
    function closePanel() { panel.style.display = 'none'; }
    // Find the first plotly div (Tab 1 bubble chart)
    var allDivs = document.querySelectorAll('.plotly-graph-div');
    if (allDivs.length === 0) return;
    var myPlot = allDivs[0];
    myPlot.on('plotly_click', function(data) {
        if (!data || !data.points || !data.points[0]) return;
        var pt = data.points[0];
        var content = pt.customdata;
        if (!content) return;
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

TAB_CSS = """
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, sans-serif;
         background: #f4f6f9; color: #222; }
  #dashboard-header {
    background: #1f6aa5;
    color: white;
    padding: 18px 32px 12px 32px;
  }
  #dashboard-header h1 { margin: 0 0 4px 0; font-size: 22px; font-weight: 700; }
  #dashboard-header p  { margin: 0; font-size: 13px; opacity: 0.88; }

  .tab-bar {
    display: flex;
    background: #fff;
    border-bottom: 2px solid #dee2e6;
    padding: 0 24px;
    overflow-x: auto;
  }
  .tab-btn {
    padding: 12px 22px;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: #555;
    border-bottom: 3px solid transparent;
    margin-bottom: -2px;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
  }
  .tab-btn:hover { color: #1f6aa5; }
  .tab-btn.active { color: #1f6aa5; border-bottom-color: #1f6aa5; }

  .tab-panel { display: none; padding: 16px 16px 32px 16px; }
  .tab-panel.active { display: block; }

  .chart-container {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    padding: 8px;
    overflow: hidden;
  }
  .tab-desc {
    font-size: 13px;
    color: #555;
    margin: 0 0 12px 4px;
  }
  .legend-note {
    font-size: 12px;
    color: #666;
    margin: 8px 4px 0 4px;
  }
</style>
"""

TAB_JS = """
<script>
function showTab(tabId) {
    document.querySelectorAll('.tab-panel').forEach(function(p) {
        p.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(function(b) {
        b.classList.remove('active');
    });
    document.getElementById(tabId).classList.add('active');
    document.querySelector('[data-tab="' + tabId + '"]').classList.add('active');

    // Trigger Plotly resize to fix blank-chart issue on tab switch
    var divs = document.getElementById(tabId).querySelectorAll('.plotly-graph-div');
    divs.forEach(function(d) {
        if (window.Plotly) { Plotly.Plots.resize(d); }
    });
}
</script>
"""


def assemble_html(tab_panels, plotlyjs_str):
    """
    tab_panels: list of (tab_label, description, html_content)
    Returns full HTML string.
    """
    tab_buttons_html = ""
    tab_divs_html    = ""

    for i, (label, desc, content) in enumerate(tab_panels):
        tab_id  = f"tab{i+1}"
        active  = "active" if i == 0 else ""
        tab_buttons_html += (
            f'<button class="tab-btn {active}" data-tab="{tab_id}" '
            f'onclick="showTab(\'{tab_id}\')">{label}</button>\n'
        )
        tab_divs_html += (
            f'<div id="{tab_id}" class="tab-panel {active}">\n'
            f'  <p class="tab-desc">{desc}</p>\n'
            f'  <div class="chart-container">{content}</div>\n'
            f'</div>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SSHRC Funding Dashboard (FY2020–2024)</title>
  {TAB_CSS}
  <script>{plotlyjs_str}</script>
</head>
<body>

<div id="dashboard-header">
  <h1>SSHRC Funding Dashboard — FY2020–2024</h1>
  <p>Interactive research-strategy tool for researchers evaluating SSHRC funding opportunities.
     Data: SSHRC Open Data (deduped to lead-applicant row per grant per year).</p>
</div>

<div class="tab-bar">
{tab_buttons_html}
</div>

{tab_divs_html}

{TAB_JS}

</body>
</html>"""
    return html


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    all_rows = load_all()

    print("Building Tab 1: Funding Landscape...")
    fig1, n_areas = build_tab1(all_rows)
    html1 = fig1.to_html(full_html=False, include_plotlyjs=False)
    print(f"  -> {n_areas} areas in bubble chart")

    print("Building Tab 2: Strategic Alignment...")
    fig2, n_heatmap_areas = build_tab2(all_rows)
    html2 = fig2.to_html(full_html=False, include_plotlyjs=False)
    print(f"  -> {n_heatmap_areas} areas in heatmap")

    print("Building Tab 3: Provincial Distribution...")
    fig3, n_provinces = build_tab3(all_rows)
    html3 = fig3.to_html(full_html=False, include_plotlyjs=False)
    print(f"  -> {n_provinces} provinces")

    print("Building Tab 4: Institutional Landscape...")
    fig4, n_institutions = build_tab4(all_rows)
    html4 = fig4.to_html(full_html=False, include_plotlyjs=False)
    print(f"  -> {n_institutions} unique institutions (top 25 shown)")

    print("Building Tab 5: 5-Year Trajectories...")
    fig5, n_traj_areas = build_tab5(all_rows)
    html5 = fig5.to_html(full_html=False, include_plotlyjs=False)
    print(f"  -> {n_traj_areas} areas in trajectory chart")

    # Load Plotly.js from package data
    print("Loading Plotly.js...")
    plotlyjs_path = os.path.join(os.path.dirname(plotly.__file__), "package_data", "plotly.min.js")
    with open(plotlyjs_path, "r", encoding="utf-8") as f:
        plotlyjs_str = f.read()

    tab_panels = [
        (
            "1. Funding Landscape",
            "Bubble chart: X = average award size (FY2024), Y = % change vs earliest available year, "
            "bubble size = total FY2024 funding. Filter by program. Click any bubble to pin details.",
            html1,
        ),
        (
            "2. Strategic Alignment",
            "Heatmap showing SSHRC research areas aligned with government priorities. "
            "Cell colour = alignment score × FY2024 funding share. Toggle Federal / BC views.",
            html2,
        ),
        (
            "3. Provincial Distribution",
            "Horizontal bar chart of FY2024 funding by province. "
            "BC highlighted in blue. BC share by program shown in annotation panel.",
            html3,
        ),
        (
            "4. Institutional Landscape",
            "Top 25 institutions by FY2024 SSHRC funding. "
            "BC institutions highlighted in blue. Filter by program.",
            html4,
        ),
        (
            "5. Five-Year Trajectories",
            "Annual funding trajectories by area of research (FY2020–2024). "
            "Blue = federal priority area | Green = BC priority | Purple = both. "
            "Toggle Top 10 / All Areas.",
            html5,
        ),
    ]

    print("Assembling HTML...")
    full_html = assemble_html(tab_panels, plotlyjs_str)

    # Inject click-to-pin JS panel before </body>
    full_html = full_html.replace("</body>", CLICK_PIN_JS + "\n</body>")

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)

    size_mb = os.path.getsize(OUT_HTML) / 1e6
    print(f"\nDone! Written to: {OUT_HTML}")
    print(f"File size: {size_mb:.1f} MB")
    print("\nSummary:")
    print(f"  Tab 1 - Funding Landscape:      {n_areas} research areas")
    print(f"  Tab 2 - Strategic Alignment:    {n_heatmap_areas} areas x "
          f"{len(FEDERAL_PRIORITIES)} federal + {len(BC_PRIORITIES)} BC priorities")
    print(f"  Tab 3 - Provincial Distribution: {n_provinces} provinces")
    print(f"  Tab 4 - Institutional Landscape: {n_institutions} institutions (top 25 shown)")
    print(f"  Tab 5 - 5-Year Trajectories:    {n_traj_areas} areas (top 10 default)")


if __name__ == "__main__":
    main()
