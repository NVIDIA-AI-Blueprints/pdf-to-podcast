#!/bin/bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-pdf-to-podcast}
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUILD_TARGET="${1:-all}"

echo "🔨 PDF-to-Podcast Image Builder"
echo "================================="

# Verify OpenShift login
if ! oc whoami &> /dev/null; then
    echo "❌ Error: Not logged in to OpenShift. Run 'oc login' first."
    exit 1
fi

# Switch to namespace
oc project $NAMESPACE 2>/dev/null || oc new-project $NAMESPACE

# Function to create temporary .dockerignore (excludes unnecessary files from upload)
setup_dockerignore() {
    cat > "$REPO_ROOT/.dockerignore" <<'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
ENV/
*.egg-info/
**/*.egg-info/
dist/
build/

# Testing
.pytest_cache/
.coverage
htmlcov/
*.wav
*.mp3
*.mp4
tests/

# Git
.git/
.gitignore
.gitattributes

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Large test/sample files
samples/
test-*.wav
test-*.mp3

# Documentation (not needed in builds)
*.md
!README.md

# Jupyter
*.ipynb
.ipynb_checkpoints/

# OpenShift scripts/docs (not needed in builds)
openshift/*.md
openshift/*.sh
EOF
}

# Function to clean up temporary .dockerignore
cleanup_dockerignore() {
    rm -f "$REPO_ROOT/.dockerignore"
}

# Ensure cleanup on script exit (even on errors)
trap cleanup_dockerignore EXIT

# Create .dockerignore once for all builds
setup_dockerignore

# Service build functions
build_api_service() {
    echo "Building api-service..."
    if ! oc get bc api-service &>/dev/null; then
        oc new-build --name=api-service --binary --strategy=docker
    fi
    oc patch bc api-service --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"services/APIService/Dockerfile"}}}}'
    oc start-build api-service --from-dir="$REPO_ROOT" --follow
}

build_agent_service() {
    echo "Building agent-service..."
    if ! oc get bc agent-service &>/dev/null; then
        oc new-build --name=agent-service --binary --strategy=docker
    fi
    oc patch bc agent-service --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"services/AgentService/Dockerfile"}}}}'
    oc start-build agent-service --from-dir="$REPO_ROOT" --follow
}

build_pdf_service() {
    echo "Building pdf-service..."
    if ! oc get bc pdf-service &>/dev/null; then
        oc new-build --name=pdf-service --binary --strategy=docker
    fi
    oc patch bc pdf-service --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"services/PDFService/Dockerfile"}}}}'
    oc start-build pdf-service --from-dir="$REPO_ROOT" --follow
}

build_tts_service() {
    echo "Building tts-service..."
    if ! oc get bc tts-service &>/dev/null; then
        oc new-build --name=tts-service --binary --strategy=docker
    fi
    oc patch bc tts-service --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"services/TTSService/Dockerfile"}}}}'
    oc start-build tts-service --from-dir="$REPO_ROOT" --follow
}

build_pdf_api() {
    echo "Building pdf-api..."
    if ! oc get bc pdf-api &>/dev/null; then
        oc new-build --name=pdf-api --binary --strategy=docker
    fi
    oc patch bc pdf-api --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"Dockerfile.api"}},"resources":{"limits":{"cpu":"2","memory":"4Gi"}},"completionDeadlineSeconds":900}}'
    oc start-build pdf-api --from-dir="$REPO_ROOT/services/PDFService/PDFModelService" --follow
}

build_celery_worker() {
    echo "Building celery-worker (downloads ML models)..."
    if ! oc get bc celery-worker &>/dev/null; then
        oc new-build --name=celery-worker --binary --strategy=docker
    fi
    oc patch bc celery-worker --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"Dockerfile.worker"}},"resources":{"limits":{"cpu":"2","memory":"8Gi"}},"completionDeadlineSeconds":1200}}'
    oc start-build celery-worker --from-dir="$REPO_ROOT/services/PDFService/PDFModelService" --follow
}

build_frontend() {
    echo "Building frontend..."
    if ! oc get bc frontend &>/dev/null; then
        oc new-build --name=frontend --binary --strategy=docker
    fi
    oc patch bc frontend --type=merge -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"openshift/frontend/Dockerfile"}}}}'
    oc start-build frontend --from-dir="$REPO_ROOT" --follow
}

# Main execution
case "$BUILD_TARGET" in
    api-service)      build_api_service ;;
    agent-service)    build_agent_service ;;
    pdf-service)      build_pdf_service ;;
    tts-service)      build_tts_service ;;
    pdf-api)          build_pdf_api ;;
    celery-worker)    build_celery_worker ;;
    frontend)         build_frontend ;;
    all)
        build_api_service
        build_agent_service
        build_pdf_service
        build_tts_service
        build_pdf_api
        build_celery_worker
        build_frontend
        ;;
    *)
        echo "❌ Unknown target: $BUILD_TARGET"
        echo "Usage: ./build-images.sh [api-service|agent-service|pdf-service|tts-service|pdf-api|celery-worker|frontend|all]"
        exit 1
        ;;
esac

echo ""
echo "✅ Build(s) completed successfully!"
echo ""
echo "📋 View images: oc get imagestreams -n $NAMESPACE"
echo "🚀 Next step: ./deploy-helm.sh"
