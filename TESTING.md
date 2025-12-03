# Camera Integration - Automated Testing

**One-command testing** - No manual steps required! ⚡

---

## Quick Start

### Windows (PowerShell)

```powershell
# Run from project root
.\test-camera-integration.ps1
```

The script will prompt you for `DATABASE_URL` and handle everything else automatically.

### Linux/Mac

```bash
# Make executable (first time only)
chmod +x test-camera-integration.sh

# Run
./test-camera-integration.sh
```

---

## What It Does

The automated test suite:

1. ✅ **Validates environment** - Checks Python 3.11+, PostgreSQL client
2. ✅ **Tests database connection** - Verifies DATABASE_URL works
3. ✅ **Applies migration** - Runs 03_add_camera_urls.sql (if needed)
4. ✅ **Installs dependencies** - pip install requirements
5. ✅ **Runs 40+ tests** - Comprehensive validation of all components
6. ✅ **Generates report** - Colored pass/fail summary

**Total Time:** ~60 seconds

---

## Test Coverage

The automated test suite validates:

### Test Suite 1: Environment Setup
- DATABASE_URL configuration
- VDOT_API_KEY (optional)
- Python version >= 3.11

### Test Suite 2: Database Migration
- Database connection
- `camera_urls` column exists
- Validation functions installed

### Test Suite 3: Admin Script
- List intersections
- Add camera
- Clear camera
- Verify database updates

### Test Suite 4: Schema Validation
- CameraLink Pydantic schema
- URL validation (accepts https://, rejects ftp://)
- IntersectionRead with camera_urls

### Test Suite 5: VDOT Camera Service
- Service import
- Haversine distance calculation (~165 miles Richmond to Blacksburg)
- Fallback 511 map link generation
- Camera search with radius

### Test Suite 6: Backend API
- Start uvicorn server
- GET /api/v1/safety/index/
- Verify camera_urls field in response
- Test specific intersection endpoint

### Test Suite 7: Database Queries
- validate_camera_url_structure() function
- Coverage statistics query
- Invalid data rejection

---

## Sample Output

```
================================================================
Camera Integration - Automated Test Suite
================================================================

================================================================
Test Suite 1: Environment Setup
================================================================

▶ DATABASE_URL is set... ✓ PASS (Set to postgresql://user@localhost...)
▶ VDOT_API_KEY is set... ⚠ WARNING: Not set - will use fallback
▶ Python version >= 3.11... ✓ PASS (Python 3.11.5)

================================================================
Test Suite 2: Database Migration
================================================================

▶ Database connection... ✓ PASS (Connected successfully)
▶ camera_urls column exists... ✓ PASS (Column exists)
▶ validate_camera_url_structure function exists... ✓ PASS (Function exists)

... (more test suites)

================================================================
Test Summary
================================================================

Time: 58.3s
Passed: 38
Failed: 0
Success Rate: 100.0%

✓ All tests passed!
```

---

## Advanced Usage

### With Environment Variables

**Windows:**
```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost/db"
$env:VDOT_API_KEY = "your-key-here"
.\test-camera-integration.ps1
```

**Linux/Mac:**
```bash
export DATABASE_URL="postgresql://user:pass@localhost/db"
export VDOT_API_KEY="your-key-here"
./test-camera-integration.sh
```

### Direct Python Execution

```bash
cd backend

# Set environment
export DATABASE_URL="postgresql://..."

# Run tests directly
python test_camera_integration.py
```

---

## Troubleshooting

### "psql: command not found"

**Windows:**
- Install PostgreSQL from https://www.postgresql.org/download/windows/
- Or install just the client: `choco install postgresql-client`

**Linux:**
```bash
sudo apt-get install postgresql-client  # Debian/Ubuntu
sudo yum install postgresql              # RHEL/CentOS
```

**Mac:**
```bash
brew install postgresql
```

### "Python 3.11+ required"

**Windows:**
- Download from https://www.python.org/downloads/
- Or: `winget install Python.Python.3.11`

**Linux/Mac:**
```bash
# Use pyenv
pyenv install 3.11.5
pyenv global 3.11.5
```

### Tests fail with "cannot connect to database"

1. Verify PostgreSQL is running:
   ```bash
   psql $DATABASE_URL -c "SELECT 1;"
   ```

2. Check DATABASE_URL format:
   ```
   postgresql://username:password@host:port/database
   ```

3. Example valid URLs:
   ```
   postgresql://postgres:mypass@localhost:5432/trafficsafety
   postgresql://user@localhost/mydb
   postgresql://user:pass@127.0.0.1/db
   ```

### Backend server fails to start (port 8000 in use)

Kill the existing process:

**Windows:**
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

**Linux/Mac:**
```bash
lsof -ti:8000 | xargs kill
```

---

## Manual Testing (Alternative)

If you prefer manual testing, see: **[docs/camera-integration-local-testing.md](docs/camera-integration-local-testing.md)**

Step-by-step guide with 10 detailed test procedures.

---

## Frontend Testing

The automated tests cover backend only. For frontend testing:

```bash
cd frontend
streamlit run pages/0_🏠_Dashboard.py
```

Then manually verify:
- ✅ Click intersection marker
- ✅ Camera section appears in popup
- ✅ Camera buttons work in details card
- ✅ Links open in new tab

---

## Continuous Integration

### GitHub Actions

```yaml
name: Camera Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Run camera integration tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost/postgres
        run: |
          chmod +x test-camera-integration.sh
          ./test-camera-integration.sh
```

---

## Test Development

To add new tests, edit `backend/test_camera_integration.py`:

```python
def test_my_feature(self):
    """Test my new feature"""
    self.print_header("Test Suite X: My Feature")

    self.print_test("My test case")
    try:
        # Your test logic
        result = my_function()
        if result == expected:
            self.print_pass("Test passed")
        else:
            self.print_fail(f"Expected {expected}, got {result}")
    except Exception as e:
        self.print_fail(f"Test failed: {e}")
```

Then add to `run_all_tests()`:
```python
self.test_my_feature()
```

---

## Related Documentation

- **[camera-integration-local-testing.md](docs/camera-integration-local-testing.md)** - Manual testing guide
- **[camera-management.md](docs/camera-management.md)** - Admin tools guide
- **[camera-auto-initialization-guide.md](docs/camera-auto-initialization-guide.md)** - Production deployment
- **[README.camera-refresh-gcp.md](backend/README.camera-refresh-gcp.md)** - GCP deployment

---

**Last Updated:** 2025-12-03
**Version:** 1.0
