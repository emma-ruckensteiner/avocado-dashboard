from __future__ import annotations

import os
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, Input, Output, State, dcc, html


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Look for avocado.csv next to app.py, so the app works from any working directory.
LOCAL_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avocado.csv")

TYPE_COLORS = {
    "conventional": "#1F5D3A",
    "organic": "#6B4226",
    "Both / total": "#74C365",
}

COMBINED_TYPE_LABEL = "Both / total"
COMBINED_COLOR = "#74C365"
MUTED_GREEN = "#9FB7A7"
MUTED_BROWN = "#B8A391"
MUTED_COMBINED = "#C6D8BB"
BACKGROUND = "#F7F7F5"
CARD_BORDER = "#E7E5E0"
TEXT = "#222222"
MUTED = "#6B6B6B"

NATIONAL_AGGREGATES = {"TotalUS", "Total US", "Total U.S.", "Total USA"}

# The 8 broad US regions add up exactly to TotalUS, and each one contains the
# metro markets inside it (e.g. West includes LosAngeles, Seattle, ...).
# Mixing them with metro markets double-counts volume, so by default the
# dashboard shows metro markets only.
BROAD_REGIONS = {
    "California", "GreatLakes", "Midsouth", "Northeast",
    "Plains", "SouthCentral", "Southeast", "West",
}
AGGREGATE_REGIONS = NATIONAL_AGGREGATES | BROAD_REGIONS

REGION_GROUPS = {
    "West & Pacific": [
        "Boise", "Denver", "LasVegas", "LosAngeles", "PhoenixTucson",
        "Portland", "Sacramento", "SanDiego", "SanFrancisco", "Seattle",
        "Spokane", "WestTexNewMexico",
    ],
    "South & Southeast": [
        "Atlanta", "BirminghamMontgomery", "Charlotte", "Jacksonville",
        "Louisville", "Miami", "MiamiFtLauderdale", "Nashville", "NewOrleans",
        "Orlando", "RaleighGreensboro", "RichmondNorfolk", "Roanoke",
        "SouthCarolina", "Tampa",
    ],
    "Midwest & Plains": [
        "Chicago", "CincinnatiDayton", "Columbus", "Detroit", "GrandRapids",
        "Indianapolis", "KansasCity", "PeoriaSpringfield", "StLouis",
        "Toledo", "Wichita",
    ],
    "Northeast": [
        "Albany", "BaltimoreWashington", "Boston", "BuffaloRochester",
        "HarrisburgScranton", "HartfordSpringfield", "NewYork",
        "NorthernNewEngland", "Philadelphia", "Pittsburgh", "Providence",
        "Syracuse",
    ],
    "Texas & South Central": [
        "DallasFtWorth", "Houston", "WestTexNewMexico",
    ],
}

NO_COMPARISON_TEXT = "No data for comparison period"


# -----------------------------------------------------------------------------
# Data loading and utilities
# -----------------------------------------------------------------------------

def find_data_path() -> str:
    """Return a usable avocado CSV path.

    Uses avocado.csv next to app.py, or the AVOCADO_CSV_PATH environment variable.
    """
    env_path = os.environ.get("AVOCADO_CSV_PATH")
    for candidate in [env_path, LOCAL_DATA_PATH]:
        if candidate and os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "Could not find avocado.csv. Put avocado.csv in the project root, "
        "or set AVOCADO_CSV_PATH."
    )


def load_data() -> pd.DataFrame:
    """Load and minimally prepare the avocado dataset for visualization."""
    df = pd.read_csv(find_data_path())

    required = ["date", "average_price", "total_volume", "type", "region"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df[required].copy()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["average_price"] = pd.to_numeric(df["average_price"], errors="coerce")
    df["total_volume"] = pd.to_numeric(df["total_volume"], errors="coerce")
    df["type"] = df["type"].astype(str).str.lower().str.strip()
    df["region"] = df["region"].astype(str).str.strip()
    df = df.dropna(subset=["date", "average_price", "total_volume", "type", "region"])

    # Visualization-only fields.
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["week_label"] = df["date"].dt.strftime("%Y-%m-%d")
    return df.sort_values("date")


DATA = load_data()
MIN_DATE = DATA["date"].min()
MAX_DATE = DATA["date"].max()
ALL_TYPES = sorted(DATA["type"].unique())
ALL_REGIONS = sorted(DATA["region"].unique())


def is_national_region(region: str) -> bool:
    return region in NATIONAL_AGGREGATES


def available_regions(region_level: str | None) -> list[str]:
    """Regions shown for a region level. Levels never overlap, so totals are not double-counted."""
    if region_level == "broad":
        return [r for r in ALL_REGIONS if r in BROAD_REGIONS]
    return [r for r in ALL_REGIONS if r not in AGGREGATE_REGIONS]


def group_regions(selected_groups: list[str] | None, region_level: str | None) -> set[str]:
    selected_groups = selected_groups or []
    regions = set()
    allowed = set(available_regions(region_level))
    for group in selected_groups:
        for region in REGION_GROUPS.get(group, []):
            if region in allowed:
                regions.add(region)
    return regions


def resolve_regions(
    selected_groups: list[str] | None,
    selected_regions: list[str] | None,
    region_level: str | None,
) -> list[str]:
    allowed = set(available_regions(region_level))
    regions = set(selected_regions or []) & allowed
    regions |= group_regions(selected_groups, region_level)
    if not regions:
        regions = allowed
    return sorted(regions)


def parse_date(value):
    if not value:
        return None
    return pd.to_datetime(value).normalize()


def period_bounds(preset: str, custom_start, custom_end) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return start/end dates for the selected primary period."""
    preset = preset or "full"
    custom_start = parse_date(custom_start)
    custom_end = parse_date(custom_end)

    if preset == "custom" and custom_start is not None and custom_end is not None:
        start, end = custom_start, custom_end
    elif preset == "last_week":
        start = MAX_DATE
        end = MAX_DATE
    elif preset == "last_month":
        start = MAX_DATE - pd.DateOffset(months=1)
        end = MAX_DATE
    elif preset == "last_6m":
        start = MAX_DATE - pd.DateOffset(months=6)
        end = MAX_DATE
    elif preset == "last_year":
        start = MAX_DATE - pd.DateOffset(years=1)
        end = MAX_DATE
    else:
        start = MIN_DATE
        end = MAX_DATE

    return max(pd.Timestamp(start), MIN_DATE), min(pd.Timestamp(end), MAX_DATE)


def comparison_bounds(
    primary_start: pd.Timestamp,
    primary_end: pd.Timestamp,
    comparison_preset: str,
    comparison_start,
    comparison_end,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return comparison-period start/end dates."""
    comparison_preset = comparison_preset or "previous"
    comparison_start = parse_date(comparison_start)
    comparison_end = parse_date(comparison_end)

    if (
        comparison_preset == "custom"
        and comparison_start is not None
        and comparison_end is not None
    ):
        start, end = comparison_start, comparison_end
    elif comparison_preset == "previous_year":
        start = primary_start - pd.DateOffset(years=1)
        end = primary_end - pd.DateOffset(years=1)
    else:
        delta = primary_end - primary_start
        end = primary_start - timedelta(days=7)
        start = end - delta

    return max(pd.Timestamp(start), MIN_DATE), min(pd.Timestamp(end), MAX_DATE)


def apply_filters(
    start_date,
    end_date,
    selected_types,
    selected_regions,
    selected_groups,
    region_level_us,
) -> pd.DataFrame:
    regions = resolve_regions(selected_groups, selected_regions, region_level_us)
    selected_types = selected_types or ALL_TYPES

    mask = (
        (DATA["date"] >= start_date)
        & (DATA["date"] <= end_date)
        & (DATA["type"].isin(selected_types))
        & (DATA["region"].isin(regions))
    )
    return DATA.loc[mask].copy()


def format_number(value) -> str:
    if pd.isna(value):
        return "—"
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.1f}K"
    return f"{value:,.0f}"


def format_price(value) -> str:
    return "—" if pd.isna(value) else f"${value:,.2f}"


def pct_change(current, previous) -> str:
    if previous in [0, None] or pd.isna(previous):
        return "—"
    return f"{(current - previous) / previous:+.1%}"


def clean_label(value: str) -> str:
    labels = {
        "last_week": "Last week",
        "last_month": "Last month",
        "last_6m": "Last 6 months",
        "last_year": "Last year",
        "full": "Full dataset",
        "custom": "Custom range",
        "previous": "Previous equivalent period",
        "previous_year": "Same period previous year",
    }
    return labels.get(value, str(value).replace("_", " ").title())


