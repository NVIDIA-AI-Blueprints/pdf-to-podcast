#!/bin/bash
set -e

echo "🗑️  Uninstalling PDF-to-Podcast..."

helm uninstall pdf-to-podcast -n pdf-to-podcast || true

echo "🧹 Deleting namespace..."
oc delete namespace pdf-to-podcast || true

echo "✅ Cleanup complete!"
