# Traffic Safety Index Dashboard 🚦

A production-ready Streamlit web application for visualizing traffic intersection safety data with interactive maps and real-time filtering.

## Features

- 🗺️ **Interactive Map**: Folium-powered map with click-to-view details
- 📊 **Visual Encoding**:
  - Marker size scales with traffic volume
  - Marker color indicates safety risk (green → orange → red)
- 🔍 **Advanced Filtering**: Filter by name, safety index, and traffic volume
- 📈 **KPI Dashboard**: Real-time metrics and statistics
- 💾 **Data Export**: Download filtered data as CSV
- 🔄 **Smart Caching**: API responses cached for 5 minutes
- 🛡️ **Error Handling**: Automatic fallback to sample data if API fails
- ✅ **Data Validation**: Pydantic models ensure data integrity

## Architecture

This application follows **MVC (Model-View-Controller)** pattern for maintainability:

```
frontend/
├── app/
│   ├── models/           # Pydantic data models
│   │   └── intersection.py
│   ├── services/         # API client with caching
│   │   └── api_client.py
│   ├── controllers/      # Map building logic
│   │   └── map_controller.py
│   ├── views/            # Streamlit UI components
│   │   ├── main.py       # App entrypoint
│   │   └── components.py # Reusable widgets
│   ├── utils/            # Helper functions
│   │   ├── config.py     # Configuration constants
│   │   └── scaling.py    # Visual encoding logic
│   └── data/             # Sample/fallback data
│       └── sample.json
├── .streamlit/           # Streamlit configuration
│   └── config.toml
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Quick Start

### Prerequisites

- Python 3.9 or higher
- **UV** (recommended - ultra-fast package manager) OR pip
  - Install UV: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Or use pip (slower but works)

### Installation

1. **Clone the repository** (if not already done):

   ```bash
   cd frontend
   ```

2. **Install UV** (optional but recommended for speed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or: brew install uv
   # or: pip install uv
   ```

3. **Create a virtual environment**:

   **With UV (fast):**

   ```bash
   uv venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   ```

   **With traditional Python:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   ```

4. **Install dependencies**:

   **With UV (10-100x faster ⚡):**

   ```bash
   uv pip install -r requirements.txt
   ```

   **With pip:**

   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

**Option 1: Using UV (Recommended - 10-100x faster! ⚡)**

```bash
./start-uv.sh
```

**Option 2: Using UV with uvx (no setup needed)**

```bash
uvx --from streamlit streamlit run app/views/main.py
```

**Option 3: Traditional method with pip**

```bash
streamlit run app/views/main.py
```

The application will open in your default browser at `http://localhost:8501`.

**Note**: If you don't have UV installed yet, see [UV_GUIDE.md](UV_GUIDE.md) for installation instructions. UV is much faster than pip!

### Alternative: Run from Project Root

If running from the project root directory:

```bash
cd frontend
./start-uv.sh  # with UV
# or
streamlit run app/views/main.py  # traditional
```

## Usage Guide

### Main Interface

1. **Map View** (Left Panel):

   - Hover over markers to see intersection names
   - Click markers to view detailed information
   - Larger circles = higher traffic volume
   - Color indicates risk: 🟢 Green (safe) → 🟠 Orange → 🔴 Red (dangerous)

2. **Details Panel** (Right Panel):

   - Displays metrics for the selected intersection
   - Shows risk level with color-coded badge
   - Includes traffic volume, coordinates, and ID

3. **Filters** (Sidebar):

   - **Search**: Find intersections by name
   - **Safety Index Range**: Filter by risk level (0-100)
   - **Traffic Volume Range**: Filter by traffic volume
   - **Refresh**: Force reload data from API

4. **Data Table** (Bottom):
   - Sortable table of all filtered intersections
   - Default sort: highest safety index (most dangerous) first
   - Download CSV button for data export

### Understanding the Data

- **Safety Index**: 0-100 scale where **higher = more dangerous**
  - < 60: Low risk (green)
  - 60-75: Medium risk (orange)
  - \> 75: High risk (red)
- **Traffic Volume**: Relative traffic count for the intersection

## Configuration

### API Settings

Edit `app/utils/config.py` to customize:

```python
# API Configuration
API_URL = "https://your-api-endpoint.com/api/v1/safety/index/"
API_TIMEOUT = 10  # seconds
API_CACHE_TTL = 300  # 5 minutes

# Map Configuration
DEFAULT_CENTER = (38.86, -77.055)  # Default map center
DEFAULT_ZOOM = 13

# Visual Encoding
MIN_RADIUS_PX = 6
MAX_RADIUS_PX = 30
COLOR_LOW_THRESHOLD = 60
COLOR_HIGH_THRESHOLD = 75
```

