# Quick Start: Testing VCC API Integration

## 🚀 Fastest Path to Testing

### Step 1: Configure Environment (30 seconds)

```bash
# Copy example environment file
cp backend/.env.example backend/.env

# Edit .env and add your VCC credentials:
# VCC_CLIENT_ID=your_client_id_here
# VCC_CLIENT_SECRET=your_client_secret_here
# DATA_SOURCE=vcc
```

### Step 2: Test Locally (Recommended First)

```bash
# Install dependencies (if not done)
cd backend
pip install -r requirements.txt

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, run tests
python backend/test_vcc_api.py
```

### Step 3: Test with Docker

```bash
cd backend
docker-compose up --build

# In another terminal
python backend/test_vcc_api.py
```

## ✅ Quick Verification

### 1. Health Check
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

### 2. VCC Status
```bash
curl http://localhost:8000/api/v1/vcc/status
# Expected: JSON with connection status
```

### 3. Test Connection
```bash
curl http://localhost:8000/api/v1/vcc/test/connection
# Expected: {"status":"success","authenticated":true}
```

## 📋 What Gets Tested

The `test_vcc_api.py` script automatically tests:
- ✓ VCC API connection and authentication
- ✓ MapData retrieval
- ✓ Historical data collection (starts background job)
- ✓ Real-time streaming status

## 🐛 Common Issues

### "Failed to obtain access token"
- Check `VCC_CLIENT_ID` and `VCC_CLIENT_SECRET` in `.env`
- Verify credentials are correct

### "Connection failed"
- Check if server is running: `curl http://localhost:8000/health`
- Verify network can reach `https://vcc.vtti.vt.edu`

### "No data available"
- This is normal if VCC API doesn't have active data
- Test with `data/vcc-api-exploration.ipynb` first

## 📚 More Details

See `backend/TESTING_VCC.md` for comprehensive testing guide.

