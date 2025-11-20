# VCC API Exploration Notebook

This directory contains a Jupyter notebook for exploring the Virginia Connected Corridor (VCC) Public API.

## Setup

### 1. Install Dependencies

#### Option A: Install all project dependencies
```bash
pip install -r ../requirements.txt
```

#### Option B: Install minimal dependencies for just this notebook
```bash
pip install -r notebook-requirements.txt
```

#### Option C: Install with conda
```bash
conda create -n vcc-api python=3.8
conda activate vcc-api
pip install -r notebook-requirements.txt
```

### 2. Configure API Credentials

Before running the notebook, you'll need to obtain VCC API credentials:

1. Contact the VCC project team to get your `client_id` and `client_secret`
2. Open [vcc-api-exploration.ipynb](vcc-api-exploration.ipynb)
3. Replace the placeholder values in the authentication section:
   ```python
   CLIENT_ID = 'your_client_id'
   CLIENT_SECRET = 'your_client_secret'
   ```

**Security Note**: Never commit your credentials to version control! Consider using environment variables or a `.env` file.

### 3. Launch Jupyter Notebook

```bash
jupyter notebook vcc-api-exploration.ipynb
```

Or use JupyterLab:
```bash
jupyter lab
```

## Notebook Contents

The notebook covers:

- **Authentication**: JWT token management
- **MapData API**: Intersection geometry and lane data
- **SPAT API**: Signal phase and timing information
- **BSM API**: Basic Safety Messages (vehicle data)
- **PSM API**: Personal Safety Messages (vulnerable road users)
- **Visualizations**: Maps, plots, and data analysis
- **WebSocket Streaming**: Real-time data collection

## API Documentation

Full API documentation is available in:
- [../files/VCC_Public_API_v3.1.pdf](../files/VCC_Public_API_v3.1.pdf)

## Quick Start Example

```python
import requests

# Authentication
BASE_URL = "https://vcc.vtti.vt.edu"
TOKEN_URL = f"{BASE_URL}/api/auth/client"

data = {
    'client_id': 'your_client_id',
    'client_secret': 'your_client_secret'
}

response = requests.post(TOKEN_URL, data=data)
access_token = response.json()['access_token']
headers = {'Authorization': f'Bearer {access_token}'}

# Get MapData
response = requests.get(f"{BASE_URL}/api/mapdata/decoded", headers=headers)
mapdata = response.json()
print(f"Found {len(mapdata)} intersections")
```

## Troubleshooting

### Import Errors
If you get import errors, ensure all dependencies are installed:
```bash
pip install --upgrade -r notebook-requirements.txt
```

### Authentication Errors (401 Unauthorized)
- Verify your `client_id` and `client_secret` are correct
- Check if your JWT token has expired (tokens expire after 1 hour)
- Re-run the authentication cell to get a new token

### WebSocket Connection Issues
- Ensure you're getting a fresh WebSocket key before each connection
- WebSocket keys are single-use and expire quickly
- Check your network firewall settings

## Data Files

If you collect data using the notebook, it's recommended to save it in this directory:

```python
# Example: Save BSM data to CSV
df_bsm.to_csv('bsm_data.csv', index=False)
```

Add `*.csv` to `.gitignore` to avoid committing large data files.

## Resources

- **VCC Website**: https://vcc.vtti.vt.edu
- **SAE J2735 Standard**: https://www.sae.org/standards/content/j2735_201603/
- **ASN.1 Decoder**: https://www.marben-products.com/decoder-asn1-automotive

## Contributing

When adding new features to the notebook:
1. Document your code with clear markdown cells
2. Include example outputs where helpful
3. Update this README if adding new dependencies
4. Test with fresh credentials to ensure it works for new users
