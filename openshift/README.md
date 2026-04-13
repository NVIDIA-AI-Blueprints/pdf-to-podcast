# PDF-to-Podcast OpenShift Deployment

Helm chart for deploying pdf-to-podcast to Red Hat OpenShift AI (RHOAI).

## Quick Start

```bash
# Create secrets file with your API keys
cd openshift
cp secrets.env.template secrets.env
# Edit secrets.env and add your NVIDIA_API_KEY and ELEVENLABS_API_KEY

# Build and deploy
./build-images.sh all
./deploy-helm.sh

# Get frontend URL
oc get route pdf-to-podcast-frontend -n pdf-to-podcast
```

Full documentation below ↓

---

## Architecture

### Infrastructure (Subcharts)
- **MinIO** (Red Hat AI Quickstart) - Object storage for PDFs and audio files
- **Jaeger** (Official) - Distributed tracing
- **Redis** (Custom) - Message broker and caching

### Application Services
Seven custom microservices deployed as Kubernetes Deployments:

1. **api-service** - Main API with WebSocket support
2. **agent-service** - LLM-based podcast script generation
3. **pdf-service** - PDF processing orchestration
4. **pdf-api** - PDF-to-markdown conversion API
5. **celery-worker** - Asynchronous PDF processing with Docling
6. **tts-service** - Text-to-speech synthesis (ElevenLabs-based)
7. **frontend** - Gradio web interface

## Prerequisites

