# Quick Test: Does the App Really Call the API?

## TL;DR - Run These Commands

```bash
cd frontend

# Method 1: Run the API tester app (BEST)
streamlit run test_app_api.py

# Method 2: Test API directly with curl
curl -w "\nTime: %{time_total}s\n" \
  https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/

# Method 3: Run main app and watch browser Network tab
streamlit run app/views/main.py
# Then open browser DevTools (F12) → Network tab → Filter: XHR
```

---

## Method 1: Interactive Tester (RECOMMENDED) ⭐

This runs a special test page that shows you exactly what's happening:

```bash
cd frontend
streamlit run test_app_api.py
```

**What you'll see:**

- 🔵 **Direct API Call** - Makes fresh request to backend
- 🟢 **Cached API Call** - Shows exactly how the app works
- 🔄 **Clear Cache** - Test cache behavior
- Real-time results, timing, and data validation

**Buttons to click:**

1. Click "🔵 Test Direct API Call" - See raw API response
2. Click "🟢 Test Cached API Call" - See how app uses the API
3. Click "🔄 Clear Cache & Retest" - Verify caching works

---

## Method 2: Browser DevTools (VISUAL PROOF) 👀

See the actual network requests in real-time:

### Steps:

1. **Start the app:**

   ```bash
   cd frontend
   streamlit run app/views/main.py
   ```

2. **Open browser** to http://localhost:8501

3. **Open DevTools:**

   - Press `F12`
   - Or Right-click → "Inspect"
   - Or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)

4. **Go to Network tab**

5. **Filter by "Fetch/XHR"**

6. **Refresh the page** (Cmd+R or Ctrl+R)

7. **Look for:**

   ```
   Name: index/
   Status: 200
   Type: xhr
   Domain: europe-west1.run.app
   ```

8. **Click on the request to see:**
   - Request Headers
   - Response Headers
   - Response body (your data!)
   - Timing details

### What You'll See:

**If API is working:**

```
Request URL: https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/
Request Method: GET
Status Code: 200 OK
Response Time: 450ms
```

**If using cached data:**

- You won't see a new request (data served from memory)
- Click "Refresh Data" button in the app to force a new API call

---

## Method 3: Terminal Watch (LIVE MONITORING) 📡

Monitor network activity in real-time:

### Option A: Watch with curl

```bash
# In one terminal, run this to monitor API
watch -n 2 'curl -s -w "\nTime: %{time_total}s Status: %{http_code}\n" \
  https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/ \
  -o /dev/null'

# In another terminal, run the app
cd frontend
streamlit run app/views/main.py
```

### Option B: Network monitoring (advanced)

```bash
# macOS/Linux - Monitor connections to backend
sudo tcpdump -i any -n host cs6604-trafficsafety-180117512369.europe-west1.run.app

# Then run app in another terminal
cd frontend
streamlit run app/views/main.py
```

You'll see packets when the app calls the API!

---

## Method 4: Add Debug Logging to the App

Temporarily add logging to see API calls:

### Quick Edit:

Open `frontend/legacy-streamlit/app/services/api_client.py` and add at line 87:

```python
@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def fetch_intersections_from_api() -> tuple[List[dict], Optional[str]]:
    """Fetch intersection data from the API with caching."""

    # ADD THESE LINES ↓↓↓
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.info(f"🔵 API CALL: {API_URL}")
    logging.info(f"🕐 Time: {datetime.now()}")
    # END ADD ↑↑↑

    try:
        session = _get_session_with_retries()
        response = session.get(API_URL, timeout=API_TIMEOUT)

        # ADD THIS LINE ↓↓↓
        logging.info(f"✅ Response: {response.status_code} in {response.elapsed.total_seconds():.2f}s")
        # END ADD ↑↑↑

        response.raise_for_status()
        # ... rest of code
```

Then run the app and **watch the terminal** for log messages!

---

## Method 5: Check App UI Indicators

