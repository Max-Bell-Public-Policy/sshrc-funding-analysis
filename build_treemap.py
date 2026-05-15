import json
import textwrap
import plotly.graph_objects as go

# ── Load LDA results ──────────────────────────────────────────────────────────
with open(r"C:\Users\calvi\policy-deep-dive-workspace\topic_assignments.json", encoding="utf-8") as f:
    ta = json.load(f)

counts = ta["topic_counts"]
topic_titles_map = ta["topic_titles"]   # "0" -> [title, title, ...]
total_assigned = sum(counts)

topic_labels = [
    "Technology, Health & Digital Society",
    "Race, Identity & Cultural Memory",
    "Policy, Justice & Climate",
    "AI, Digital & Children",
    "Care, Education & Early Childhood",
    "Corporate Governance & Global Relations",
    "Wellbeing, Language & Social Systems",
    "Health, Education & Identity",
    "Economic Development & Food Systems",
]

INSIGHT_TOTAL = 86.3
insight_themes = [
    (topic_labels[i], round(counts[i] / total_assigned * INSIGHT_TOTAL, 1), topic_titles_map[str(i)])
    for i in range(9)
]

# Other programs (theme, value, titles list)
other_data = [
    ("Insight Development Grants", "Early-Stage Research",          36.8, []),
    ("Partnership Grants",         "Equity & Access",                9.6, []),
    ("Partnership Grants",         "Climate & Global South",         7.5, []),
    ("Partnership Grants",         "Arts, Culture & Humanities",     7.4, []),
    ("Partnership Grants",         "Indigenous",                     5.0, []),
    ("Partnership Grants",         "AI & Work",                      2.5, []),
    ("Partnership Grants",         "Political Science",              2.5, []),
    ("Partnership Grants",         "Migration & Refugees",           2.5, []),
    ("Partnership Grants",         "Research Infrastructure",        2.5, []),
    ("Partnership Grants",         "Health & Wellbeing",             2.5, []),
    ("Partnership Development Grants", "Health & Wellbeing",         3.0, []),
    ("Partnership Development Grants", "Education & Youth",          2.8, []),
    ("Partnership Development Grants", "Indigenous & Justice",       2.8, []),
    ("Partnership Development Grants", "Climate & Environment",      2.8, []),
    ("Partnership Development Grants", "Community & Justice",        2.6, []),
    ("Connection Grants",          "Knowledge Dissemination",        7.5, []),
    ("Partnership Engage Grants",  "Short-Term Partnerships",        7.4, []),
]

prog_colors = {
    "Insight Grants":                "#1f6aa5",
    "Insight Development Grants":    "#2d8fc4",
    "Partnership Grants":            "#2a9d5c",
    "Partnership Development Grants":"#52b67a",
    "Connection Grants":             "#e07b39",
    "Partnership Engage Grants":     "#f0a860",
}

# ── Build full data rows: (program, theme, value, titles_list) ────────────────
data_full = []
for label, val, t_list in insight_themes:
    data_full.append(("Insight Grants", label, val, t_list))
for prog, theme, val, t_list in other_data:
    data_full.append((prog, theme, val, t_list))

# Program totals
programs = {}
for prog, theme, val, _ in data_full:
    programs[prog] = programs.get(prog, 0) + val

total_shown = sum(v for _, _, v, _ in data_full)

# ── Assemble treemap arrays ───────────────────────────────────────────────────
labels, parents, values, colors, customdata = [], [], [], [], []

# Root
labels.append("SSHRC Project Funding")
parents.append("")
values.append(total_shown)
colors.append("#4a4a4a")
customdata.append("")

# Program nodes
for prog, total in programs.items():
    lbl = prog + "<br><b>$" + f"{total:.1f}M</b>"
    labels.append(lbl)
    parents.append("SSHRC Project Funding")
    values.append(total)
    colors.append(prog_colors.get(prog, "#999"))
    customdata.append("")

# Theme nodes
for prog, theme, val, t_list in data_full:
    prog_lbl = prog + "<br><b>$" + f"{programs[prog]:.1f}M</b>"
    theme_lbl = theme + "<br>$" + f"{val:.1f}M"
    labels.append(theme_lbl)
    parents.append(prog_lbl)
    values.append(val)
    c = prog_colors.get(prog, "#999999")
    r = min(255, int(c[1:3], 16) + 40)
    g = min(255, int(c[3:5], 16) + 40)
    b = min(255, int(c[5:7], 16) + 40)
    colors.append(f"#{r:02x}{g:02x}{b:02x}")
    # Hover: first 10 titles as a preview
    preview = "<br>".join(
        textwrap.shorten(t, width=70, placeholder="…") for t in t_list[:10]
    )
    if len(t_list) > 10:
        preview += f"<br>... and {len(t_list) - 10} more"
    customdata.append(preview)

    # Title nodes (leaf level — only for Insight Grants which have real titles)
    for title in t_list:
        short = textwrap.shorten(title, width=80, placeholder="…")
        labels.append(short)
        parents.append(theme_lbl)
        values.append(round(val / max(len(t_list), 1), 2))
        colors.append(f"#{r:02x}{g:02x}{b:02x}")
        customdata.append(title)   # full title in hover

# ── Figure ────────────────────────────────────────────────────────────────────
fig = go.Figure(go.Treemap(
    labels=labels,
    parents=parents,
    values=values,
    marker=dict(colors=colors, line=dict(width=1, color="#ffffff")),
    textfont=dict(size=14),
    hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
    customdata=customdata,
    branchvalues="total",
    maxdepth=3,
))

note = (
    "SSHRC Project Funding by Program and Research Theme (2024-25)  |  "
    "Total shown: ~$" + f"{total_shown:.0f}M CAD<br>"
    "<sup>Insight Grants themes from LDA topic modeling on 502 grant titles (open data). "
    "Click a theme to see individual project titles. "
    "Other program splits estimated from competition results.</sup>"
)

fig.update_layout(
    title=dict(text=note, font=dict(size=14), x=0.01),
    margin=dict(t=95, l=10, r=10, b=10),
    width=1300,
    height=750,
)

out = r"C:\Users\calvi\policy-deep-dive-workspace\sshrc_treemap.html"
fig.write_html(out, include_plotlyjs=True)
print("Written:", out)
print(f"\nInsight Grants: {total_assigned} titles across 9 topics")
for i, (label, val, t_list) in enumerate(insight_themes):
    print(f"  {label}: ${val}M ({len(t_list)} titles)")