- OpenShift CLI (`oc`) installed and configured
- Helm 3.x installed
- Access to an OpenShift cluster with RHOAI
- NVIDIA API key (from https://build.nvidia.com/) - for LLM/agent-service
- ElevenLabs API key (from https://elevenlabs.io/) - for TTS service
- Container registry access (uses OpenShift internal registry by default)

## Quick Start

### Step 1: Build Container Images

```bash
# Login to OpenShift
oc login --server=https://your-cluster:6443

# Build all images using cluster resources
cd openshift
./build-images.sh all
```

The script creates BuildConfig objects and builds all 7 container images inside the cluster using OpenShift's internal registry.

**Build specific service:**
```bash
./build-images.sh api-service
```

**Available targets:** api-service, agent-service, pdf-service, tts-service, pdf-api, celery-worker, frontend, all

### Step 2: Configure API Keys

```bash
# Create secrets file
cp secrets.env.template secrets.env
vim secrets.env  # Add your NVIDIA_API_KEY and ELEVENLABS_API_KEY
```

### Step 3: Deploy to OpenShift

```bash
# Use default namespace (pdf-to-podcast)
./deploy-helm.sh

# Or use existing namespace
export OPENSHIFT_NAMESPACE=my-existing-namespace
./deploy-helm.sh
```

The script automatically downloads dependencies (MinIO, Jaeger), creates namespace if needed, and deploys all services.

### Step 4: Access the Application

```bash
# Get frontend route URL
oc get route pdf-to-podcast-frontend -n pdf-to-podcast

# Open in browser
export FRONTEND_URL=$(oc get route pdf-to-podcast-frontend -n pdf-to-podcast -o jsonpath='{.spec.host}')
xdg-open "https://$FRONTEND_URL"
```

---

## Using the Notebook in RHOAI

The `launchable/PDFtoPodcast.ipynb` notebook works seamlessly in RHOAI workbenches.

### Prerequisites

1. **Services deployed** to OpenShift (see Quick Start above)
2. **RHOAI Workbench** in `pdf-to-podcast` namespace
   - Image: **Jupyter | Minimal | CPU | Python 3.12**
   - No additional packages needed (requests is pre-installed)

### Setup

#### 1. Create Workbench with Environment Variable (RECOMMENDED)

When creating your RHOAI workbench, set the deployment mode:

**Option A: Via RHOAI Workbench UI**
- During workbench creation, add environment variable:
  - Name: `DEPLOYMENT_MODE`
  - Value: `openshift`

**Option B: In Notebook Cell (Fallback)**

If you didn't set it during workbench creation, uncomment these lines in the **first cell** of the notebook:
```python
import os
os.environ['DEPLOYMENT_MODE'] = 'openshift'
```

#### 2. Upload and Run Notebook

Upload `launchable/PDFtoPodcast.ipynb` to your workbench and run it.

The notebook will automatically:
- ✅ Detect OpenShift mode via `DEPLOYMENT_MODE` environment variable
- ⏭️ Skip docker-compose deployment
- 🔗 Use internal Kubernetes service URLs
- ✅ Verify services are accessible
- 🎙️ Generate podcasts

### Service URLs (Automatic)

When `DEPLOYMENT_MODE=openshift`, the notebook uses cluster-internal URLs:
- API: `http://api-service:8002` (main endpoint for all operations)
- Jaeger: `http://pdf-to-podcast-jaeger:16686` (tracing UI)
- MinIO: `http://minio:9090` (object storage UI)

> **Note**: The notebook only calls the API service directly. Other services (PDF, Agent, TTS) are internal microservices called by the API.

### Troubleshooting

**Services not ready?**
```bash
# Check pod status
oc get pods -n pdf-to-podcast

# Check logs for any failing deployment
oc logs -f deployment/<deployment-name> -n pdf-to-podcast
# Example: deployment/api-service, deployment/tts-service, etc.
```

**Wrong mode detected?**
```python
# Check environment variable in a notebook cell
import os
print(os.getenv('DEPLOYMENT_MODE'))
# Should output: openshift
```

---

## Configuration

### Namespace

```bash
# Use custom namespace (default: pdf-to-podcast)
export OPENSHIFT_NAMESPACE=my-namespace
./deploy-helm.sh
```

### Resource Scaling

Edit `values.yaml` or `values-prod.yaml`:

```yaml
# Scale specific services
celeryWorker:
  replicas: 2
  resources:
    requests:
      cpu: "1"
      memory: "4Gi"
    limits:
      cpu: "2"
      memory: "8Gi"

# Enable GPU for PDF processing
celeryWorker:
  gpu:
    enabled: true
    count: 1
```

### Storage Sizing

```yaml
# Increase MinIO storage
minio:
  volumeClaimTemplates:
    - metadata:
        name: minio-data
      spec:
        resources:
          requests:
            storage: 100Gi

# Increase PDF temp storage
pdfTempStorage:
  size: 20Gi
```

### Production Deployment

Edit `values-prod.yaml` for production settings, then deploy:

```bash
# Update deploy-helm.sh to use values-prod.yaml or
# manually specify when deploying
./deploy-helm.sh
```

## Updating Images After Code Changes

```bash
# Make your code changes locally
vim services/APIService/main.py

# Rebuild the image
cd openshift
./build-images.sh api-service

# Restart deployment to use new image
oc rollout restart deployment/api-service -n pdf-to-podcast
```

## Troubleshooting

**Check pod status:**
```bash
oc get pods -n pdf-to-podcast
oc logs -f deployment/api-service -n pdf-to-podcast
```

**Verify Helm release:**
```bash
helm status pdf-to-podcast -n pdf-to-podcast
helm get values pdf-to-podcast -n pdf-to-podcast
```

**Check routes:**
```bash
oc get routes -n pdf-to-podcast
oc describe route pdf-to-podcast-api -n pdf-to-podcast
```

**Debug dependency issues:**
```bash
# List downloaded dependencies
ls -la pdf-to-podcast-chart/charts/

# Re-download dependencies
cd pdf-to-podcast-chart
helm dependency update
```

## Chart Structure

```
openshift/
├── README.md                         # This file
├── deploy-helm.sh                    # One-command deployment
├── undeploy-helm.sh                  # Cleanup script
├── build-images.sh                   # BuildConfig image builder
├── secrets.env.template              # API keys template
├── frontend/                         # Frontend Dockerfile
└── pdf-to-podcast-chart/             # Helm chart
    ├── Chart.yaml                    # Chart metadata + dependencies
    ├── Chart.lock                    # Dependency versions
    ├── values.yaml                   # Default configuration
    ├── values-prod.yaml              # Production overrides
    ├── charts/                       # Downloaded subcharts (gitignored)
    └── templates/                    # K8s manifests
        ├── _helpers.tpl
        ├── namespace.yaml
        ├── secrets.yaml
        ├── configmaps.yaml
        ├── pvc.yaml
        ├── *-deployment.yaml         # 7 service deployments
        ├── services.yaml
        └── routes.yaml
```

## What Gets Deployed

| Component | Type | Managed By |
|-----------|------|------------|
| Redis | Deployment | Our templates |
| MinIO | StatefulSet | Red Hat AI Quickstart subchart |
| Jaeger | Deployment | Official subchart |
| celery-worker | Deployment | Our templates |
| pdf-api | Deployment | Our templates |
| pdf-service | Deployment | Our templates |
| agent-service | Deployment | Our templates |
| tts-service | Deployment | Our templates |
| api-service | Deployment | Our templates |
| frontend | Deployment | Our templates |

**Total:** 10 deployments/statefulsets

## Production Considerations

### Operator Alternative

For long-term enterprise production, Red Hat recommends using **Operators** instead of Helm charts for stateful infrastructure:

- **Redis Operator** - [Redis Enterprise Operator](https://operatorhub.io/operator/redis-enterprise-operator)
- **Storage Operator** - [OpenShift Data Foundation](https://www.redhat.com/en/technologies/cloud-computing/openshift-data-foundation)

**Migration Path:**
1. ✅ Start with this Helm chart for development and initial production
2. Validate application works on OpenShift
3. Migrate to Operators if advanced HA/DR is needed
4. Keep Helm chart for dev/test environments

The Helm approach is valid and widely used in OpenShift - don't over-engineer!

### Security Best Practices

- API keys stored as Kubernetes Secrets (base64-encoded)
- All services use ClusterIP (not exposed externally)
- External access only through OpenShift Routes (automatic TLS)
- Security contexts configured for OpenShift SCC compliance

## Uninstall

```bash
./undeploy-helm.sh
```

Or manually:
```bash
helm uninstall pdf-to-podcast -n pdf-to-podcast
oc delete namespace pdf-to-podcast
```

## Support

For issues with:
- **Application services** - Check this repository's issues
- **MinIO** - See [Red Hat AI Quickstart docs](https://github.com/redhat-ai-services/ai-quickstart-minio-chart)
- **Jaeger** - See [Jaeger Helm docs](https://github.com/jaegertracing/helm-charts)
