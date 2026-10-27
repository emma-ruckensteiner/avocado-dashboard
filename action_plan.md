# Action Plan: Interactive Avocado Sales Dashboard

## 1. Objective

Build a clean, Notion-like, multi-page interactive dashboard for exploring weekly avocado sales across US regions using Python, pandas, Plotly, and Dash.

The dashboard will help users answer questions such as:

- Which regions are the biggest avocado markets?
- Which avocado type sells more: conventional or organic?
- How have prices evolved over time?
- How do average prices differ by region and avocado type?
- Which regions combine high sales volume with attractive pricing?
- How do selected periods compare with prior periods or custom comparison periods?
- How have sales volumes and prices changed relative to a selected starting point?

No existing analytical logic will be rewritten. The implementation will focus on loading the CSV, preparing fields needed for visualization, and presenting the data interactively.

---

## 2. Data Assumptions

The app expects a CSV named `avocado.csv` in the project root.

Required columns:

| Column | Description |
|---|---|
| `date` | Week start date for sales data |
| `average_price` | Average avocado price for the week |
| `total_volume` | Total avocado volume sold |
| `type` | Avocado type: `conventional` or `organic` |
| `region` | US region or market |

Preprocessing assumptions:

- Parse `date` as a datetime column.
- Ensure `average_price` and `total_volume` are numeric.
- Keep original dataset semantics unchanged.
- Add only visualization-supporting fields such as year, month, quarter, and week labels.
- Exclude `TotalUS` / `Total US` from regional ranking and regional aggregation views by default, because it is a national aggregate rather than an individual market.
- Allow the national aggregate to be included only if the user switches off the exclusion toggle.

---

## 3. UX Direction

The app will use a clean, Notion-like layout:

- Multi-page dashboard with tabs at the top.
- Collapsible side filter panel.
- White or near-white background.
- Card-style content sections.
- Soft grey borders and rounded corners.
- Generous spacing.
- Minimal, mature color palette.
- Clear typographic hierarchy.

Accent colors:

| Avocado Type | Color | Hex |
|---|---:|---|
| Conventional | Deep green | `#1F5D3A` |
| Organic | Deep brown | `#6B4226` |

---

## 4. Dashboard Pages

The app will use four tabs:

1. Executive Summary
2. Markets & Regions
3. Sales Evolution
4. Price Evolution

The previous methodology/about page will be removed.

---

## 5. Global Collapsible Side Filter Panel

The side panel will be available across all tabs and can be expanded or collapsed.

### 5.1 Combined Date Element

All date-related controls will be combined into one panel element called **Period controls**.

It will include:

| Control | Purpose |
|---|---|
| Primary period preset | Choose Last week, Last month, Last 6 months, Last year, Full dataset, or Custom range |
| Primary custom date range | Select exact start and end weeks when Custom range is selected |
| Comparison toggle | Turn comparison mode on or off |
| Comparison period preset | Choose Previous equivalent period, Same period previous year, or Custom comparison range |
| Comparison custom date range | Select exact comparison weeks when custom comparison is selected |

This meets the requirement to support both generic time frames and specific week-based custom time frames.

### 5.2 Combined Region Element

All region-related controls will be combined into one panel element called **Region controls**.

It will include:

| Control | Purpose |
|---|---|
| Region group selector | Select one or more predefined region groups |
| Region selector | Select one, many, or all individual regions |
| Exclude national aggregate toggle | Exclude `TotalUS` / `Total US` by default |
| Top N selector | Default to top 10 regions for regional ranking views |

Region filters will support multiple regions, not just one. If a formal geographic grouping is not present in the data, groups will be defined in code as a configuration dictionary and can be refined later.

### 5.3 Type and Metric Controls

Additional global controls:

| Control | Purpose |
|---|---|
| Avocado type selector | Select conventional, organic, or both |
| Metric selector | Toggle some regional visuals between total volume and average price where useful |

---

## 6. Page 1: Executive Summary

### Purpose

Provide a concise market overview for the selected date range, regions, and avocado types.

### Components

KPI cards:

| KPI Card | Description |
|---|---|
| Total volume sold | Sum of `total_volume` for the selected filters |
| Average price | Average of `average_price` for selected filters |
| Top-selling region | Display as `Top-selling region: XYZ (out of X regions)` |
| Best-selling avocado type | The type with the highest total volume |
| Selected period | Primary period and comparison period if comparison mode is enabled |

Charts:

