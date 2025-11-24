import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from app.utils.config import API_URL

st.set_page_config(
    page_title="Database Explorer",
    page_icon="🗄️",
    layout="wide"
)

st.title("🗄️ Database Explorer")
st.markdown("Explore the raw data tables in the Traffic Safety database.")

# Helper function to fetch data
def fetch_api(endpoint):
    try:
        # Handle if API_URL already has /api/v1 or not
        base_url = API_URL.replace("/api/v1", "")
        url = f"{base_url}/api/v1{endpoint}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

# 1. Fetch Tables
tables = fetch_api("/database/tables")

if tables:
    selected_table = st.selectbox("Select a Table", tables)
    
    if selected_table:
        st.header(f"Table: {selected_table}")
        
        # 2. Fetch Schema
        schema = fetch_api(f"/database/schema/{selected_table}")
        
        if schema:
            with st.expander("View Schema"):
                schema_df = pd.DataFrame(schema)
                st.dataframe(schema_df, use_container_width=True)
        
        # 3. Fetch Data
        
        # Specialized logic for specific tables
        filter_params = ""
        if selected_table == "speed-distribution":
            st.subheader("🔍 Specialized Analysis: Speed Distribution")
            
            # Fetch unique intersections for filtering
            # Note: In a real app, we'd have a dedicated endpoint for distinct values
            # For now, we'll just let the user type or use a known list if available
            intersection_filter = st.text_input("Filter by Intersection (e.g., 'glebe-potomac')", "")
            
            if intersection_filter:
                filter_params = f"&filter_col=intersection&filter_val={intersection_filter}"
                st.info(f"Filtering by intersection: {intersection_filter}")

        limit = st.slider("Rows to fetch", 10, 5000, 1000)
        data = fetch_api(f"/database/data/{selected_table}?limit={limit}{filter_params}")
        
        if data:
            df = pd.DataFrame(data)
            st.subheader(f"Data Preview ({len(df)} rows)")
            st.dataframe(df, use_container_width=True)
            
            # 4. Visualization
            st.subheader("Visualization")
            
            if not df.empty:
                # Identify column types
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                datetime_cols = []
                # Try to identify datetime columns (heuristic)
                for col in df.columns:
                    if 'date' in col.lower() or 'time' in col.lower():
                        try:
                            # Handle BigInt timestamps (milliseconds)
                            if df[col].dtype == 'int64' and df[col].mean() > 1000000000000:
                                df[col] = pd.to_datetime(df[col], unit='ms')
                            # Handle BigInt timestamps (seconds)
                            elif df[col].dtype == 'int64' and df[col].mean() > 1000000000:
                                df[col] = pd.to_datetime(df[col], unit='s')
                            else:
                                pd.to_datetime(df[col])
                            datetime_cols.append(col)
                        except:
                            pass
                
                categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
                # Remove datetime cols from categorical if they were identified
                categorical_cols = [c for c in categorical_cols if c not in datetime_cols]

                # Specialized Visualization Options
                viz_options = ["Histogram", "Scatter Plot", "Box Plot", "Bar Chart", "Map"]
                
                if selected_table == "speed-distribution":
                    viz_options.insert(0, "Speed Distribution Over Time")

                viz_type = st.selectbox("Visualization Type", viz_options)
                
                if viz_type == "Speed Distribution Over Time":
                    if 'start_timestamp' in df.columns and 'speed_interval' in df.columns and 'count' in df.columns:
                        # Ensure timestamp is datetime
                        if df['start_timestamp'].dtype == 'int64':
                             df['start_timestamp'] = pd.to_datetime(df['start_timestamp'], unit='ms')
                        
                        # Aggregate by time bin if needed (e.g. hourly)
                        # For now, just plot raw
                        
                        fig = px.bar(
                            df, 
                            x='start_timestamp', 
                            y='count', 
                            color='speed_interval',
                            title="Speed Distribution Over Time",
                            labels={'start_timestamp': 'Time', 'count': 'Vehicle Count', 'speed_interval': 'Speed Range'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Required columns (start_timestamp, speed_interval, count) not found.")

                elif viz_type == "Histogram":
                    if numeric_cols:
                        col = st.selectbox("Select Column", numeric_cols)
                        fig = px.histogram(df, x=col, title=f"Distribution of {col}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No numeric columns found for histogram.")
                        
                elif viz_type == "Scatter Plot":
                    if len(numeric_cols) >= 2:
                        x_col = st.selectbox("X Axis", numeric_cols)
                        y_col = st.selectbox("Y Axis", numeric_cols, index=1)
                        color_col = st.selectbox("Color (Optional)", ["None"] + categorical_cols)
                        color = None if color_col == "None" else color_col
                        
                        fig = px.scatter(df, x=x_col, y=y_col, color=color, title=f"{x_col} vs {y_col}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Need at least 2 numeric columns for scatter plot.")
                        
                elif viz_type == "Box Plot":
                    if numeric_cols:
                        y_col = st.selectbox("Value Column", numeric_cols)
                        x_col = st.selectbox("Group By (Optional)", ["None"] + categorical_cols)
                        x = None if x_col == "None" else x_col
                        
                        fig = px.box(df, y=y_col, x=x, title=f"Box Plot of {y_col}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No numeric columns found for box plot.")
                        
                elif viz_type == "Bar Chart":
                    if categorical_cols:
                        col = st.selectbox("Category Column", categorical_cols)
                        counts = df[col].value_counts().reset_index()
                        counts.columns = [col, 'count']
                        fig = px.bar(counts, x=col, y='count', title=f"Counts of {col}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No categorical columns found for bar chart.")
                        
                elif viz_type == "Map":
                    # Look for lat/lon columns
                    lat_cols = [c for c in df.columns if 'lat' in c.lower() or 'y' == c.lower()]
                    lon_cols = [c for c in df.columns if 'lon' in c.lower() or 'x' == c.lower()]
                    
                    if lat_cols and lon_cols:
                        lat_col = st.selectbox("Latitude Column", lat_cols)
                        lon_col = st.selectbox("Longitude Column", lon_cols)
                        
                        # Filter out invalid lat/lon
                        map_df = df.dropna(subset=[lat_col, lon_col])
                        
                        fig = px.scatter_mapbox(
                            map_df, 
                            lat=lat_col, 
                            lon=lon_col, 
                            zoom=10,
                            mapbox_style="carto-positron"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No latitude/longitude columns found for map.")
        else:
            st.warning("No data found in this table.")

else:
    st.error("Could not fetch tables. Is the backend running?")