The app shows you visually if it's using the API:

### ✅ API IS WORKING if you see:

- No warning banner at top
- Real intersection names (e.g., "Main St & 1st Ave")
- Multiple intersections (more than 10)
- "Refresh Data" button works
- Data changes when you click refresh

### ⚠️ API FAILED if you see:

- Yellow warning banner: "⚠️ Using fallback data: [error]"
- Intersection names with "(Offline)"
- Exactly 10 intersections (sample data)
- Names like "Sample Intersection (Offline)"

---

## Quick Tests Comparison

| Method   | Speed          | Detail     | Best For               |
| -------- | -------------- | ---------- | ---------------------- |
| Test App | ⚡ Fast        | 🌟🌟🌟🌟🌟 | **Quick verification** |
| DevTools | ⚡ Fast        | 🌟🌟🌟🌟   | **Visual proof**       |
| curl     | ⚡⚡ Instant   | 🌟🌟🌟     | **Command line**       |
| tcpdump  | ⚡⚡ Real-time | 🌟🌟       | **Advanced users**     |
| Logging  | ⚡ Fast        | 🌟🌟🌟🌟   | **Development**        |

---

## Expected Results

### When App Calls API Successfully:

```
✅ Status: 200 OK
✅ Response time: 0.5-2.0 seconds (first call)
✅ Response time: <0.1 seconds (cached calls)
✅ Data: JSON array with intersection objects
✅ Count: Multiple intersections (10+)
```

### When App Uses Cache:

```
✅ No network request visible in DevTools
✅ Response time: ~0.05 seconds
✅ Data: Same as previous call
✅ No API call for 5 minutes
```

### When API Fails:

```
⚠️ Warning banner in app
⚠️ Using data from: app/data/sample.json
⚠️ Exactly 10 intersections
⚠️ Intersection names include "(Offline)"
```

---

## Proof the App Uses Your API

Run this complete test sequence:

```bash
# 1. Test API is reachable
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/ | head -20

# 2. Start the test app
cd frontend
streamlit run test_app_api.py

# 3. In the browser, click all three buttons:
#    - Test Direct API Call
#    - Test Cached API Call
#    - Clear Cache & Retest

# 4. Open main app
streamlit run app/views/main.py

# 5. Open DevTools (F12), go to Network tab
# 6. Refresh page, look for request to europe-west1.run.app
# 7. Click the request to see response data
```

---

## Troubleshooting

### "I don't see any API calls in DevTools"

**Reason**: Data is being served from cache!

**Solution**: Click "🔄 Refresh Data" button in the sidebar to force a fresh API call.

### "I see a warning banner"

**Reason**: API call failed, using fallback data.

**Check**:

1. Is backend deployed? Visit URL in browser
2. Is URL correct in `app/utils/config.py`?
3. Try: `curl [API_URL]` to test directly

### "Response is too fast (< 100ms)"

**Reason**: That's the cache working! Caching is GOOD.

**To verify**: Click "Refresh Data" button to make a new API call (will be slower ~1-2s).

---

## Final Verification Checklist

✅ Run test app: `streamlit run test_app_api.py`  
✅ Click "Test Direct API Call" → See 200 status  
✅ Click "Test Cached API Call" → See valid data  
✅ Open DevTools → See network request  
✅ Check for intersection names (not "Offline")  
✅ Verify count > 10 intersections  
✅ Click Refresh button → See new request in DevTools

**If all pass** → ✅ Your app IS calling the backend API! 🎉

---

## Quick Command Reference

```bash
# Test API directly
curl https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1/safety/index/

# Run test app
streamlit run test_app_api.py

# Run main app
streamlit run app/views/main.py

# Watch API calls
watch -n 2 'curl -s -w "\nStatus: %{http_code}\n" [API_URL] -o /dev/null'
```

**Need more help?** See [API_TESTING.md](API_TESTING.md) for detailed documentation.
