import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configure logging for tracking parsing issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit page settings for a wider layout and custom title
st.set_page_config(page_title="India EV Market Dashboard", layout="wide")


# Cache data loading to optimize performance
@st.cache_data
def load_data():
    """
    Load and preprocess EV datasets:
    - Reads sales, registration, and maker location data from CSV files.
    - Filters out invalid date entries ('0') and parses dates in Indian format (DD/MM/YY).
    - Aggregates registration data by year, summing only numeric columns to avoid datetime errors.
    - Logs parsing issues for debugging and user feedback.
    """
    try:
        # Load datasets
        sales_df = pd.read_csv("datasets/ev_sales_by_makers_and_cat_15-24.csv")
        reg_df = pd.read_csv("datasets/ev_cat_01-24.csv")
        makers_df = pd.read_csv("datasets/EV Maker by Place.csv")

        # Transform sales data into long format
        sales_df = sales_df.melt(id_vars=["Cat", "Maker"],
                                 var_name="Year",
                                 value_name="Sales")
        sales_df["Year"] = sales_df["Year"].astype(int)

        # Clean registration data by removing invalid dates
        reg_df = reg_df[reg_df["Date"] != '0']

        # Parse dates with Indian format (DD/MM/YY) explicitly, handling invalid entries
        reg_df["Date"] = pd.to_datetime(reg_df["Date"], format='%d/%m/%y', errors='coerce')

        # Log and warn if there are parsing issues
        if reg_df["Date"].isna().any():
            logger.warning("Some dates could not be parsed and were set to NaT.")
            st.warning("Some dates in the dataset could not be parsed and were excluded.")

        # Drop rows with unparseable dates
        reg_df = reg_df.dropna(subset=["Date"])

        # Extract year from date for aggregation
        reg_df["Year"] = reg_df["Date"].dt.year

        # Group by year and sum only numeric columns to avoid summing datetime
        reg_df = reg_df.groupby("Year").sum(numeric_only=True).reset_index()

        return sales_df, reg_df, makers_df
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        st.error(f"Error loading data: {e}")
        raise


# Load preprocessed data with error handling
try:
    sales_df, reg_df, makers_df = load_data()
except Exception:
    st.stop()

# Sidebar for interactive user filters
st.sidebar.title("Filters")
year_range = st.sidebar.slider("Select Year Range", 2015, 2024, (2015, 2024))
categories = st.sidebar.multiselect("Select Categories",
                                    sales_df["Cat"].unique(),
                                    default=sales_df["Cat"].unique())
makers = st.sidebar.multiselect("Select Makers",
                                sales_df["Maker"].unique(),
                                default=sales_df["Maker"].unique()[:5])

# Apply filters to sales and registration data
filtered_sales = sales_df[(sales_df["Year"].between(year_range[0], year_range[1])) &
                          (sales_df["Cat"].isin(categories)) &
                          (sales_df["Maker"].isin(makers))]
filtered_reg = reg_df[reg_df["Year"].between(year_range[0], year_range[1])]

# Create dashboard tabs for different analyses
tabs = st.tabs(["Overview", "Sales by Category", "Maker Market Share",
                "Geographical Distribution", "Market Penetration",
                "Charging Infrastructure", "Top Performers", "Growth Rates"])

# Tab 1: Overview - Total EV sales trend
with tabs[0]:
    st.header("Overview")
    total_sales = filtered_sales.groupby("Year")["Sales"].sum().reset_index()
    fig = px.line(total_sales, x="Year", y="Sales", title="Total EV Sales Over Time")
    fig.add_vline(x=2015, line_dash="dash", annotation_text="FAME-I")
    fig.add_vline(x=2019, line_dash="dash", annotation_text="FAME-II")
    st.plotly_chart(fig, use_container_width=True)

# Tab 2: Sales by Category - Breakdown by vehicle type
with tabs[1]:
    st.header("Sales by Category")
    cat_sales = filtered_sales.groupby(["Year", "Cat"])["Sales"].sum().reset_index()
    fig = px.bar(cat_sales, x="Year", y="Sales", color="Cat",
                 title="EV Sales by Category")
    st.plotly_chart(fig, use_container_width=True)

# Tab 3: Maker Market Share - Top N makers by sales
with tabs[2]:
    st.header("Maker Market Share")
    maker_sales = filtered_sales.groupby("Maker")["Sales"].sum().reset_index()
    top_n = st.slider("Select Top N Makers", 5, 20, 10)
    top_makers = maker_sales.nlargest(top_n, "Sales")
    fig = px.pie(top_makers, values="Sales", names="Maker",
                 title=f"Top {top_n} Makers by Sales")
    st.plotly_chart(fig, use_container_width=True)

# Tab 4: Geographical Distribution - Manufacturers by state
with tabs[3]:
    st.header("Geographical Distribution")
    state_counts = makers_df["State"].value_counts().reset_index()
    state_counts.columns = ["State", "Count"]
    fig = px.bar(state_counts, x="State", y="Count",
                 title="Number of EV Manufacturers by State")
    st.plotly_chart(fig, use_container_width=True)

# Tab 5: Market Penetration - EV share in total registrations
with tabs[4]:
    st.header("Market Penetration")
    category_map = {
        "2W": ["TWO WHEELER(NT)", "TWO WHEELER(T)"],
        "3W": ["THREE WHEELER(NT)", "THREE WHEELER(T)"],
        "LMV": ["LIGHT MOTOR VEHICLE"]
    }
    penetration = []
    for cat, reg_cols in category_map.items():
        if cat in categories:
            ev_sales = filtered_sales[filtered_sales["Cat"] == cat].groupby("Year")["Sales"].sum()
            total_reg = filtered_reg[["Year"] + reg_cols].set_index("Year").sum(axis=1)
            share = (ev_sales / total_reg * 100).reset_index(name="Penetration")
            share["Category"] = cat
            penetration.append(share)
    penetration_df = pd.concat(penetration)
    fig = px.line(penetration_df, x="Year", y="Penetration", color="Category",
                  title="EV Market Penetration (%)")
    st.plotly_chart(fig, use_container_width=True)

# Tab 6: Charging Infrastructure - Comparison with sales
with tabs[5]:
    st.header("Charging Infrastructure")
    charging_data = pd.DataFrame({
        "Year": [2022, 2023, 2024],
        "Stations": [1800, 6586, 25202]
    })
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=charging_data["Year"], y=charging_data["Stations"],
                             name="Charging Stations", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=total_sales["Year"], y=total_sales["Sales"],
                             name="EV Sales", yaxis="y2"))
    fig.update_layout(
        title="Charging Stations vs. EV Sales",
        yaxis=dict(title="Charging Stations"),
        yaxis2=dict(title="EV Sales", overlaying="y", side="right")
    )
    st.plotly_chart(fig, use_container_width=True)

# Tab 7: Top Performers - Leading makers in a selected year
with tabs[6]:
    st.header("Top Performers")
    selected_year = st.selectbox("Select Year", range(year_range[0], year_range[1] + 1))
    top_makers = filtered_sales[filtered_sales["Year"] == selected_year].groupby("Maker")["Sales"].sum().nlargest(
        5).reset_index()
    st.table(top_makers)

# Tab 8: Growth Rates - Year-over-year sales growth
with tabs[7]:
    st.header("Growth Rates")
    total_sales["Growth"] = total_sales["Sales"].pct_change() * 100
    fig = px.bar(total_sales, x="Year", y="Growth",
                 title="Year-over-Year Sales Growth (%)")
    st.plotly_chart(fig, use_container_width=True)
