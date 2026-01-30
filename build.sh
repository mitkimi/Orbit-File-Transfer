#!/bin/bash

echo "Building Orbit File Transfer application..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed or not in PATH"
    exit 1
fi

# Run the build script
python3 build_app.py

echo ""
echo "Build process completed!"
echo ""