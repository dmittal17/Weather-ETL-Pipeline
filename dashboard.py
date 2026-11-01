"""Weather ETL Interactive Dashboard.

Built with Streamlit and Plotly to explore and visualize hourly weather
data stored in an SQLite database by the weather-etl-pipeline.
"""

from pathlib import Path
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# ==============================================================================
# Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="Weather ETL Dashboard",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Database location relative to this file
DB_PATH = Path(__file__).resolve().parent / "data" / "weather.db"
TIMEZONE = "Asia/Kolkata"

# Consistent color palette for cities across all charts
CITY_COLORS = {
    "Mumbai": "#1f77b4",     # Steel Blue
    "Delhi": "#ff7f0e",      # Amber Orange
    "Bengaluru": "#2ca02c",  # Forest Green
    "Chennai": "#d62728",    # Crimson Red
    "Kolkata": "#9467bd",    # Purple
}


# ==============================================================================
# Data Loading & Caching
# ==============================================================================
@st.cache_data(ttl=300)
def load_weather_data() -> pd.DataFrame:
    """Load weather readings from the SQLite database.

    Caches query results for 5 minutes (300s) to keep dashboard responsive.
    Converts timestamps from UTC to Asia/Kolkata for local representation.
    """
    if not DB_PATH.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Verify table exists before querying
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='weather_readings'"
            )
            if not cursor.fetchone():
                return pd.DataFrame()

            # Read all historical readings ordered by observation time
            query = "SELECT * FROM weather_readings ORDER BY observed_at ASC"
            df = pd.read_sql_query(query, conn)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Convert UTC timestamps to display timezone (Asia/Kolkata)
    df["observed_at"] = (
        pd.to_datetime(df["observed_at"], utc=True)
        .dt.tz_convert(TIMEZONE)
        .dt.tz_localize(None)
    )

    # Derive helper columns for filtering and grouping
    df["date"] = df["observed_at"].dt.date
    df["hour"] = df["observed_at"].dt.hour
    df["time_str"] = df["observed_at"].dt.strftime("%Y-%m-%d %H:%M")

    return df


# Load data
raw_df = load_weather_data()

# ==============================================================================
# Friendly empty-state handler
# ==============================================================================
if raw_df.empty:
    st.title("🌤️ Weather ETL Dashboard")
    st.warning("⚠️ Weather database or readings table is missing or empty.")
    st.info(
        "Please run the ETL pipeline first to populate the database:\n\n"
        "```bash\n"
        "python pipeline.py\n"
        "```\n"
        "After running the pipeline, click 'Refresh data' in the sidebar or reload this page."
    )
    if st.sidebar.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()
    st.stop()


# ==============================================================================
# Sidebar Filters & Controls
# ==============================================================================
st.sidebar.header("⚙️ Filters & Settings")

# 1. City selection (default: all available cities)
all_cities = sorted(raw_df["city"].unique().tolist())
selected_cities = st.sidebar.multiselect(
    "Select Cities",
    options=all_cities,
    default=all_cities,
    help="Filter observations for one or more cities",
)

if not selected_cities:
    st.sidebar.warning("Please select at least one city.")
    st.stop()

# 2. Date range picker
min_date = raw_df["date"].min()
max_date = raw_df["date"].max()

date_selection = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    help="Select start and end dates to filter data",
)

# Handle single date or range selection from date_input
if isinstance(date_selection, (tuple, list)):
    if len(date_selection) == 2:
        start_date, end_date = date_selection
    elif len(date_selection) == 1:
        start_date = end_date = date_selection[0]
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = date_selection

# 3. Temperature Unit Toggle (°C / °F)
temp_unit = st.sidebar.radio(
    "Temperature Unit",
    options=["°C", "°F"],
    horizontal=True,
    help="Switch between Celsius and Fahrenheit",
)

# Map chosen unit to respective column and label
is_celsius = temp_unit == "°C"
temp_col = "temperature_c" if is_celsius else "temperature_f"
feels_like_col = "feels_like_c" if is_celsius else "feels_like_f"

# Calculate feels_like_f if Fahrenheit is active
if not is_celsius and "feels_like_f" not in raw_df.columns:
    raw_df["feels_like_f"] = (raw_df["feels_like_c"] * 9 / 5 + 32).round(2)

# 4. Refresh Button
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption(f"Timezone: **{TIMEZONE}**")


# ==============================================================================
# Filter Data Based on User Input
# ==============================================================================
mask = (
    raw_df["city"].isin(selected_cities)
    & (raw_df["date"] >= start_date)
    & (raw_df["date"] <= end_date)
)
filtered_df = raw_df.loc[mask].copy()

if filtered_df.empty:
    st.warning("No data found for the selected city and date filters.")
    st.stop()


