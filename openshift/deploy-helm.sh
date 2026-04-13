#!/bin/bash
set -e

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

echo "📦 PDF-to-Podcast Helm Deployment"
echo "================================="

# Check prerequisites
command -v oc >/dev/null 2>&1 || { echo "❌ Error: oc CLI not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "❌ Error: Helm not found"; exit 1; }

# Check if secrets.env exists
if [ ! -f "$REPO_ROOT/openshift/secrets.env" ]; then
    echo "❌ Error: openshift/secrets.env not found"
    echo "Please create it from secrets.env.template:"
    echo "  cp openshift/secrets.env.template openshift/secrets.env"
    echo "  vim openshift/secrets.env  # Add your API keys"
    exit 1
fi

# Source secrets
source "$REPO_ROOT/openshift/secrets.env"

# Validate required variables
if [ -z "$NVIDIA_API_KEY" ]; then
    echo "❌ Error: NVIDIA_API_KEY not set in secrets.env"
    echo "Please set NVIDIA_API_KEY in secrets.env"
    exit 1
fi

if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "❌ Error: ELEVENLABS_API_KEY not set in secrets.env"
    echo "Please set ELEVENLABS_API_KEY in secrets.env (used for TTS service)"
    exit 1
fi

echo "✅ Prerequisites checked"
echo ""

# Get namespace from environment variable or use default
NAMESPACE="${OPENSHIFT_NAMESPACE:-pdf-to-podcast}"
echo "📍 Using namespace: $NAMESPACE"

# Check if namespace exists
if ! oc get namespace "$NAMESPACE" >/dev/null 2>&1; then
    echo "⚠️  Warning: Namespace '$NAMESPACE' does not exist"
    echo "Creating namespace..."
    oc create namespace "$NAMESPACE" || {
        echo "❌ Error: Failed to create namespace. Please create it manually or use an existing one."
        echo "Set OPENSHIFT_NAMESPACE environment variable to use a different namespace."
        exit 1
    }
fi

# Update Helm dependencies (Redis, MinIO, Jaeger charts)
echo "📦 Updating Helm dependencies..."
cd "$REPO_ROOT/openshift/pdf-to-podcast-chart"
helm dependency update
cd "$REPO_ROOT"

# Deploy with Helm
echo "🚀 Deploying with Helm..."
helm upgrade --install pdf-to-podcast "$REPO_ROOT/openshift/pdf-to-podcast-chart/" \
  --namespace "$NAMESPACE" \
  --set apiKeys.nvidia="$NVIDIA_API_KEY" \
  --set apiKeys.elevenlabs="$ELEVENLABS_API_KEY" \
  --set maxConcurrentRequests="${MAX_CONCURRENT_REQUESTS:-1}" \
  --wait \
  --timeout 5m

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Checking status..."
oc get pods -n "$NAMESPACE" | grep -v 'build'

echo ""
echo "🌍 API Route:"
oc get route pdf-to-podcast-api -n "$NAMESPACE" -o jsonpath='{.spec.host}'
echo ""