- Total volume by avocado type.
- Average price by avocado type.
- Optional comparison deltas for volume and average price when comparison mode is enabled.

---

## 7. Page 2: Markets & Regions

### Purpose

Identify the largest markets and compare regional differences in volume, price, and avocado type mix.

### Visualizations

Graphs will be stacked vertically in one page section:

1. **Biggest Markets by Sales Volume**
   - Horizontal bar chart.
   - Default top 10 regions.
   - Excludes `TotalUS` by default.
   - Can be split by avocado type using deep green and deep brown.

2. **Regional Price Comparison**
   - Bar chart showing average price by region and type.

3. **Regional Volume vs Price Opportunity Map**
   - Scatter plot with total volume on one axis and average price on the other.
   - Bubble size can represent total volume.
   - Color by avocado type.
   - Helps identify high-volume regions with attractive pricing.

4. **Regional Type Mix**
   - Stacked bar or grouped bar chart showing conventional vs organic volume share by region.

This incorporates the previously separate regional opportunity proposal into the regions page.

---

## 8. Page 3: Sales Evolution

### Purpose

Show how avocado sales volume evolves over time by region and avocado type.

### Visualizations

1. **Weekly Sales Volume Over Time**
   - Line chart by type and/or selected regions.
   - Hover tooltip includes current value and percentage change vs previous week.

2. **Indexed Sales Volume Change**
   - Indexed line chart where the first visible week equals 100.
   - This makes relative growth or decline easy to compare across regions/types even if absolute volumes differ.

3. **Period Comparison Summary**
   - If comparison mode is enabled, cards or grouped bars show current period vs comparison period total volume and percentage change.

Judgement call: include both tooltip-based week-over-week change and an indexed chart. The indexed chart is especially useful where comparing regions with very different absolute sales volumes.

---

## 9. Page 4: Price Evolution

### Purpose

Show how average avocado prices evolve over time by region and avocado type.

### Visualizations

1. **Weekly Average Price Over Time**
   - Line chart by type and/or selected regions.
   - Hover tooltip includes current price and percentage change vs previous week.

2. **Indexed Price Change**
   - Indexed line chart where the first visible week equals 100.
   - Useful for comparing relative price movements between organic and conventional avocados.

3. **Period Comparison Summary**
   - If comparison mode is enabled, cards or grouped bars show current period vs comparison period average price and percentage change.

---

## 10. Removed Sections / Features

The following will not be implemented:

- Standalone Organic vs Conventional section.
- Standalone Best Opportunities section.
- Data table / downloadable CSV section.
- Methodology / About page.
- Downloadable CSV feature.

Any insights from removed sections will be represented through the Executive Summary, Markets & Regions, Sales Evolution, and Price Evolution pages.

---

## 11. File and Component Structure

Initial implementation will use a compact structure suitable for GitHub and Render deployment:

```text
avocado-dashboard/
├── app.py
├── avocado.csv
├── requirements.txt
├── Procfile
├── README.md
└── action_plan.md
```

Planned files:

| File | Purpose |
|---|---|
| `app.py` | Main Dash application, layout, callbacks, data loading, charts |
| `avocado.csv` | Source dataset placed in the project root |
| `requirements.txt` | Python dependencies for Render |
| `Procfile` | Render start command using Gunicorn |
| `README.md` | Local setup, GitHub push, and Render hosting instructions |
| `action_plan.md` | This implementation plan |

A larger project can later be split into `/components`, `/utils`, and `/assets`, but a single-file Dash app is easier to review and deploy initially.

---

## 12. GitHub and Render Deployment Plan

### GitHub

1. Create a project folder locally.
2. Add `app.py`, `requirements.txt`, `Procfile`, `README.md`, `action_plan.md`, and `avocado.csv`.
3. Initialize Git.
4. Commit the files.
5. Create a new GitHub repository.
6. Push the local project to GitHub.

### Render Free Web Service

1. Log in to Render.
2. Create a new Web Service.
3. Connect the GitHub repository.
4. Select the free instance type.
5. Use the following settings:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:server`
6. Deploy.

---

## 13. Implementation Decision Points

Assumptions made for the first build:

- The dashboard will read `avocado.csv` from the app root.
- Regional groups will be defined in code and can be refined later.
- `TotalUS` is excluded by default from regional aggregations.
- Top regions default to 10.
- Comparison features will support previous equivalent period, same period previous year, and custom comparison range.
- Indexed charts will be included for both sales and prices.

After this plan update, implementation can begin.