### Using Secrets (Production)

For production deployments, use Streamlit secrets:

1. Create `.streamlit/secrets.toml`:

   ```toml
   API_URL = "https://your-production-api.com/api/v1/safety/index/"
   ```

2. Update `config.py`:
   ```python
   import streamlit as st
   API_URL = st.secrets.get("API_URL", "default-url")
   ```

### Theme Customization

Edit `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#E74C3C"      # Red accent
backgroundColor = "#FFFFFF"    # White background
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## Deployment

### Streamlit Community Cloud

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Set main file path: `frontend/app/views/main.py`
5. Add secrets in the Streamlit Cloud dashboard if needed

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app/views/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:

```bash
docker build -t traffic-safety-dashboard .
docker run -p 8501:8501 traffic-safety-dashboard
```

### Other Hosting Options

- **Heroku**: Use Streamlit's Heroku buildpack
- **AWS/GCP/Azure**: Deploy as containerized app
- **Self-hosted**: Run with systemd or supervisor

## Development

### Project Structure

- **Models** (`app/models/`): Pydantic schemas for data validation
- **Services** (`app/services/`): API integration with retry logic
- **Controllers** (`app/controllers/`): Business logic (map building)
- **Views** (`app/views/`): UI components and layouts
- **Utils** (`app/utils/`): Helper functions and configuration

### Adding New Features

1. **New Filter**: Add to `components.py` → `render_filters()` and `apply_filters()`
2. **New Visualization**: Extend `map_controller.py` → `build_map()`
3. **New Data Source**: Modify `api_client.py` → `fetch_intersections_from_api()`
4. **New UI Component**: Add to `components.py` and import in `main.py`

### Testing

Create unit tests in `app/tests/`:

```python
# tests/test_scaling.py
from app.utils.scaling import scale_radius, get_color_for_safety_index

def test_scale_radius():
    assert scale_radius(50, 0, 100) == 18.0  # Mid-range

def test_color_mapping():
    assert get_color_for_safety_index(45) == "#2ECC71"  # Green
    assert get_color_for_safety_index(80) == "#E74C3C"  # Red
```

Run with pytest:

```bash
pip install pytest
pytest app/tests/
```

## API Integration

### Expected API Response Format

The application expects JSON in one of these formats:

**Option 1: Array of objects**

```json
[
  {
    "intersection_id": 1,
    "intersection_name": "Main St & 1st Ave",
    "safety_index": 45.2,
    "traffic_volume": 15000,
    "latitude": 38.8951,
    "longitude": -77.0364
  }
]
```

**Option 2: Object with "intersections" key**

```json
{
  "intersections": [...]
}
```

**Option 3: Object with "data" key**

```json
{
  "data": [...]
}
```

### Field Specifications

- `intersection_id`: Integer, unique identifier
- `intersection_name`: String, display name
- `safety_index`: Float, 0-100 (validated/clamped)
- `traffic_volume`: Float/Integer, >= 0
- `latitude`: Float, -90 to 90
- `longitude`: Float, -180 to 180

## Troubleshooting

### Common Issues

**Problem**: "Import could not be resolved" errors in IDE

- **Solution**: Install dependencies: `pip install -r requirements.txt`
- These are linting warnings and don't affect runtime

**Problem**: API timeout or connection error

- **Solution**: The app automatically falls back to sample data
- Check API_URL in `config.py`
- Increase API_TIMEOUT if needed

**Problem**: Map not displaying

- **Solution**: Check browser console for errors
- Ensure `streamlit-folium` is installed
- Clear browser cache

**Problem**: Empty map / no markers

- **Solution**: Check that data has valid lat/lon values
- Verify filters aren't too restrictive
- Check data loading stats in sidebar

### Performance Optimization

For large datasets (>1000 intersections):

1. **Enable clustering**:

   ```python
   from folium.plugins import MarkerCluster
   marker_cluster = MarkerCluster().add_to(m)
   # Add markers to marker_cluster instead of m
   ```

2. **Add server-side filtering** to your API with query parameters

3. **Reduce cache TTL** if data changes frequently

4. **Use pagination** in the data table

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is part of the CS6604 Traffic Safety research initiative.

## Support

For issues, questions, or contributions:

- Open an issue on GitHub
- Contact the development team
- Check the API documentation

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Maps powered by [Folium](https://python-visualization.github.io/folium/)
- Data validation by [Pydantic](https://docs.pydantic.dev/)
- API integration with [Requests](https://requests.readthedocs.io/)

---

**Version**: 1.0.0  
**Last Updated**: October 2025
