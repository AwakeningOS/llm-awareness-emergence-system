#!/bin/bash

echo "========================================"
echo " LLM Awareness Emergence System"
echo "========================================"
echo

cd "$(dirname "$0")"

echo "Checking Python..."
python3 --version || python --version
if [ $? -ne 0 ]; then
    echo "Python is not installed!"
    exit 1
fi

echo
echo "Starting Awareness UI..."
echo

python3 -m awareness_ui || python -m awareness_ui