# ==============================================================================
# Dashboard Header
# ==============================================================================
st.title("🌤️ Weather ETL Dashboard")
st.markdown(
    "Real-time analytics, historical trends, and summary insights for Indian metropolitan cities "
    f"*(Times displayed in {TIMEZONE})*."
)
st.markdown("---")


# ==============================================================================
# Top KPI Cards
# ==============================================================================
# 1. Latest temperature per selected city
st.subheader("📍 Latest City Temperatures")
city_cols = st.columns(len(selected_cities))

# Find the latest reading for each city
latest_readings = (
    raw_df.sort_values("observed_at")
    .groupby("city")
    .last()
    .reset_index()
)

for idx, city in enumerate(selected_cities):
    city_data = latest_readings[latest_readings["city"] == city]
    with city_cols[idx]:
        if not city_data.empty:
            curr_temp = city_data[temp_col].values[0]
            curr_desc = city_data["weather_description"].values[0]
            curr_comfort = city_data["feels_like_category"].values[0]
            st.metric(
                label=city,
                value=f"{curr_temp:.1f} {temp_unit}",
                delta=f"{curr_desc} • {curr_comfort}",
                delta_color="off",
            )
        else:
            st.metric(label=city, value="N/A")

st.markdown("")

# 2. Overall aggregate KPIs for filtered range
st.subheader("📊 Period Highlights")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

avg_temp = filtered_df[temp_col].mean()
avg_humidity = filtered_df["humidity_pct"].mean()
total_rainfall = filtered_df["precipitation_mm"].sum()
rainy_hours = filtered_df["is_rainy"].sum()

with kpi1:
    st.metric(
        label=f"Average Temperature ({temp_unit})",
        value=f"{avg_temp:.1f} {temp_unit}",
    )
with kpi2:
    st.metric(
        label="Average Humidity",
        value=f"{avg_humidity:.1f}%",
    )
with kpi3:
    st.metric(
        label="Total Rainfall",
        value=f"{total_rainfall:.2f} mm",
    )
with kpi4:
    st.metric(
        label="Rainy Hours",
        value=f"{int(rainy_hours)} hrs",
    )

st.markdown("---")


# ==============================================================================
# Tabs Navigation
# ==============================================================================
tab_overview, tab_trends, tab_details = st.tabs(["Overview", "Trends", "Details"])


# ------------------------------------------------------------------------------
# TAB 1: OVERVIEW
# ------------------------------------------------------------------------------
with tab_overview:
    # Latest readings table for each city
    st.subheader("📋 Latest Readings per City")
    display_latest = latest_readings[latest_readings["city"].isin(selected_cities)][
        [
            "city",
            "time_str",
            temp_col,
            feels_like_col,
            "humidity_pct",
            "precipitation_mm",
            "wind_speed_kmh",
            "weather_description",
            "feels_like_category",
        ]
    ].rename(
        columns={
            "city": "City",
            "time_str": f"Observed At ({TIMEZONE})",
            temp_col: f"Temperature ({temp_unit})",
            feels_like_col: f"Feels Like ({temp_unit})",
            "humidity_pct": "Humidity (%)",
            "precipitation_mm": "Rainfall (mm)",
            "wind_speed_kmh": "Wind Speed (km/h)",
            "weather_description": "Condition",
            "feels_like_category": "Comfort Category",
        }
    )
    st.dataframe(display_latest, hide_index=True, use_container_width=True)

    st.markdown("---")

    # Bar chart 1: Daily average temperature per city
    # Bar chart 2: Total daily rainfall per city
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader(f"📅 Daily Average Temperature ({temp_unit})")
        daily_temp = (
            filtered_df.groupby(["city", "date"])[temp_col]
            .mean()
            .round(2)
            .reset_index()
        )
        # Format date for cleaner display
        daily_temp["date_str"] = daily_temp["date"].astype(str)
        fig_daily_temp = px.bar(
            daily_temp,
            x="date_str",
            y=temp_col,
            color="city",
            barmode="group",
            color_discrete_map=CITY_COLORS,
            labels={"date_str": "Date", temp_col: f"Avg Temp ({temp_unit})", "city": "City"},
        )
        fig_daily_temp.update_layout(
            legend_title_text="City",
            xaxis_title="Date",
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_daily_temp, use_container_width=True)

    with row1_col2:
        st.subheader("🌧️ Total Daily Rainfall (mm)")
        daily_rain = (
            filtered_df.groupby(["city", "date"])["precipitation_mm"]
            .sum()
            .round(2)
            .reset_index()
        )
        daily_rain["date_str"] = daily_rain["date"].astype(str)
        fig_daily_rain = px.bar(
            daily_rain,
            x="date_str",
            y="precipitation_mm",
            color="city",
            barmode="group",
            color_discrete_map=CITY_COLORS,
            labels={"date_str": "Date", "precipitation_mm": "Rainfall (mm)", "city": "City"},
        )
        fig_daily_rain.update_layout(
            legend_title_text="City",
            xaxis_title="Date",
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_daily_rain, use_container_width=True)

    # Bar chart 3: Average wind speed per city
    # Donut chart: Share of feels_like_category hours
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("💨 Average Wind Speed (km/h)")
        avg_wind = (
            filtered_df.groupby("city")["wind_speed_kmh"]
            .mean()
            .round(2)
            .reset_index()
        )
        fig_wind = px.bar(
            avg_wind,
            x="city",
            y="wind_speed_kmh",
            color="city",
            color_discrete_map=CITY_COLORS,
            labels={"city": "City", "wind_speed_kmh": "Wind Speed (km/h)"},
            text="wind_speed_kmh",
        )
        fig_wind.update_traces(texttemplate="%{text:.1f} km/h", textposition="outside")
        fig_wind.update_layout(
            showlegend=False,
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_wind, use_container_width=True)

    with row2_col2:
        st.subheader("🌡️ 'Feels Like' Comfort Distribution")
        comfort_counts = (
            filtered_df["feels_like_category"]
            .value_counts()
            .reset_index()
        )
        comfort_counts.columns = ["feels_like_category", "hours"]
        fig_comfort = px.pie(
            comfort_counts,
            names="feels_like_category",
            values="hours",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Plotly,
        )
        fig_comfort.update_traces(textposition="inside", textinfo="percent+label")
        fig_comfort.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_comfort, use_container_width=True)


