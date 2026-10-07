#!/bin/bash
set -e

# Display help information
function show_help {
    echo "AgentSociety Docker Image Build Script"
    echo "Usage: ./build_docker.sh [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -t, --tag TAG  Specify image tag (default: agentsociety-runner:latest)"
    echo ""
    exit 0
}

# Default tag
TAG="agentsociety-runner:latest"

# Parse arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            ;;
        -t|--tag)
            TAG="$2"
            shift
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

echo "Starting to build AgentSociety Docker image..."
echo "Image tag: $TAG"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Script directory: $SCRIPT_DIR"

# Get project root directory
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
echo "Project root directory: $PROJECT_ROOT"

# Check project structure
if [ ! -f "$PROJECT_ROOT/Dockerfile" ]; then
    echo "Error: Dockerfile not found in $PROJECT_ROOT"
    echo "Current directory structure:"
    ls -la "$PROJECT_ROOT"
    exit 1
fi

# Build Docker image
echo "Building Docker image..."
export DOCKER_BUILDKIT=1
docker build --progress=plain -t "$TAG" -f "$PROJECT_ROOT/Dockerfile" "$PROJECT_ROOT"

# Check build result
if [ $? -eq 0 ]; then
    echo "Docker image built successfully: $TAG"
    echo ""
    echo "Usage example:"
    echo "  docker run --rm $TAG --help"
else
    echo "Docker image build failed"
    exit 1
fi 