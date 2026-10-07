#!/bin/bash

ROOT_DIR=$(dirname "$(realpath "$0")")/..
GTFS_DIR="$ROOT_DIR/data/gtfs"
EXPORT_DIR="$ROOT_DIR/data/exports/gtfs"
GAMA_DIR="$ROOT_DIR/GAMA/CityTransport"

if [ ! -d "$EXPORT_DIR" ]; then
    echo "Export GTFS directory does not exist. Creating it..."
    mkdir -p "$EXPORT_DIR"
fi

# Extract GTFS data
cd "$GTFS_DIR"
unzip -o -d "$GTFS_DIR" *.zip

# Generate Shape and copy to GAMA folder
echo "Generating GTFS shape files and trip info data..."
cd "$ROOT_DIR/llm-agents"
env PYTHONPATH=. python inputs/gtfs/reader.py
env PYTHONPATH=. python inputs/gtfs/gama.py

cd "$ROOT_DIR"
echo "Copying the generated files to the GAMA directory..."
cp ${EXPORT_DIR}/* ${GAMA_DIR}/includes/