def date_label(start, end) -> str:
    if pd.isna(start) or pd.isna(end):
        return "—"
    return f"{pd.Timestamp(start):%d %b %Y} – {pd.Timestamp(end):%d %b %Y}"


def empty_figure(message="No data for the selected filters"):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16, "color": MUTED},
    )
    fig.update_layout(
        template="plotly_white",
        height=360,
        margin={"l": 30, "r": 30, "t": 40, "b": 30},
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


def add_no_comparison_note(fig: go.Figure) -> go.Figure:
    """Explain why only the current period is shown when comparison mode is on."""
    fig.add_annotation(
        text=f"No comparison data: dataset starts {MIN_DATE:%d %b %Y}",
        xref="paper", yref="paper", x=0, y=-0.16, xanchor="left", showarrow=False,
        font={"size": 12, "color": MUTED},
    )
    fig.update_layout(margin={"b": 80})
    return fig


def base_layout(fig: go.Figure, height=420):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin={"l": 40, "r": 24, "t": 56, "b": 48},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Inter, Arial, sans-serif", "color": TEXT},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor=CARD_BORDER)
    fig.update_yaxes(gridcolor="#EFEDE8", linecolor=CARD_BORDER)
    polish_labels(fig)
    trim_precision(fig)
    return fig


def trim_precision(fig: go.Figure) -> go.Figure:
    """Round plotted numbers so charts send far less data to the browser (no visible change)."""
    import numpy as np
    for trace in fig.data:
        for attr in ("x", "y"):
            values = getattr(trace, attr, None)
            if values is None:
                continue
            arr = np.asarray(values)
            if arr.dtype.kind != "f":
                continue
            finite = arr[np.isfinite(arr)]
            if finite.size == 0:
                continue
            decimals = 0 if np.nanmedian(np.abs(finite)) >= 1000 else 3
            setattr(trace, attr, np.round(arr, decimals))
    return fig


TYPE_NAMES = {"conventional": "Conventional", "organic": "Organic"}


def polish_labels(fig: go.Figure) -> go.Figure:
    """Readable legend entries, no raw column-name legend titles, and $ on price axes."""
    fig.update_layout(legend_title_text="")
    fig.for_each_trace(lambda t: t.update(name=TYPE_NAMES.get(t.name, t.name)))
    for trace in fig.data:
        if trace.type == "bar" and trace.x is not None and all(isinstance(v, str) for v in trace.x):
            trace.x = [TYPE_NAMES.get(v, v) for v in trace.x]
    for axis_name in [k for k in fig.layout.to_plotly_json() if k.startswith(("xaxis", "yaxis"))]:
        axis = fig.layout[axis_name]
        title = (axis.title.text or "") if axis.title else ""
        if "price" in title.lower():
            axis.update(tickprefix="$", tickformat=".2f")
    return fig


def add_wow_change(df: pd.DataFrame, value_col: str, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.sort_values(group_cols + ["date"]).copy()
    previous = out.groupby(group_cols)[value_col].shift(1)
    out["wow_change"] = (out[value_col] - previous) / previous
    out["wow_text"] = out["wow_change"].apply(lambda x: "—" if pd.isna(x) else f"{x:+.1%}")
    return out


def build_indexed(df: pd.DataFrame, value_col: str, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.sort_values(group_cols + ["date"]).copy()
    first_values = out.groupby(group_cols)[value_col].transform("first")
    out["indexed_value"] = out[value_col] / first_values * 100
    out.loc[first_values == 0, "indexed_value"] = None
    return out


def weighted_average_price(df: pd.DataFrame) -> float:
    if df.empty or df["total_volume"].sum() == 0:
        return float("nan")
    return (df["average_price"] * df["total_volume"]).sum() / df["total_volume"].sum()


def selected_types_from_mode(type_mode: str | None) -> list[str]:
    """Map the display-oriented type selector to actual dataset type values."""
    type_mode = type_mode or "split"
    if type_mode in {"conventional", "organic"}:
        return [type_mode]
    return ALL_TYPES


def mode_label(type_mode: str | None) -> str:
    labels = {
        "conventional": "Conventional",
        "organic": "Organic",
        "both_total": COMBINED_TYPE_LABEL,
        "split": "Split by type",
    }
    return labels.get(type_mode or "split", "Split by type")


def type_order_for_mode(type_mode: str | None) -> list[str]:
    type_mode = type_mode or "split"
    if type_mode == "organic":
        return ["organic"]
    if type_mode == "conventional":
        return ["conventional"]
    if type_mode == "both_total":
        return [COMBINED_TYPE_LABEL]
    return [t for t in ["conventional", "organic"] if t in ALL_TYPES]


def pct_delta_value(current, comparison) -> float:
    if pd.isna(current) or pd.isna(comparison) or comparison == 0:
        return float("nan")
    return (current - comparison) / comparison


def pct_delta_text(current, comparison) -> str:
    delta = pct_delta_value(current, comparison)
    return "—" if pd.isna(delta) else f"{delta:+.1%}"


def metric_summary(df: pd.DataFrame, metric: str) -> float:
    if df.empty:
        return float("nan")
    if metric == "total_volume":
        return df["total_volume"].sum()
    return df["average_price"].mean()


def aggregate_by_type_for_mode(df: pd.DataFrame, metric: str, type_mode: str | None) -> pd.DataFrame:
    """Aggregate by type display mode for summary/time-series charts."""
    if df.empty:
        return pd.DataFrame(columns=["type_display", metric])

    type_mode = type_mode or "split"
    if metric == "total_volume":
        if type_mode == "both_total":
            return pd.DataFrame({"type_display": [COMBINED_TYPE_LABEL], metric: [df["total_volume"].sum()]})
        grouped = df.groupby("type", as_index=False)["total_volume"].sum()
        return grouped.rename(columns={"type": "type_display"})

    if type_mode == "both_total":
        return pd.DataFrame({"type_display": [COMBINED_TYPE_LABEL], metric: [df["average_price"].mean()]})
    grouped = df.groupby("type", as_index=False)["average_price"].mean()
    return grouped.rename(columns={"type": "type_display"})


def aggregate_timeseries_for_mode(df: pd.DataFrame, metric: str, type_mode: str | None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "type_display", metric])

    type_mode = type_mode or "split"
    if metric == "total_volume":
        if type_mode == "both_total":
            grouped = df.groupby("date", as_index=False)["total_volume"].sum()
            grouped["type_display"] = COMBINED_TYPE_LABEL
            return grouped[["date", "type_display", "total_volume"]]
        return (
            df.groupby(["date", "type"], as_index=False)["total_volume"]
            .sum()
            .rename(columns={"type": "type_display"})
        )

    if type_mode == "both_total":
        grouped = df.groupby("date", as_index=False)["average_price"].mean()
        grouped["type_display"] = COMBINED_TYPE_LABEL
        return grouped[["date", "type_display", "average_price"]]
    return (
        df.groupby(["date", "type"], as_index=False)["average_price"]
        .mean()
        .rename(columns={"type": "type_display"})
    )


def comparison_lookup_by_group(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    group_cols: list[str],
    metric: str,
) -> dict:
    """Return comparison text by group for hover labels."""
    if current_df.empty or comparison_df.empty:
        return {}

    if metric == "total_volume":
        cur = current_df.groupby(group_cols, as_index=False)["total_volume"].sum()
        comp = comparison_df.groupby(group_cols, as_index=False)["total_volume"].sum()
        value_col = "total_volume"
    else:
        cur = current_df.groupby(group_cols, as_index=False)["average_price"].mean()
        comp = comparison_df.groupby(group_cols, as_index=False)["average_price"].mean()
        value_col = "average_price"

    merged = cur.merge(comp, on=group_cols, how="left", suffixes=("_current", "_comparison"))
    out = {}
    for _, row in merged.iterrows():
        key = tuple(row[col] for col in group_cols)
        if len(key) == 1:
            key = key[0]
        current = row[f"{value_col}_current"]
        comparison = row[f"{value_col}_comparison"]
        out[key] = pct_delta_text(current, comparison)
    return out


def add_comparison_hover(
    grouped: pd.DataFrame,
    lookup: dict,
    group_cols: list[str],
    comparison_enabled: bool,
) -> pd.DataFrame:
    grouped = grouped.copy()
    if not comparison_enabled:
        grouped["comparison_text"] = "Comparison: off"
        return grouped
    if not lookup:
        grouped["comparison_text"] = f"Comparison: {NO_COMPARISON_TEXT.lower()}"
        return grouped

    if len(group_cols) == 1:
        grouped["comparison_text"] = grouped[group_cols[0]].map(lambda key: f"Period change vs comparison: {lookup.get(key, '—')}")
    else:
        grouped["comparison_text"] = grouped[group_cols].apply(
            lambda row: f"Period change vs comparison: {lookup.get(tuple(row), '—')}",
            axis=1,
        )
    return grouped


# -----------------------------------------------------------------------------
# Figure builders
# -----------------------------------------------------------------------------

def fig_summary_volume(current_df: pd.DataFrame, comparison_df: pd.DataFrame, comparison_enabled: bool, type_mode: str | None):
    if current_df.empty:
        return empty_figure()

    type_mode = type_mode or "split"
    rows = []
    for period, period_df in [("Current", current_df), ("Comparison", comparison_df)]:
        if period == "Comparison" and not comparison_enabled:
            continue
        if period_df.empty:
            continue
        grouped = aggregate_by_type_for_mode(period_df, "total_volume", type_mode)
        for _, row in grouped.iterrows():
            rows.append({"Period": period, "Type": row["type_display"], "Total volume": row["total_volume"]})

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return empty_figure("Not enough data for the selected comparison")

    category_orders = {
        "Period": ["Current", "Comparison"],
        "Type": type_order_for_mode(type_mode),
    }

    fig = px.bar(
        plot_df,
        x="Period",
        y="Total volume",
        color="Type",
        barmode="stack" if type_mode == "split" else "group",
        color_discrete_map=TYPE_COLORS,
        category_orders=category_orders,
        title="Total Volume by Period",
    )
    fig.update_traces(
        hovertemplate="Period: %{x}<br>Type: %{fullData.name}<br>Total volume: %{y:,.0f}<extra></extra>"
    )
    fig.update_yaxes(title="Total volume")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=430)


def fig_summary_price(current_df: pd.DataFrame, comparison_df: pd.DataFrame, comparison_enabled: bool, type_mode: str | None):
    if current_df.empty:
        return empty_figure()

    type_mode = type_mode or "split"
    type_order = type_order_for_mode(type_mode)

    current = aggregate_by_type_for_mode(current_df, "average_price", type_mode).set_index("type_display")
    comparison = aggregate_by_type_for_mode(comparison_df, "average_price", type_mode).set_index("type_display") if comparison_enabled and not comparison_df.empty else pd.DataFrame()

    current_y = [current.loc[t, "average_price"] if t in current.index else None for t in type_order]
    comp_y = [comparison.loc[t, "average_price"] if t in comparison.index else None for t in type_order] if comparison_enabled and not comparison.empty else []

    fig = go.Figure()
    current_colors = [TYPE_COLORS.get(t, TYPE_COLORS.get(t.lower(), COMBINED_COLOR)) for t in type_order]
    fig.add_trace(
        go.Bar(
            x=type_order,
            y=current_y,
            name="Current",
            marker_color=current_colors,
            text=[format_price(v) if v is not None else "—" for v in current_y],
            textposition="outside",
            offsetgroup="current",
            hovertemplate="Type: %{x}<br>Current average price: $%{y:.2f}<extra></extra>",
        )
    )

    if comparison_enabled and comp_y:
        muted_map = {
            "conventional": MUTED_GREEN,
            "organic": MUTED_BROWN,
            COMBINED_TYPE_LABEL: MUTED_COMBINED,
        }
        fig.add_trace(
            go.Bar(
                x=type_order,
                y=comp_y,
                name="Comparison",
                marker_color=[muted_map.get(t, "#B7AEA5") for t in type_order],
                text=[format_price(v) if v is not None else "—" for v in comp_y],
                textposition="outside",
                offsetgroup="comparison",
                hovertemplate="Type: %{x}<br>Comparison average price: $%{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(title="Average Price by Type and Period", barmode="group")
    fig.update_yaxes(title="Average price")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=430)


def fig_top_markets(
    df: pd.DataFrame,
    top_n: int,
    comparison_df: pd.DataFrame | None = None,
    comparison_enabled: bool = False,
    type_mode: str | None = "split",
):
    if df.empty:
        return empty_figure()

    type_mode = type_mode or "split"
    if type_mode == "both_total":
        grouped = df.groupby("region", as_index=False)["total_volume"].sum()
        grouped["type_display"] = COMBINED_TYPE_LABEL
        comparison_grouped = (
            comparison_df.groupby("region", as_index=False)["total_volume"].sum()
            if comparison_enabled and comparison_df is not None and not comparison_df.empty
            else pd.DataFrame(columns=["region", "total_volume"])
        )
        merge_cols = ["region"]
    else:
        grouped = (
            df.groupby(["region", "type"], as_index=False)["total_volume"]
            .sum()
            .rename(columns={"type": "type_display"})
        )
        comparison_grouped = (
            comparison_df.groupby(["region", "type"], as_index=False)["total_volume"]
            .sum()
            .rename(columns={"type": "type_display"})
            if comparison_enabled and comparison_df is not None and not comparison_df.empty
            else pd.DataFrame(columns=["region", "type_display", "total_volume"])
        )
        merge_cols = ["region", "type_display"]

    totals = grouped.groupby("region", as_index=False)["total_volume"].sum().nlargest(top_n, "total_volume")
    grouped = grouped[grouped["region"].isin(totals["region"])]
    order = totals.sort_values("total_volume", ascending=True)["region"].tolist()

    if comparison_enabled and not comparison_grouped.empty:
        grouped = grouped.merge(comparison_grouped, on=merge_cols, how="left", suffixes=("", "_comparison"))
        grouped["comparison_text"] = grouped.apply(
            lambda row: pct_delta_text(row["total_volume"], row.get("total_volume_comparison")),
            axis=1,
        )
    else:
        grouped["comparison_text"] = NO_COMPARISON_TEXT.lower() if comparison_enabled else "off"

    fig = px.bar(
        grouped,
        y="region",
        x="total_volume",
        color="type_display",
        color_discrete_map=TYPE_COLORS,
        orientation="h",
        category_orders={"region": order},
        title=f"Biggest Markets by Sales Volume — Top {top_n}",
        custom_data=["comparison_text"],
    )
    fig.update_traces(
        hovertemplate=(
            "Region: %{y}<br>Type: %{fullData.name}<br>Volume: %{x:,.0f}"
            "<br>Period change vs comparison: %{customdata[0]}<extra></extra>"
        )
    )
    fig.update_xaxes(title="Total volume")
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=order)
    return base_layout(fig, height=max(420, 34 * len(order) + 160))


def fig_region_price_dumbbell(df: pd.DataFrame, top_n: int, comparison_df: pd.DataFrame | None = None, comparison_enabled: bool = False):
    if df.empty:
        return empty_figure()
    if not {"conventional", "organic"}.issubset(set(df["type"].unique())):
        return empty_figure("Select Split by type or Both / total to view organic price markup")

    top_regions = df.groupby("region", as_index=False)["total_volume"].sum().nlargest(top_n, "total_volume")["region"]
    grouped = (
        df[df["region"].isin(top_regions)]
        .groupby(["region", "type"], as_index=False)["average_price"]
        .mean()
    )
    pivot = grouped.pivot(index="region", columns="type", values="average_price").reset_index()
    if not {"conventional", "organic"}.issubset(pivot.columns):
        return empty_figure("Not enough data to compare conventional and organic prices")
    pivot = pivot.dropna(subset=["conventional", "organic"])
    if pivot.empty:
        return empty_figure("Not enough data to compare conventional and organic prices")

    pivot["premium"] = pivot["organic"] - pivot["conventional"]
    pivot["premium_pct"] = pivot["premium"] / pivot["conventional"]
    order = pivot.sort_values("premium", ascending=True)["region"].tolist()
    pivot = pivot.set_index("region").loc[order].reset_index()

    comp_lookup = {}
    if comparison_enabled and comparison_df is not None and not comparison_df.empty:
        comp_grouped = (
            comparison_df[comparison_df["region"].isin(top_regions)]
            .groupby(["region", "type"], as_index=False)["average_price"]
            .mean()
        )
        comp_pivot = comp_grouped.pivot(index="region", columns="type", values="average_price").reset_index()
        if {"conventional", "organic"}.issubset(comp_pivot.columns):
            comp_pivot["premium"] = comp_pivot["organic"] - comp_pivot["conventional"]
            for _, row in comp_pivot.iterrows():
                comp_lookup[row["region"]] = row["premium"]

    line_x = []
    line_y = []
    for _, row in pivot.iterrows():
        line_x.extend([row["conventional"], row["organic"], None])
        line_y.extend([row["region"], row["region"], None])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=line_x,
            y=line_y,
            mode="lines",
            line={"color": "#D8D3CC", "width": 3},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    custom = []
    for _, row in pivot.iterrows():
        comp_text = "Comparison: off"
        if comparison_enabled:
            comp_premium = comp_lookup.get(row["region"])
            comp_text = (
                f"Premium change vs comparison: {pct_delta_text(row['premium'], comp_premium)}"
                if comp_lookup else f"Comparison: {NO_COMPARISON_TEXT.lower()}"
            )
        custom.append([row["premium"], row["premium_pct"], comp_text])

    fig.add_trace(
        go.Scatter(
            x=pivot["conventional"],
            y=pivot["region"],
            mode="markers",
            name="Conventional",
            marker={"color": TYPE_COLORS["conventional"], "size": 12},
            customdata=custom,
            hovertemplate=(
                "Region: %{y}<br>Conventional price: $%{x:.2f}"
                "<br>Organic premium: $%{customdata[0]:.2f} (%{customdata[1]:.1%})"
                "<br>%{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=pivot["organic"],
            y=pivot["region"],
            mode="markers",
            name="Organic",
            marker={"color": TYPE_COLORS["organic"], "size": 12},
            customdata=custom,
            hovertemplate=(
                "Region: %{y}<br>Organic price: $%{x:.2f}"
                "<br>Organic premium: $%{customdata[0]:.2f} (%{customdata[1]:.1%})"
                "<br>%{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(title="Organic Price Markup by Region")
    fig.update_xaxes(title="Average price")
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=order)
    return base_layout(fig, height=max(420, 34 * len(order) + 160))


def fig_opportunity_map(
    df: pd.DataFrame,
    top_n: int,
    comparison_df: pd.DataFrame | None = None,
    comparison_enabled: bool = False,
    type_mode: str | None = "split",
):
    if df.empty:
        return empty_figure()

    type_mode = type_mode or "split"
    region_totals = df.groupby("region", as_index=False)["total_volume"].sum().nlargest(top_n, "total_volume")
    filtered = df[df["region"].isin(region_totals["region"])]

    if type_mode == "both_total":
        grouped = (
            filtered.groupby("region", as_index=False)
            .agg(total_volume=("total_volume", "sum"), average_price=("average_price", "mean"))
        )
        grouped["type_display"] = COMBINED_TYPE_LABEL
        comp_lookup = comparison_lookup_by_group(
            filtered,
            comparison_df[comparison_df["region"].isin(region_totals["region"])] if comparison_df is not None and not comparison_df.empty else pd.DataFrame(),
            ["region"],
            "total_volume",
        )
        grouped = add_comparison_hover(grouped, comp_lookup, ["region"], comparison_enabled)
    else:
        grouped = (
            filtered.groupby(["region", "type"], as_index=False)
            .agg(total_volume=("total_volume", "sum"), average_price=("average_price", "mean"))
            .rename(columns={"type": "type_display"})
        )
        comp_lookup = {}
        if comparison_df is not None and not comparison_df.empty:
            comp_filtered = comparison_df[comparison_df["region"].isin(region_totals["region"])]
            current_for_lookup = filtered.rename(columns={"type": "type_display"})
            comp_for_lookup = comp_filtered.rename(columns={"type": "type_display"})
            comp_lookup = comparison_lookup_by_group(current_for_lookup, comp_for_lookup, ["region", "type_display"], "total_volume")
        grouped = add_comparison_hover(grouped, comp_lookup, ["region", "type_display"], comparison_enabled)

    fig = px.scatter(
        grouped,
        x="average_price",
        y="total_volume",
        size="total_volume",
        color="type_display",
        color_discrete_map=TYPE_COLORS,
        custom_data=["comparison_text"],
        hover_name="region",
        title="Regional Volume vs Price Opportunity Map",
        size_max=46,
    )
    fig.update_traces(
        hovertemplate=(
            "Region: %{hovertext}<br>Average price: $%{x:.2f}<br>Total volume: %{y:,.0f}"
            "<br>%{customdata[0]}<extra></extra>"
        )
    )
    fig.update_xaxes(title="Average price")
    fig.update_yaxes(title="Total volume")
    return base_layout(fig, height=460)


def fig_type_mix(df: pd.DataFrame, top_n: int, comparison_df: pd.DataFrame | None = None, comparison_enabled: bool = False):
    if df.empty:
        return empty_figure()
    top_regions = df.groupby("region", as_index=False)["total_volume"].sum().nlargest(top_n, "total_volume")["region"]
    grouped = (
        df[df["region"].isin(top_regions)]
        .groupby(["region", "type"], as_index=False)["total_volume"]
        .sum()
    )
    totals = grouped.groupby("region")["total_volume"].transform("sum")
    grouped["share"] = grouped["total_volume"] / totals
    order = (
        grouped.groupby("region", as_index=False)["total_volume"]
        .sum()
        .sort_values("total_volume", ascending=True)["region"]
        .tolist()
    )

    comp_lookup = {}
    if comparison_enabled and comparison_df is not None and not comparison_df.empty:
        comp_lookup = comparison_lookup_by_group(
            df[df["region"].isin(top_regions)],
            comparison_df[comparison_df["region"].isin(top_regions)],
            ["region", "type"],
            "total_volume",
        )
    grouped = add_comparison_hover(grouped, comp_lookup, ["region", "type"], comparison_enabled)

    fig = px.bar(
        grouped,
        y="region",
        x="share",
        color="type",
        color_discrete_map=TYPE_COLORS,
        orientation="h",
        category_orders={"region": order},
        custom_data=["comparison_text"],
        title="Regional Type Mix",
    )
    fig.update_traces(
        hovertemplate="Region: %{y}<br>Type: %{fullData.name}<br>Share: %{x:.1%}<br>%{customdata[0]}<extra></extra>"
    )
    fig.update_xaxes(title="Volume share", tickformat=".0%")
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=order)
    return base_layout(fig, height=max(420, 34 * len(order) + 160))


def fig_sales_over_time(
    df: pd.DataFrame,
    comparison_df: pd.DataFrame | None = None,
    comparison_enabled: bool = False,
    type_mode: str | None = "split",
):
    if df.empty:
        return empty_figure()
    grouped = aggregate_timeseries_for_mode(df, "total_volume", type_mode).sort_values(["type_display", "date"])
    grouped = add_wow_change(grouped, "total_volume", ["type_display"])

    comp_lookup = {}
    if comparison_enabled and comparison_df is not None and not comparison_df.empty:
        if type_mode == "both_total":
            cur_lookup_df = df.copy()
            cur_lookup_df["type_display"] = COMBINED_TYPE_LABEL
            comp_lookup_df = comparison_df.copy()
            comp_lookup_df["type_display"] = COMBINED_TYPE_LABEL
        else:
            cur_lookup_df = df.rename(columns={"type": "type_display"})
            comp_lookup_df = comparison_df.rename(columns={"type": "type_display"})
        comp_lookup = comparison_lookup_by_group(cur_lookup_df, comp_lookup_df, ["type_display"], "total_volume")
    grouped = add_comparison_hover(grouped, comp_lookup, ["type_display"], comparison_enabled)

    fig = px.line(
        grouped,
        x="date",
        y="total_volume",
        color="type_display",
        color_discrete_map=TYPE_COLORS,
        custom_data=["wow_text", "comparison_text"],
        title="Weekly Sales Volume Over Time",
    )
    fig.update_traces(
        mode="lines+markers",
        hovertemplate=(
            "Week: %{x|%d %b %Y}<br>Volume: %{y:,.0f}<br>WoW change: %{customdata[0]}"
            "<br>%{customdata[1]}<extra></extra>"
        ),
    )
    fig.update_yaxes(title="Total volume")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=460)


def fig_indexed_sales(df: pd.DataFrame, type_mode: str | None = "split"):
    if df.empty:
        return empty_figure()
    grouped = aggregate_timeseries_for_mode(df, "total_volume", type_mode)
    indexed = build_indexed(grouped, "total_volume", ["type_display"])
    fig = px.line(
        indexed,
        x="date",
        y="indexed_value",
        color="type_display",
        color_discrete_map=TYPE_COLORS,
        title="Indexed Sales Volume Change — First Visible Week = 100",
    )
    fig.update_traces(mode="lines+markers", hovertemplate="Week: %{x|%d %b %Y}<br>Index: %{y:.1f}<extra></extra>")
    fig.add_hline(y=100, line_dash="dash", line_color="#B7AEA5")
    fig.update_yaxes(title="Index")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=420)


def fig_sales_region_lines(df: pd.DataFrame, top_n: int, comparison_df: pd.DataFrame | None = None, comparison_enabled: bool = False):
    if df.empty:
        return empty_figure()
    top_regions = df.groupby("region", as_index=False)["total_volume"].sum().nlargest(top_n, "total_volume")["region"]
    grouped = (
        df[df["region"].isin(top_regions)]
        .groupby(["date", "region"], as_index=False)["total_volume"]
        .sum()
    )
    grouped = add_wow_change(grouped, "total_volume", ["region"])
    comp_lookup = {}
    if comparison_enabled and comparison_df is not None and not comparison_df.empty:
        comp_lookup = comparison_lookup_by_group(
            df[df["region"].isin(top_regions)],
            comparison_df[comparison_df["region"].isin(top_regions)],
            ["region"],
            "total_volume",
        )
    grouped = add_comparison_hover(grouped, comp_lookup, ["region"], comparison_enabled)

    fig = px.line(
        grouped,
        x="date",
        y="total_volume",
        color="region",
        custom_data=["wow_text", "comparison_text"],
        title=f"Weekly Sales Volume by Region — Top {top_n}",
    )
    fig.update_traces(
        mode="lines",
        hovertemplate=(
            "Week: %{x|%d %b %Y}<br>Volume: %{y:,.0f}<br>WoW change: %{customdata[0]}"
            "<br>%{customdata[1]}<extra></extra>"
        ),
    )
    fig.update_yaxes(title="Total volume")
    fig.update_xaxes(title=None)
    fig = base_layout(fig, height=500)
    fig.update_layout(
        legend={"orientation": "h", "yanchor": "top", "y": -0.18, "xanchor": "left", "x": 0},
        margin={"l": 40, "r": 24, "t": 64, "b": 120},
    )
    return fig


def fig_price_over_time(
    df: pd.DataFrame,
    comparison_df: pd.DataFrame | None = None,
    comparison_enabled: bool = False,
    type_mode: str | None = "split",
):
    if df.empty:
        return empty_figure()
    grouped = aggregate_timeseries_for_mode(df, "average_price", type_mode).sort_values(["type_display", "date"])
    grouped = add_wow_change(grouped, "average_price", ["type_display"])

    comp_lookup = {}
    if comparison_enabled and comparison_df is not None and not comparison_df.empty:
        if type_mode == "both_total":
            cur_lookup_df = df.copy()
            cur_lookup_df["type_display"] = COMBINED_TYPE_LABEL
            comp_lookup_df = comparison_df.copy()
            comp_lookup_df["type_display"] = COMBINED_TYPE_LABEL
        else:
            cur_lookup_df = df.rename(columns={"type": "type_display"})
            comp_lookup_df = comparison_df.rename(columns={"type": "type_display"})
        comp_lookup = comparison_lookup_by_group(cur_lookup_df, comp_lookup_df, ["type_display"], "average_price")
    grouped = add_comparison_hover(grouped, comp_lookup, ["type_display"], comparison_enabled)

    fig = px.line(
        grouped,
        x="date",
        y="average_price",
        color="type_display",
        color_discrete_map=TYPE_COLORS,
        custom_data=["wow_text", "comparison_text"],
        title="Weekly Average Price Over Time",
    )
    fig.update_traces(
        mode="lines+markers",
        hovertemplate=(
            "Week: %{x|%d %b %Y}<br>Average price: $%{y:.2f}<br>WoW change: %{customdata[0]}"
            "<br>%{customdata[1]}<extra></extra>"
        ),
    )
    fig.update_yaxes(title="Average price")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=460)


