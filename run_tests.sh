#!/bin/bash
# Test runner script for EVCC Battery Charging Controller

set -e

echo "=== EVCC Battery Charging Controller Test Suite ==="
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install test dependencies
echo "Installing test dependencies..."
pip install -r requirements-test.txt

echo
echo "=== Running Unit Tests ==="
echo

# Run tests with unittest
echo "Running tests with unittest runner..."
python test_battery_charging_controller.py

echo
echo "=== Running Tests with pytest (if available) ==="
echo

# Run tests with pytest if available
if command -v pytest &> /dev/null; then
    echo "Running tests with pytest..."
    pytest test_battery_charging_controller.py -v --tb=short
else
    echo "pytest not available, skipping pytest run"
fi

echo
echo "=== Test Summary ==="
echo "Tests completed successfully!"

# Deactivate virtual environment
deactivate

echo "All tests passed! ✅"
