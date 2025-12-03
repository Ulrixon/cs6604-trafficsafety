#!/bin/bash
#
# Camera Integration - Automated Test Script (Linux/Mac)
#
# This script automates the entire testing process:
# 1. Sets up environment variables
# 2. Applies database migration
# 3. Runs automated test suite
#
# Usage:
#   ./test-camera-integration.sh
#
# Or with custom database URL:
#   DATABASE_URL="postgresql://..." ./test-camera-integration.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo ""
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo ""
}

print_step() {
    echo -ne "${YELLOW}▶ $1...${NC}"
}

print_success() {
    if [ -n "$1" ]; then
        echo -e " ${GREEN}✓ $1${NC}"
    else
        echo -e " ${GREEN}✓${NC}"
    fi
}

print_error() {
    echo -e " ${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${CYAN}$1${NC}"
}

# Start
print_header "Camera Integration - Automated Test Setup"

# Step 1: Check prerequisites
print_header "Step 1: Checking Prerequisites"

print_step "Python 3.11+"
PYTHON_VERSION=$(python3 --version 2>&1)
if [[ $PYTHON_VERSION =~ Python\ 3\.(1[1-9]|[2-9][0-9]) ]]; then
    print_success "$PYTHON_VERSION"
else
    print_error "Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

print_step "PostgreSQL client (psql)"
if command -v psql &> /dev/null; then
    print_success "Found"
else
    print_error "psql not found. Install PostgreSQL client"
    exit 1
fi

# Step 2: Set environment variables
print_header "Step 2: Environment Configuration"

if [ -z "$DATABASE_URL" ]; then
    print_info "Enter your DATABASE_URL:"
    print_info "Format: postgresql://username:password@host:port/database"
    read -p "DATABASE_URL: " DATABASE_URL
fi

export DATABASE_URL
print_success "DATABASE_URL set"

if [ -n "$VDOT_API_KEY" ]; then
    export VDOT_API_KEY
    print_success "VDOT_API_KEY set"
else
    print_info "VDOT_API_KEY not set - will use fallback (511 map links)"
fi

# Step 3: Test database connection
print_header "Step 3: Database Connection Test"

print_step "Testing connection"
if psql "$DATABASE_URL" -c "SELECT version();" &> /dev/null; then
    print_success "Connected successfully"
else
    print_error "Connection failed"
    exit 1
fi

# Step 4: Apply database migration
print_header "Step 4: Database Migration"

print_step "Checking if camera_urls column exists"
COLUMN_CHECK=$(psql "$DATABASE_URL" -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='intersections' AND column_name='camera_urls';")

if [[ $COLUMN_CHECK =~ camera_urls ]]; then
    print_success "Migration already applied"
else
    print_step "Applying migration (03_add_camera_urls.sql)"
    if psql "$DATABASE_URL" -f backend/db/init/03_add_camera_urls.sql &> /dev/null; then
        print_success "Migration applied"
    else
        print_error "Migration failed"
        exit 1
    fi
fi

# Step 5: Install Python dependencies
print_header "Step 5: Installing Dependencies"

print_step "Installing backend requirements"
cd backend
if pip3 install -r requirements.txt --quiet &> /dev/null; then
    print_success "Dependencies installed"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Step 6: Install test dependencies
print_step "Installing test dependencies"
if pip3 install colorama requests --quiet &> /dev/null; then
    print_success "Test dependencies installed"
else
    print_error "Failed to install test dependencies"
fi

# Step 7: Run automated tests
print_header "Step 6: Running Automated Test Suite"

print_info "Starting automated tests (this may take 30-60 seconds)..."
echo ""

python3 test_camera_integration.py
TEST_EXIT_CODE=$?

# Summary
print_header "Test Run Complete"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    print_info "Next steps:"
    print_info "  1. Test the frontend: streamlit run ../frontend/pages/0_🏠_Dashboard.py"
    print_info "  2. Review logs and verify camera functionality"
    print_info "  3. Proceed with GCP deployment if ready"
    echo ""
else
    echo -e "${RED}✗ Some tests failed. Review output above.${NC}"
    echo ""
    print_info "Troubleshooting:"
    print_info "  - Check DATABASE_URL is correct"
    print_info "  - Verify migration was applied successfully"
    print_info "  - Review error messages in test output"
    print_info "  - See docs/camera-integration-local-testing.md for manual steps"
    echo ""
fi

exit $TEST_EXIT_CODE