def fig_indexed_price(df: pd.DataFrame, type_mode: str | None = "split"):
    if df.empty:
        return empty_figure()
    grouped = aggregate_timeseries_for_mode(df, "average_price", type_mode)
    indexed = build_indexed(grouped, "average_price", ["type_display"])
    fig = px.line(
        indexed,
        x="date",
        y="indexed_value",
        color="type_display",
        color_discrete_map=TYPE_COLORS,
        title="Indexed Price Change — First Visible Week = 100",
    )
    fig.update_traces(mode="lines+markers", hovertemplate="Week: %{x|%d %b %Y}<br>Index: %{y:.1f}<extra></extra>")
    fig.add_hline(y=100, line_dash="dash", line_color="#B7AEA5")
    fig.update_yaxes(title="Index")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=420)


def fig_price_region_lines(df: pd.DataFrame, top_n: int, comparison_df: pd.DataFrame | None = None, comparison_enabled: bool = False):
    if df.empty:
        return empty_figure()
    top_regions = df.groupby("region", as_index=False)["total_volume"].sum().nlargest(top_n, "total_volume")["region"]
    grouped = (
        df[df["region"].isin(top_regions)]
        .groupby(["date", "region"], as_index=False)["average_price"]
        .mean()
    )
    grouped = add_wow_change(grouped, "average_price", ["region"])
    comp_lookup = {}
    if comparison_enabled and comparison_df is not None and not comparison_df.empty:
        comp_lookup = comparison_lookup_by_group(
            df[df["region"].isin(top_regions)],
            comparison_df[comparison_df["region"].isin(top_regions)],
            ["region"],
            "average_price",
        )
    grouped = add_comparison_hover(grouped, comp_lookup, ["region"], comparison_enabled)

    fig = px.line(
        grouped,
        x="date",
        y="average_price",
        color="region",
        custom_data=["wow_text", "comparison_text"],
        title=f"Weekly Average Price by Region — Top {top_n}",
    )
    fig.update_traces(
        mode="lines",
        hovertemplate=(
            "Week: %{x|%d %b %Y}<br>Average price: $%{y:.2f}<br>WoW change: %{customdata[0]}"
            "<br>%{customdata[1]}<extra></extra>"
        ),
    )
    fig.update_yaxes(title="Average price")
    fig.update_xaxes(title=None)
    return base_layout(fig, height=460)


# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------

def kpi_card(title: str, value: str, detail: str = ""):
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(title, className="kpi-title"),
            html.Div(value, className="kpi-value"),
            html.Div(detail, className="kpi-detail"),
        ],
    )


def section(title: str, description: str, children):
    return html.Div(
        className="section-card",
        children=[
            html.Div(
                [
                    html.H2(title),
                    html.P(description, className="section-description"),
                ],
                className="section-header",
            ),
            children,
        ],
    )


def graph_card(graph_id: str):
    return html.Div(className="chart-card", children=[dcc.Graph(id=graph_id, config={"displayModeBar": False})])


# -----------------------------------------------------------------------------
# Avocado artwork (inline SVG, no external files)
# -----------------------------------------------------------------------------

import base64

_LEFT_HALF = "M50 8 C34 8 28 32 24 50 C14 72 16 112 50 114 Z"
_RIGHT_HALF = "M50 8 C66 8 72 32 76 50 C86 72 84 112 50 114 Z"


def _avocado_svg(animated: bool) -> str:
    style = ""
    if animated:
        style = """<style>
        .l{transform-origin:50px 114px;animation:l 1.4s ease-in-out infinite}
        .r{transform-origin:50px 114px;animation:r 1.4s ease-in-out infinite}
        .p{transform-origin:50px 80px;animation:p 1.4s ease-in-out infinite}
        @keyframes l{0%,100%{transform:none}50%{transform:translateX(-5px) rotate(-7deg)}}
        @keyframes r{0%,100%{transform:none}50%{transform:translateX(5px) rotate(7deg)}}
        @keyframes p{0%,100%{transform:none}50%{transform:translateY(-12px) rotate(25deg)}}
        </style>"""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 122">' + style +
        f'<path class="l" d="{_LEFT_HALF}" fill="#D5E59A" stroke="{TYPE_COLORS["conventional"]}" stroke-width="6" stroke-linejoin="round"/>'
        f'<g class="r"><path d="{_RIGHT_HALF}" fill="#D5E59A" stroke="{TYPE_COLORS["conventional"]}" stroke-width="6" stroke-linejoin="round"/>'
        f'<circle class="p" cx="50" cy="80" r="15" fill="{TYPE_COLORS["organic"]}"/>'
        '<circle class="p" cx="45" cy="75" r="4" fill="#FFFFFF" opacity="0.35"/></g></svg>'
    )


