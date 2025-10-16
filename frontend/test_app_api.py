"""
Live API Call Tester for Streamlit App

This creates a simple test page that shows you exactly what's happening
when the app calls the API.
"""

import streamlit as st
import requests
import time
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.api_client import (
    get_intersections,
    fetch_intersections_from_api,
    clear_cache,
)
from app.utils.config import API_URL, API_TIMEOUT, API_CACHE_TTL

st.set_page_config(page_title="API Connection Tester", page_icon="🔍", layout="wide")

st.title("🔍 API Connection Tester")
st.markdown("**Real-time verification that Streamlit is calling the backend API**")

st.divider()

# Show configuration
with st.expander("📋 Current Configuration", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.code(f"API_URL:\n{API_URL}", language="text")
        st.code(f"API_TIMEOUT: {API_TIMEOUT} seconds", language="text")
    with col2:
        st.code(
            f"API_CACHE_TTL: {API_CACHE_TTL} seconds ({API_CACHE_TTL//60} minutes)",
            language="text",
        )

st.divider()

# Test buttons
col1, col2, col3 = st.columns(3)

with col1:
    test_direct = st.button(
        "🔵 Test Direct API Call", use_container_width=True, type="primary"
    )

with col2:
    test_cached = st.button("🟢 Test Cached API Call", use_container_width=True)

with col3:
    clear_cache_btn = st.button("🔄 Clear Cache & Retest", use_container_width=True)

st.divider()

# Test 1: Direct API call (bypassing cache)
if test_direct:
    st.subheader("🔵 Direct API Call Test")
    st.info("This makes a fresh API call, bypassing the cache.")

    with st.spinner("Making API call..."):
        start_time = time.time()

        try:
            response = requests.get(API_URL, timeout=API_TIMEOUT)
            elapsed = time.time() - start_time

            st.success(f"✅ **API Call Successful!**")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Status Code", response.status_code)
            with col2:
                st.metric("Response Time", f"{elapsed:.2f}s")
            with col3:
                st.metric("Content Length", f"{len(response.content)} bytes")

            st.markdown("---")

            # Parse response
            try:
                data = response.json()

                # Detect format
                if isinstance(data, list):
                    count = len(data)
                    sample = data[0] if data else None
                elif isinstance(data, dict) and "intersections" in data:
                    count = len(data["intersections"])
                    sample = data["intersections"][0] if data["intersections"] else None
                elif isinstance(data, dict) and "data" in data:
                    count = len(data["data"])
                    sample = data["data"][0] if data["data"] else None
                else:
                    count = 1
                    sample = data

                st.success(f"✅ Received **{count}** intersections from API")

                if sample:
                    st.json(sample)

                    # Validate fields
                    st.markdown("#### Field Validation:")
                    required_fields = [
                        "intersection_id",
                        "intersection_name",
                        "safety_index",
                        "traffic_volume",
                        "latitude",
                        "longitude",
                    ]

                    cols = st.columns(len(required_fields))
                    for idx, field in enumerate(required_fields):
                        with cols[idx]:
                            if field in sample:
                                st.success(f"✅ {field}")
                            else:
                                st.error(f"❌ {field}")

            except Exception as e:
                st.error(f"❌ Failed to parse JSON: {e}")
                st.code(response.text[:500])

        except requests.Timeout:
            elapsed = time.time() - start_time
            st.error(f"❌ **API Call Timed Out** after {elapsed:.2f}s")
            st.warning("The app will fall back to sample data.")

        except requests.ConnectionError:
            st.error(f"❌ **Connection Error** - Cannot reach API")
            st.warning("The app will fall back to sample data.")

        except Exception as e:
            st.error(f"❌ **Error**: {e}")

# Test 2: Cached API call (how the app actually works)
if test_cached:
    st.subheader("🟢 Cached API Call Test (How App Works)")
    st.info("This is exactly how the Streamlit app calls the API (with caching).")

    with st.spinner("Calling API through app service layer..."):
        start_time = time.time()

        # This is what the app actually does
        intersections, error, stats = get_intersections()

        elapsed = time.time() - start_time

        if error:
            st.warning(f"⚠️ **API Error**: {error}")
            st.warning("App is using fallback data from sample.json")
        else:
            st.success(f"✅ **API Call Successful!**")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Response Time", f"{elapsed:.3f}s")
        with col2:
            st.metric("Total Intersections", stats["total_raw"])
        with col3:
            st.metric("Valid Records", stats["valid"])
        with col4:
            st.metric("Invalid Records", stats["invalid"])

        st.markdown("---")

        if intersections:
            st.success(
                f"✅ App received **{len(intersections)}** validated intersections"
            )

            # Show first intersection
            st.markdown("#### First Intersection (after Pydantic validation):")
            st.json(intersections[0].to_dict())

            # Show data quality
            if stats["invalid"] > 0:
                with st.expander("⚠️ Data Quality Issues"):
                    for reason in stats["skipped_reasons"][:5]:
                        st.caption(f"- {reason}")
        else:
            st.error("❌ No valid data received")

# Test 3: Clear cache and retest
if clear_cache_btn:
    st.subheader("🔄 Cache Cleared")
    clear_cache()
    st.success(
        "✅ Cache cleared! Click 'Test Cached API Call' to make a fresh request."
    )
    st.info("Note: The main app cache is also cleared.")

st.divider()

# Show cache status
st.subheader("📊 Cache Information")

cache_info = f"""
- **Cache TTL**: {API_CACHE_TTL} seconds ({API_CACHE_TTL//60} minutes)
- **How it works**:
  1. First API call → Data fetched from backend
  2. Next {API_CACHE_TTL//60} minutes → Data served from memory (no API call)
  3. After {API_CACHE_TTL//60} minutes → Fresh API call made
  4. Click 'Refresh Data' button → Cache cleared, new API call

This means the API is called:
- When you first open the app
- Every {API_CACHE_TTL//60} minutes automatically
- When you click the Refresh button
"""

st.info(cache_info)

st.divider()

# Real-time monitoring section
st.subheader("🔍 How to Verify Live API Calls")

tab1, tab2, tab3 = st.tabs(["Browser DevTools", "Network Monitor", "Command Line"])

with tab1:
    st.markdown(
        """
    ### Using Browser Developer Tools
    
    1. **Open DevTools**: Press `F12` or `Ctrl+Shift+I` (Win) / `Cmd+Option+I` (Mac)
    2. **Go to Network tab**
    3. **Filter by "Fetch/XHR"**
    4. **Refresh the app** or **click a button**
    5. **Look for requests to**: `europe-west1.run.app`
    
    You'll see:
    - Request URL (your backend API)
    - Status code (200 = success)
    - Response time
    - Response data
    """
    )

    st.image(
        "https://via.placeholder.com/800x200/2ECC71/FFFFFF?text=Look+for+requests+to+your+backend+URL+in+Network+tab",
        caption="Network tab will show all API calls",
    )

with tab2:
    st.markdown(
        """
    ### Real-time Network Monitoring
    
    **On macOS/Linux:**
    ```bash
    # Monitor all network connections
    sudo tcpdump -i any host europe-west1.run.app
    
    # Or use lsof to see active connections
    lsof -i | grep python
    ```
    
    **On Windows:**
    ```powershell
    # Use Resource Monitor
    resmon.exe
    # Go to Network tab, filter by python.exe
    ```
    """
    )

with tab3:
    st.markdown(
        f"""
    ### Test API from Command Line
    
    **Quick test:**
    ```bash
    curl "{API_URL}"
    ```
    
    **With timing:**
    ```bash
    curl -w "\\nTime: %{{time_total}}s\\n" "{API_URL}"
    ```
    
    **Pretty JSON:**
    ```bash
    curl "{API_URL}" | python -m json.tool
    ```
    
    **Watch for changes:**
    ```bash
    watch -n 5 'curl -s "{API_URL}" | head -20'
    ```
    """
    )

st.divider()

# Footer with instructions
st.markdown(
    """
---
### 💡 Key Indicators the App is Using Live API:

✅ **Fast response** (< 1 second) = Using cache  
✅ **Slower first load** (1-3 seconds) = Fresh API call  
✅ **No warning banner** = API working  
✅ **Real intersection names** (not "Sample Intersection (Offline)")  
✅ **More than 10 intersections** = Live data (sample.json has exactly 10)  

⚠️ **Warning banner** = API failed, using fallback  
⚠️ **"(Offline)" in names** = Using sample data  

---
**Current time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
)
