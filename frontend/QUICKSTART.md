# Quick Reference Guide

## 🚀 Running the Application

### Option 1: Using UV Quick Start (Recommended - FASTEST ⚡)

```bash
cd frontend
./start-uv.sh
```

### Option 2: Using uvx (no setup needed)

```bash
cd frontend
uvx --from streamlit streamlit run app/views/main.py
```

### Option 3: Traditional Quick Start Script

```bash
cd frontend
./start.sh
```

### Option 4: Manual Start with UV

```bash
cd frontend
uv venv
source .venv/bin/activate  # On macOS/Linux
uv pip install -r requirements.txt
streamlit run app/views/main.py
```

### Option 5: Manual Start with pip

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt
streamlit run app/views/main.py
```

### Option 6: Direct Run (if dependencies installed)

```bash
cd frontend
streamlit run app/views/main.py
```

**💡 Tip**: UV is 10-100x faster than pip! Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 📁 Key Files

| File                                | Purpose                      |
| ----------------------------------- | ---------------------------- |
| `app/views/main.py`                 | Main application entry point |
| `app/models/intersection.py`        | Data validation schemas      |
| `app/services/api_client.py`        | API integration with caching |
| `app/controllers/map_controller.py` | Map building logic           |
| `app/utils/config.py`               | Configuration settings       |
| `app/data/sample.json`              | Fallback data                |
| `requirements.txt`                  | Python dependencies          |

## ⚙️ Configuration

### Change API URL

Edit `app/utils/config.py`:

```python
API_URL = "https://your-api-endpoint.com/..."
```

### Adjust Visual Encoding

Edit `app/utils/config.py`:

```python
# Marker size range
MIN_RADIUS_PX = 6
MAX_RADIUS_PX = 30

# Color thresholds
COLOR_LOW_THRESHOLD = 60   # Below: green
COLOR_HIGH_THRESHOLD = 75  # Above: red
```

### Modify Cache Duration

Edit `app/utils/config.py`:

```python
API_CACHE_TTL = 300  # seconds (5 minutes)
```

## 🎨 Color Scheme

- **Green** (#2ECC71): Low risk (Safety Index < 60)
- **Orange** (#F39C12): Medium risk (Safety Index 60-75)
- **Red** (#E74C3C): High risk (Safety Index > 75)

## 🐛 Common Issues

### Import Errors

```bash
pip install -r requirements.txt
```

### Port Already in Use

```bash
streamlit run app/views/main.py --server.port 8502
```

### API Not Accessible

The app will automatically use sample data from `app/data/sample.json`

## 📊 Data Format

Required fields for each intersection:

```json
{
  "intersection_id": 1,
  "intersection_name": "Main St & 1st Ave",
  "safety_index": 45.2,
  "traffic_volume": 15000,
  "latitude": 38.8951,
  "longitude": -77.0364
}
```

## 🔧 Development

### Project Structure

```
frontend/
├── app/
│   ├── models/          # Data schemas (Pydantic)
│   ├── services/        # API client
│   ├── controllers/     # Business logic
│   ├── views/           # UI components
│   ├── utils/           # Helpers & config
│   └── data/            # Sample data
├── .streamlit/          # Streamlit config
└── requirements.txt     # Dependencies
```

### Adding a New Feature

1. **Model**: Add/modify `app/models/intersection.py`
2. **Service**: Update `app/services/api_client.py`
3. **Controller**: Extend `app/controllers/map_controller.py`
4. **View**: Add component to `app/views/components.py`
5. **Main**: Integrate in `app/views/main.py`

## 📝 Environment Variables

Create `.streamlit/secrets.toml` for sensitive data:

```toml
API_URL = "https://production-api.com/..."
API_KEY = "your-secret-key"
```

Access in code:

```python
import streamlit as st
api_url = st.secrets["API_URL"]
```

## 🚢 Deployment

### Streamlit Cloud

1. Push to GitHub
2. Go to share.streamlit.io
3. Connect repository
4. Set main file: `frontend/app/views/main.py`

### Docker

```bash
docker build -t traffic-safety-dashboard .
docker run -p 8501:8501 traffic-safety-dashboard
```

## 📞 Support

- **Documentation**: See README.md
- **Issues**: Open a GitHub issue
- **API Docs**: Check your API endpoint documentation

---

**Quick Commands**

| Command                                                | Purpose                     |
| ------------------------------------------------------ | --------------------------- |
| `./start-uv.sh`                                        | Launch with UV (fastest ⚡) |
| `./start.sh`                                           | Launch with pip             |
| `uvx --from streamlit streamlit run app/views/main.py` | Run without setup           |
| `streamlit run app/views/main.py`                      | Run manually                |
| `uv pip install -r requirements.txt`                   | Install deps (UV - fast)    |
| `pip install -r requirements.txt`                      | Install deps (pip - slower) |
| `streamlit cache clear`                                | Clear all caches            |

**Default URL**: http://localhost:8501

**UV Installation**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