def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


AVOCADO_ICON = _svg_data_uri(_avocado_svg(animated=False))
AVOCADO_LOADER = _svg_data_uri(_avocado_svg(animated=True))


def avocado_loader():
    return html.Div(
        [
            html.Img(src=AVOCADO_LOADER, alt="", className="avo-loader-img"),
            html.Div("Slicing avocados…", className="avo-loader-text"),
        ],
        className="avo-loader",
        role="status",
    )


# -----------------------------------------------------------------------------
# App setup and CSS
# -----------------------------------------------------------------------------

app = Dash(__name__, suppress_callback_exceptions=True, compress=True)
server = app.server
app.title = "Avocado Sales Dashboard"

APP_CSS = f"""
body {{
    background: {BACKGROUND};
    margin: 0;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    color: {TEXT};
}}
.app-shell {{
    min-height: 100vh;
    background: {BACKGROUND};
}}
.topbar {{
    background: rgba(255, 255, 255, 0.92);
    border-bottom: 1px solid {CARD_BORDER};
    padding: 18px 28px 10px;
    position: sticky;
    top: 0;
    z-index: 20;
    backdrop-filter: blur(10px);
}}
.title-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
}}
.title-avocado {{
    width: 26px;
    height: 32px;
    margin-right: 10px;
    vertical-align: -4px;
}}
.content-loading {{
    flex: 1;
    min-width: 0;
}}
.avo-loader {{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 30;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 22px 28px 18px;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid {CARD_BORDER};
    border-radius: 18px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
}}
.avo-loader-img {{
    width: 64px;
    height: 78px;
}}
.avo-loader-text {{
    font-size: 13px;
    color: {MUTED};
    letter-spacing: 0.02em;
}}
.app-title {{
    margin: 0;
    font-size: 26px;
    letter-spacing: -0.03em;
}}
.app-subtitle {{
    margin: 6px 0 0;
    color: {MUTED};
    font-size: 14px;
}}
.main-layout {{
    display: flex;
    gap: 20px;
    padding: 22px 28px 40px;
}}
.sidebar {{
    width: 330px;
    min-width: 330px;
    transition: all 0.2s ease;
}}
.sidebar.collapsed {{
    width: 64px;
    min-width: 64px;
}}
.sidebar-card {{
    background: white;
    border: 1px solid {CARD_BORDER};
    border-radius: 18px;
    padding: 18px;
    position: sticky;
    top: 112px;
    max-height: calc(100vh - 132px);
    overflow-y: auto;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.035);
}}
.sidebar.collapsed .filter-content {{
    display: none;
}}
.sidebar-toggle {{
    border: 1px solid {CARD_BORDER};
    background: #FAFAF8;
    color: {TEXT};
    border-radius: 12px;
    padding: 9px 12px;
    width: 100%;
    cursor: pointer;
    font-weight: 650;
}}
.filter-block {{
    border-top: 1px solid {CARD_BORDER};
    padding-top: 16px;
    margin-top: 16px;
}}
.filter-block h3 {{
    font-size: 13px;
    margin: 0 0 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {MUTED};
}}
.filter-label {{
    font-size: 12px;
    font-weight: 650;
    color: {TEXT};
    display: block;
    margin: 12px 0 6px;
}}
.content {{
    flex: 1;
    min-width: 0;
}}
.section-card {{
    background: white;
    border: 1px solid {CARD_BORDER};
    border-radius: 20px;
    padding: 22px;
    margin-bottom: 20px;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.035);
}}
.section-header h2 {{
    margin: 0;
    font-size: 22px;
    letter-spacing: -0.02em;
}}
.section-description {{
    margin: 7px 0 18px;
    color: {MUTED};
    line-height: 1.45;
}}
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(5, minmax(160px, 1fr));
    gap: 14px;
}}
.kpi-card {{
    border: 1px solid {CARD_BORDER};
    background: #FAFAF8;
    border-radius: 16px;
    padding: 16px;
}}
.kpi-title {{
    color: {MUTED};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}}
.kpi-value {{
    margin-top: 8px;
    font-size: 24px;
    font-weight: 760;
    letter-spacing: -0.03em;
}}
.kpi-detail {{
    margin-top: 4px;
    color: {MUTED};
    font-size: 13px;
}}
.two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}}
.chart-stack {{
    display: flex;
    flex-direction: column;
    gap: 16px;
}}
.chart-card {{
    border: 1px solid {CARD_BORDER};
    border-radius: 16px;
    overflow: hidden;
    background: white;
}}
.tab-holder .tab {{
    border: none !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    padding: 12px 14px !important;
    color: {MUTED} !important;
    font-weight: 650;
}}
.tab-holder .tab--selected {{
    color: {TEXT} !important;
    border-bottom: 2px solid #1F5D3A !important;
}}
.Select-control, .DateInput_input, .DateRangePickerInput {{
    border-color: {CARD_BORDER} !important;
    border-radius: 12px !important;
}}
button {{
    font-family: inherit;
}}
.comparison-note {{
    color: {MUTED};
    font-size: 13px;
    margin-top: 10px;
}}
.rc-slider-track {{
    background-color: #1F5D3A;
}}
.rc-slider-dot-active, .rc-slider-handle {{
    border-color: #1F5D3A;
}}
input[type="checkbox"] {{
    accent-color: #1F5D3A;
}}
.check-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    color: {TEXT};
    font-size: 13px;
    margin-top: 10px;
}}
.help-text {{
    color: {MUTED};
    font-size: 12px;
    line-height: 1.35;
    margin-top: 6px;
}}
@media (max-width: 1100px) {{
    .main-layout {{
        flex-direction: column;
    }}
    .sidebar {{
        width: 100%;
        min-width: 0;
    }}
    .kpi-grid, .two-col {{
        grid-template-columns: 1fr;
    }}
}}
"""

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        <link rel="icon" type="image/svg+xml" href="__AVOCADO_ICON__">
        {%css%}
        <style>
