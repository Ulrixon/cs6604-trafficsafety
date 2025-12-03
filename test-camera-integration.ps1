# Camera Integration - Automated Test Script (Windows PowerShell)
#
# This script automates the entire testing process:
# 1. Sets up environment variables
# 2. Applies database migration
# 3. Runs automated test suite
#
# Usage:
#   .\test-camera-integration.ps1
#
# Or with custom database URL:
#   .\test-camera-integration.ps1 -DatabaseUrl "postgresql://user:pass@host/db"

param(
    [string]$DatabaseUrl = "",
    [string]$VdotApiKey = ""
)

# Colors
$Red = "`e[31m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Cyan = "`e[36m"
$Reset = "`e[0m"

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "$Cyan================================================================$Reset"
    Write-Host "$Cyan$Text$Reset"
    Write-Host "$Cyan================================================================$Reset"
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "$Yellow▶ $Text...$Reset" -NoNewline
}

function Write-Success {
    param([string]$Text = "")
    if ($Text) {
        Write-Host " $Green✓ $Text$Reset"
    } else {
        Write-Host " $Green✓$Reset"
    }
}

function Write-Error {
    param([string]$Text)
    Write-Host " $Red✗ $Text$Reset"
}

function Write-Info {
    param([string]$Text)
    Write-Host "$Cyan$Text$Reset"
}

# Start
Write-Header "Camera Integration - Automated Test Setup"

# Step 1: Check prerequisites
Write-Header "Step 1: Checking Prerequisites"

Write-Step "Python 3.11+"
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.1[1-9]") {
        Write-Success $pythonVersion
    } else {
        Write-Error "Python 3.11+ required. Found: $pythonVersion"
        exit 1
    }
} catch {
    Write-Error "Python not found. Install Python 3.11+"
    exit 1
}

Write-Step "PostgreSQL client (psql)"
try {
    $psqlVersion = psql --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Found"
    } else {
        Write-Error "psql not found. Install PostgreSQL client"
        exit 1
    }
} catch {
    Write-Error "psql not found. Install PostgreSQL client"
    exit 1
}

# Step 2: Set environment variables
Write-Header "Step 2: Environment Configuration"

if (-not $DatabaseUrl) {
    Write-Info "Enter your DATABASE_URL:"
    Write-Info "Format: postgresql://username:password@host:port/database"
    $DatabaseUrl = Read-Host "DATABASE_URL"
}

$env:DATABASE_URL = $DatabaseUrl
Write-Success "DATABASE_URL set"

if ($VdotApiKey) {
    $env:VDOT_API_KEY = $VdotApiKey
    Write-Success "VDOT_API_KEY set"
} else {
    Write-Info "VDOT_API_KEY not provided - will use fallback (511 map links)"
}

# Step 3: Test database connection
Write-Header "Step 3: Database Connection Test"

Write-Step "Testing connection"
try {
    $result = psql $env:DATABASE_URL -c "SELECT version();" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Connected successfully"
    } else {
        Write-Error "Connection failed: $result"
        exit 1
    }
} catch {
    Write-Error "Connection failed: $_"
    exit 1
}

# Step 4: Apply database migration
Write-Header "Step 4: Database Migration"

Write-Step "Checking if camera_urls column exists"
$columnCheck = psql $env:DATABASE_URL -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='intersections' AND column_name='camera_urls';" 2>&1

if ($columnCheck -match "camera_urls") {
    Write-Success "Migration already applied"
} else {
    Write-Step "Applying migration (03_add_camera_urls.sql)"
    try {
        psql $env:DATABASE_URL -f backend/db/init/03_add_camera_urls.sql 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Migration applied"
        } else {
            Write-Error "Migration failed"
            exit 1
        }
    } catch {
        Write-Error "Migration failed: $_"
        exit 1
    }
}

# Step 5: Install Python dependencies
Write-Header "Step 5: Installing Dependencies"

Write-Step "Installing backend requirements"
cd backend
try {
    pip install -r requirements.txt --quiet 2>&1 | Out-Null
    Write-Success "Dependencies installed"
} catch {
    Write-Error "Failed to install dependencies: $_"
    exit 1
}

# Step 6: Install test dependencies
Write-Step "Installing test dependencies"
try {
    pip install colorama requests --quiet 2>&1 | Out-Null
    Write-Success "Test dependencies installed"
} catch {
    Write-Error "Failed to install test dependencies: $_"
}

# Step 7: Run automated tests
Write-Header "Step 6: Running Automated Test Suite"

Write-Info "Starting automated tests (this may take 30-60 seconds)..."
Write-Info ""

try {
    python test_camera_integration.py
    $testExitCode = $LASTEXITCODE
} catch {
    Write-Error "Test execution failed: $_"
    exit 1
}

# Summary
Write-Header "Test Run Complete"

if ($testExitCode -eq 0) {
    Write-Host "$Green✓ All tests passed!$Reset"
    Write-Info ""
    Write-Info "Next steps:"
    Write-Info "  1. Test the frontend: streamlit run ../frontend/pages/0_🏠_Dashboard.py"
    Write-Info "  2. Review logs and verify camera functionality"
    Write-Info "  3. Proceed with GCP deployment if ready"
    Write-Info ""
} else {
    Write-Host "$Red✗ Some tests failed. Review output above.$Reset"
    Write-Info ""
    Write-Info "Troubleshooting:"
    Write-Info "  - Check DATABASE_URL is correct"
    Write-Info "  - Verify migration was applied successfully"
    Write-Info "  - Review error messages in test output"
    Write-Info "  - See docs/camera-integration-local-testing.md for manual steps"
    Write-Info ""
}

exit $testExitCode