# ------------------------------------------------------------------------------
# TAB 2: TRENDS
# ------------------------------------------------------------------------------
with tab_trends:
    # 1. Hourly Temperature Trend (Line chart)
    st.subheader(f"📈 Hourly Temperature Trend ({temp_unit})")
    fig_temp_trend = px.line(
        filtered_df,
        x="observed_at",
        y=temp_col,
        color="city",
        color_discrete_map=CITY_COLORS,
        labels={"observed_at": f"Time ({TIMEZONE})", temp_col: f"Temperature ({temp_unit})", "city": "City"},
    )
    fig_temp_trend.update_layout(
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig_temp_trend, use_container_width=True)

    st.markdown("---")

    # 2. Hourly Humidity Trend (Line chart)
    st.subheader("💧 Humidity Over Time (%)")
    fig_hum_trend = px.line(
        filtered_df,
        x="observed_at",
        y="humidity_pct",
        color="city",
        color_discrete_map=CITY_COLORS,
        labels={"observed_at": f"Time ({TIMEZONE})", "humidity_pct": "Humidity (%)", "city": "City"},
    )
    fig_hum_trend.update_layout(
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig_hum_trend, use_container_width=True)

    st.markdown("---")

    # 3. Heatmap: Average temperature by city and hour of day
    st.subheader(f"🔥 Temperature Heatmap by City and Hour of Day ({temp_unit})")
    heatmap_data = (
        filtered_df.groupby(["city", "hour"])[temp_col]
        .mean()
        .round(1)
        .reset_index()
    )

    # Pivot to create matrix of City vs Hour (0 to 23)
    heatmap_matrix = heatmap_data.pivot(
        index="city", columns="hour", values=temp_col
    )
    # Ensure all hours 0..23 are present as columns
    for h in range(24):
        if h not in heatmap_matrix.columns:
            heatmap_matrix[h] = None
    heatmap_matrix = heatmap_matrix.reindex(sorted(heatmap_matrix.columns), axis=1)

    fig_heatmap = px.imshow(
        heatmap_matrix,
        labels=dict(x="Hour of Day (0–23)", y="City", color=f"Avg Temp ({temp_unit})"),
        x=[f"{h:02d}:00" for h in heatmap_matrix.columns],
        y=heatmap_matrix.index,
        color_continuous_scale="RdYlBu_r",
        text_auto=".1f",
        aspect="auto",
    )
    fig_heatmap.update_layout(margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig_heatmap, use_container_width=True)


# ------------------------------------------------------------------------------
# TAB 3: DETAILS & DATA EXPORT
# ------------------------------------------------------------------------------
with tab_details:
    st.subheader("📄 Filtered Weather Dataset")
    st.write(
        f"Displaying **{len(filtered_df):,}** readings matching your selected filters."
    )

    # Clean display columns
    export_df = filtered_df[
        [
            "id",
            "city",
            "time_str",
            "temperature_c",
            "temperature_f",
            "feels_like_c",
            "humidity_pct",
            "precipitation_mm",
            "wind_speed_kmh",
            "wind_speed_ms",
            "weather_code",
            "weather_description",
            "feels_like_category",
            "is_rainy",
            "ingested_at",
        ]
    ].rename(columns={"time_str": f"observed_at_{TIMEZONE.lower()}"})

    # Download button for CSV
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv_bytes,
        file_name="weather_readings_filtered.csv",
        mime="text/csv",
        use_container_width=False,
    )

    st.dataframe(export_df, hide_index=True, use_container_width=True)