""" + APP_CSS + """
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""
app.index_string = app.index_string.replace("__AVOCADO_ICON__", AVOCADO_ICON)

app.layout = html.Div(
    [
        dcc.Store(id="sidebar-state", data={"collapsed": False}),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.H1(
                                    [html.Img(src=AVOCADO_ICON, alt="", className="title-avocado"), "Avocado Sales Dashboard"],
                                    className="app-title",
                                ),
                                html.P(
                                    "Explore weekly avocado sales, prices, types, and regional market dynamics.",
                                    className="app-subtitle",
                                ),
                            ]
                        ),
                        html.Div(id="period-summary", className="app-subtitle"),
                    ],
                    className="title-row",
                ),
                dcc.Tabs(
                    id="tabs",
                    value="summary",
                    className="tab-holder",
                    children=[
                        dcc.Tab(label="Executive Summary", value="summary", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Markets & Regions", value="regions", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Sales Evolution", value="sales", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Price Evolution", value="prices", className="tab", selected_className="tab--selected"),
                    ],
                ),
            ],
            className="topbar",
        ),
        html.Div(
            [
                html.Div(
                    id="sidebar",
                    className="sidebar",
                    children=[
                        html.Div(
                            className="sidebar-card",
                            children=[
                                html.Button("Collapse filters", id="sidebar-toggle", className="sidebar-toggle", n_clicks=0),
                                html.Div(
                                    className="filter-content",
                                    children=[
                                        html.Div(
                                            className="filter-block",
                                            children=[
                                                html.H3("Period controls"),
                                                html.Label("Primary period preset", className="filter-label"),
                                                dcc.Dropdown(
                                                    id="primary-period-preset",
                                                    options=[
                                                        {"label": "Last week", "value": "last_week"},
                                                        {"label": "Last month", "value": "last_month"},
                                                        {"label": "Last 6 months", "value": "last_6m"},
                                                        {"label": "Last year", "value": "last_year"},
                                                        {"label": "Full dataset", "value": "full"},
                                                        {"label": "Custom range", "value": "custom"},
                                                    ],
                                                    value="full",
                                                    clearable=False,
                                                ),
                                                html.Label("Primary custom date range", className="filter-label"),
                                                dcc.DatePickerRange(
                                                    id="primary-date-range",
                                                    min_date_allowed=MIN_DATE,
                                                    max_date_allowed=MAX_DATE,
                                                    start_date=MIN_DATE,
                                                    end_date=MAX_DATE,
                                                    display_format="DD MMM YYYY",
                                                ),
                                                html.Label(className="check-row", children=[
                                                    dcc.Checklist(
                                                        id="comparison-enabled",
                                                        options=[{"label": "", "value": "enabled"}],
                                                        value=[],
                                                        inputStyle={"marginRight": "0px"},
                                                    ),
                                                    html.Span("Enable comparison mode"),
                                                ]),
                                                html.Label("Comparison period preset", className="filter-label"),
                                                dcc.Dropdown(
                                                    id="comparison-period-preset",
                                                    options=[
                                                        {"label": "Previous equivalent period", "value": "previous"},
                                                        {"label": "Same period previous year", "value": "previous_year"},
                                                        {"label": "Custom comparison range", "value": "custom"},
                                                    ],
                                                    value="previous",
                                                    clearable=False,
                                                ),
                                                html.Label("Comparison custom date range", className="filter-label"),
                                                dcc.DatePickerRange(
                                                    id="comparison-date-range",
                                                    min_date_allowed=MIN_DATE,
                                                    max_date_allowed=MAX_DATE,
                                                    start_date=MIN_DATE,
                                                    end_date=MAX_DATE,
                                                    display_format="DD MMM YYYY",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="filter-block",
                                            children=[
                                                html.H3("Region controls"),
                                                html.Label("Region level", className="filter-label"),
                                                dcc.RadioItems(
                                                    id="region-level",
                                                    options=[
                                                        {"label": " Metro markets", "value": "metro"},
                                                        {"label": " Broad US regions", "value": "broad"},
                                                    ],
                                                    value="metro",
                                                    inputStyle={"marginRight": "6px", "marginLeft": "0px"},
                                                    labelStyle={"display": "block", "marginBottom": "8px"},
                                                ),
                                                html.Div(
                                                    "Metro markets are cities like LosAngeles or NewYork. Broad regions "
                                                    "(West, Northeast, ...) contain those cities, so the two are never mixed. "
                                                    "If nothing is selected above, every region at this level is included.",
                                                    className="help-text",
                                                ),
                                                html.Label("Region groups", className="filter-label"),
                                                dcc.Dropdown(
                                                    id="region-groups",
                                                    options=[{"label": key, "value": key} for key in REGION_GROUPS],
                                                    value=[],
                                                    multi=True,
                                                    placeholder="Choose one or more groups",
                                                ),
                                                html.Label("Individual regions", className="filter-label"),
                                                dcc.Dropdown(
                                                    id="regions",
                                                    options=[{"label": region, "value": region} for region in available_regions("metro")],
                                                    value=[],
                                                    multi=True,
                                                    placeholder="All regions at this level",
                                                ),
                                                html.Label("Top N regions for ranking views", className="filter-label"),
                                                dcc.Slider(
                                                    id="top-n",
                                                    min=5,
                                                    max=25,
                                                    step=1,
                                                    value=10,
                                                    marks={5: "5", 10: "10", 15: "15", 20: "20", 25: "25"},
                                                    tooltip={"placement": "bottom", "always_visible": False},
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="filter-block",
                                            children=[
                                                html.H3("Type controls"),
                                                html.Label("Avocado type view", className="filter-label"),
                                                dcc.RadioItems(
                                                    id="type-mode",
                                                    options=[
                                                        {"label": " Conventional", "value": "conventional"},
                                                        {"label": " Organic", "value": "organic"},
                                                        {"label": " Both / total", "value": "both_total"},
                                                        {"label": " Split by type", "value": "split"},
                                                    ],
                                                    value="split",
                                                    inputStyle={"marginRight": "6px", "marginLeft": "0px"},
                                                    labelStyle={"display": "block", "marginBottom": "8px"},
                                                ),
                                                html.Div(
                                                    "Use Both / total when you care about total sales rather than the organic/conventional split.",
                                                    className="help-text",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ],
                ),
                dcc.Loading(
                    html.Div(id="tab-content", className="content"),
                    custom_spinner=avocado_loader(),
                    delay_show=250,
                    overlay_style={"visibility": "visible", "opacity": 0.45},
                    parent_className="content-loading",
                ),
            ],
            className="main-layout",
        ),
    ],
    className="app-shell",
)


# -----------------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------------

@app.callback(
    Output("sidebar-state", "data"),
    Input("sidebar-toggle", "n_clicks"),
    State("sidebar-state", "data"),
    prevent_initial_call=True,
)
def toggle_sidebar(n_clicks, state):
    collapsed = not (state or {}).get("collapsed", False)
    return {"collapsed": collapsed}


@app.callback(
    Output("sidebar", "className"),
    Output("sidebar-toggle", "children"),
    Input("sidebar-state", "data"),
)
def update_sidebar_state(state):
    collapsed = (state or {}).get("collapsed", False)
    if collapsed:
        return "sidebar collapsed", "Filters"
    return "sidebar", "Collapse filters"


@app.callback(
    Output("regions", "options"),
    Output("regions", "value"),
    Output("region-groups", "disabled"),
    Output("region-groups", "value"),
    Input("region-level", "value"),
    State("regions", "value"),
    State("region-groups", "value"),
)
def update_region_options(region_level, current_regions, current_groups):
    allowed = available_regions(region_level)
    current = [region for region in (current_regions or []) if region in allowed]
    is_broad = region_level == "broad"
    groups = [] if is_broad else (current_groups or [])
    return [{"label": region, "value": region} for region in allowed], current, is_broad, groups


@app.callback(
    Output("period-summary", "children"),
    Input("primary-period-preset", "value"),
    Input("primary-date-range", "start_date"),
    Input("primary-date-range", "end_date"),
    Input("comparison-enabled", "value"),
    Input("comparison-period-preset", "value"),
    Input("comparison-date-range", "start_date"),
    Input("comparison-date-range", "end_date"),
)
def update_period_summary(primary_preset, primary_start, primary_end, comparison_enabled, comparison_preset, comparison_start, comparison_end):
    start, end = period_bounds(primary_preset, primary_start, primary_end)
    label = f"Selected period: {clean_label(primary_preset)} · {date_label(start, end)}"
    if "enabled" in (comparison_enabled or []):
        comp_start, comp_end = comparison_bounds(start, end, comparison_preset, comparison_start, comparison_end)
        if comp_start > comp_end:
            label += f" | Comparison: {clean_label(comparison_preset)} · not available (data starts {MIN_DATE:%d %b %Y})"
        else:
            label += f" | Comparison: {clean_label(comparison_preset)} · {date_label(comp_start, comp_end)}"
    return label


@app.callback(
    Output("tab-content", "children"),
    Input("tabs", "value"),
)
def render_tab(tab):
    if tab == "regions":
        return html.Div(
            [
                section(
                    "Markets & Regions",
                    "Identify the largest avocado markets and compare regional volume, pricing, opportunity, and type mix.",
                    html.Div(
                        className="chart-stack",
                        children=[
                            graph_card("top-markets-chart"),
                            graph_card("region-price-chart"),
                            graph_card("opportunity-map-chart"),
                            graph_card("type-mix-chart"),
                        ],
                    ),
                )
            ]
        )
    if tab == "sales":
        return html.Div(
            [
                section(
                    "Sales Evolution",
                    "Track weekly sales volume over time by avocado type and region. Hover labels include week-over-week and comparison-period percentage change.",
                    html.Div(
                        className="chart-stack",
                        children=[
                            graph_card("sales-time-chart"),
                            graph_card("indexed-sales-chart"),
                            graph_card("sales-region-lines-chart"),
                        ],
                    ),
                )
            ]
        )
    if tab == "prices":
        return html.Div(
            [
                section(
                    "Price Evolution",
                    "Track weekly average prices over time by avocado type and region. Hover labels include week-over-week and comparison-period percentage change.",
                    html.Div(
                        className="chart-stack",
                        children=[
                            graph_card("price-time-chart"),
                            graph_card("indexed-price-chart"),
                            graph_card("price-region-lines-chart"),
                        ],
                    ),
                )
            ]
        )
    return html.Div(
        [
            section(
                "Executive Summary",
                "High-level overview of market size, pricing, top region, best-selling avocado type, and selected period.",
                html.Div(
                    [
                        html.Div(id="kpi-grid", className="kpi-grid"),
                        html.Div(
                            className="two-col",
                            style={"marginTop": "18px"},
                            children=[
                                graph_card("volume-by-type-chart"),
                                graph_card("price-by-type-chart"),
                            ],
                        ),
                    ]
                ),
            )
        ]
    )


@app.callback(
    Output("kpi-grid", "children"),
    Output("volume-by-type-chart", "figure"),
    Output("price-by-type-chart", "figure"),
    Input("primary-period-preset", "value"),
    Input("primary-date-range", "start_date"),
    Input("primary-date-range", "end_date"),
    Input("comparison-enabled", "value"),
    Input("comparison-period-preset", "value"),
    Input("comparison-date-range", "start_date"),
    Input("comparison-date-range", "end_date"),
    Input("type-mode", "value"),
    Input("regions", "value"),
    Input("region-groups", "value"),
    Input("region-level", "value"),
)
def update_summary(
    primary_preset,
    primary_start,
    primary_end,
    comparison_enabled,
    comparison_preset,
    comparison_start,
    comparison_end,
    type_mode,
    selected_regions,
    selected_groups,
    region_level_value,
):
    start, end = period_bounds(primary_preset, primary_start, primary_end)
    region_level = region_level_value or "metro"
    selected_types = selected_types_from_mode(type_mode)
    current_df = apply_filters(start, end, selected_types, selected_regions, selected_groups, region_level)

    comp_enabled = "enabled" in (comparison_enabled or [])
    comp_start, comp_end = comparison_bounds(start, end, comparison_preset, comparison_start, comparison_end)
    comp_df = apply_filters(comp_start, comp_end, selected_types, selected_regions, selected_groups, region_level)

    total_volume = current_df["total_volume"].sum() if not current_df.empty else float("nan")
    avg_price = current_df["average_price"].mean() if not current_df.empty else float("nan")

    if current_df.empty:
        top_region = "—"
        region_count = 0
        best_type = "—"
    else:
        region_grouped = current_df.groupby("region", as_index=False)["total_volume"].sum()
        top_region = region_grouped.sort_values("total_volume", ascending=False).iloc[0]["region"]
        region_count = current_df["region"].nunique()
        type_grouped = current_df.groupby("type", as_index=False)["total_volume"].sum()
        best_type = type_grouped.sort_values("total_volume", ascending=False).iloc[0]["type"].title()

    period_text = date_label(start, end)
    volume_detail = ""
    price_detail = ""
    if comp_enabled and comp_df.empty:
        volume_detail = price_detail = NO_COMPARISON_TEXT
    elif comp_enabled:
        comp_volume = comp_df["total_volume"].sum() if not comp_df.empty else float("nan")
        comp_price = comp_df["average_price"].mean() if not comp_df.empty else float("nan")
        volume_detail = f"{pct_delta_text(total_volume, comp_volume)} vs comparison period"
        price_detail = f"{pct_delta_text(avg_price, comp_price)} vs comparison period"

    cards = [
        kpi_card("Total volume sold", format_number(total_volume), volume_detail),
        kpi_card("Average price", format_price(avg_price), price_detail),
        kpi_card("Top-selling region", f"{top_region}", f"Top-selling region: {top_region} (out of {region_count} regions)"),
        kpi_card("Best-selling avocado type", best_type, "Based on total volume"),
        kpi_card("Selected period", period_text, clean_label(primary_preset)),
    ]

    volume_fig = fig_summary_volume(current_df, comp_df, comp_enabled, type_mode)
    price_fig = fig_summary_price(current_df, comp_df, comp_enabled, type_mode)
    if comp_enabled and comp_df.empty and not current_df.empty:
        for fig in (volume_fig, price_fig):
            add_no_comparison_note(fig)
    return cards, volume_fig, price_fig


@app.callback(
    Output("top-markets-chart", "figure"),
    Output("region-price-chart", "figure"),
    Output("opportunity-map-chart", "figure"),
    Output("type-mix-chart", "figure"),
    Input("primary-period-preset", "value"),
    Input("primary-date-range", "start_date"),
    Input("primary-date-range", "end_date"),
    Input("comparison-enabled", "value"),
    Input("comparison-period-preset", "value"),
    Input("comparison-date-range", "start_date"),
    Input("comparison-date-range", "end_date"),
    Input("type-mode", "value"),
    Input("regions", "value"),
    Input("region-groups", "value"),
    Input("region-level", "value"),
    Input("top-n", "value"),
)
def update_regions(
    primary_preset,
    primary_start,
    primary_end,
    comparison_enabled,
    comparison_preset,
    comparison_start,
    comparison_end,
    type_mode,
    selected_regions,
    selected_groups,
    region_level_value,
    top_n,
):
    start, end = period_bounds(primary_preset, primary_start, primary_end)
    region_level = region_level_value or "metro"
    selected_types = selected_types_from_mode(type_mode)
    current_df = apply_filters(start, end, selected_types, selected_regions, selected_groups, region_level)
    comp_enabled = "enabled" in (comparison_enabled or [])
    comp_start, comp_end = comparison_bounds(start, end, comparison_preset, comparison_start, comparison_end)
    comp_df = apply_filters(comp_start, comp_end, selected_types, selected_regions, selected_groups, region_level)
    top_n = top_n or 10
    return (
        fig_top_markets(current_df, top_n, comp_df, comp_enabled, type_mode),
        fig_region_price_dumbbell(current_df, top_n, comp_df, comp_enabled),
        fig_opportunity_map(current_df, top_n, comp_df, comp_enabled, type_mode),
        fig_type_mix(current_df, top_n, comp_df, comp_enabled),
    )


@app.callback(
    Output("sales-time-chart", "figure"),
    Output("indexed-sales-chart", "figure"),
    Output("sales-region-lines-chart", "figure"),
    Input("primary-period-preset", "value"),
    Input("primary-date-range", "start_date"),
    Input("primary-date-range", "end_date"),
    Input("comparison-enabled", "value"),
    Input("comparison-period-preset", "value"),
    Input("comparison-date-range", "start_date"),
    Input("comparison-date-range", "end_date"),
    Input("type-mode", "value"),
    Input("regions", "value"),
    Input("region-groups", "value"),
    Input("region-level", "value"),
    Input("top-n", "value"),
)
def update_sales(
    primary_preset,
    primary_start,
    primary_end,
    comparison_enabled,
    comparison_preset,
    comparison_start,
    comparison_end,
    type_mode,
    selected_regions,
    selected_groups,
    region_level_value,
    top_n,
):
    start, end = period_bounds(primary_preset, primary_start, primary_end)
    region_level = region_level_value or "metro"
    selected_types = selected_types_from_mode(type_mode)
    current_df = apply_filters(start, end, selected_types, selected_regions, selected_groups, region_level)
    comp_enabled = "enabled" in (comparison_enabled or [])
    comp_start, comp_end = comparison_bounds(start, end, comparison_preset, comparison_start, comparison_end)
    comp_df = apply_filters(comp_start, comp_end, selected_types, selected_regions, selected_groups, region_level)
    return (
        fig_sales_over_time(current_df, comp_df, comp_enabled, type_mode),
        fig_indexed_sales(current_df, type_mode),
        fig_sales_region_lines(current_df, top_n or 10, comp_df, comp_enabled),
    )


@app.callback(
    Output("price-time-chart", "figure"),
    Output("indexed-price-chart", "figure"),
    Output("price-region-lines-chart", "figure"),
    Input("primary-period-preset", "value"),
    Input("primary-date-range", "start_date"),
    Input("primary-date-range", "end_date"),
    Input("comparison-enabled", "value"),
    Input("comparison-period-preset", "value"),
    Input("comparison-date-range", "start_date"),
    Input("comparison-date-range", "end_date"),
    Input("type-mode", "value"),
    Input("regions", "value"),
    Input("region-groups", "value"),
    Input("region-level", "value"),
    Input("top-n", "value"),
)
def update_prices(
    primary_preset,
    primary_start,
    primary_end,
    comparison_enabled,
    comparison_preset,
    comparison_start,
    comparison_end,
    type_mode,
    selected_regions,
    selected_groups,
    region_level_value,
    top_n,
):
    start, end = period_bounds(primary_preset, primary_start, primary_end)
    region_level = region_level_value or "metro"
    selected_types = selected_types_from_mode(type_mode)
    current_df = apply_filters(start, end, selected_types, selected_regions, selected_groups, region_level)
    comp_enabled = "enabled" in (comparison_enabled or [])
    comp_start, comp_end = comparison_bounds(start, end, comparison_preset, comparison_start, comparison_end)
    comp_df = apply_filters(comp_start, comp_end, selected_types, selected_regions, selected_groups, region_level)
    return (
        fig_price_over_time(current_df, comp_df, comp_enabled, type_mode),
        fig_indexed_price(current_df, type_mode),
        fig_price_region_lines(current_df, top_n or 10, comp_df, comp_enabled),
    )


if __name__ == "__main__":
    app.run(debug=True)
