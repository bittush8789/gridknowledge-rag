# Local Kubernetes Deployment Guide (KinD) — GridKnowledge RAG

This guide walks you through deploying **GridKnowledge RAG** on a local **Kubernetes (k8s)** cluster using **KinD (Kubernetes IN Docker)** from start to finish.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites & Tool Installation](#2-prerequisites--tool-installation)
3. [Step 1: Create the Local KinD Cluster](#step-1-create-the-local-kind-cluster)
4. [Step 2: Build the Docker Image Locally](#step-2-build-the-docker-image-locally)
5. [Step 3: Load the Image into KinD](#step-3-load-the-image-into-kind)
6. [Step 4: Configure Secrets & Credentials](#step-4-configure-secrets--credentials)
7. [Step 5: Apply Kubernetes Manifests](#step-5-apply-kubernetes-manifests)
8. [Step 6: Verify Pods & Services](#step-6-verify-pods--services)
9. [Step 7: Access in Your Web Browser](#step-7-access-in-your-web-browser)
10. [Useful Operations & Debugging](#10-useful-operations--debugging)
11. [Cluster Teardown (Clean Up)](#11-cluster-teardown-clean-up)

---

## 1. Architecture Overview

```
[ Your Web Browser ]
        │
        ▼ (HTTP : http://localhost:8000)
[ KinD Node (Docker Container: gridknowledge-control-plane) ]
        │
        ▼ (Port Forwarding: 8000 ➔ NodePort 30080)
[ Kubernetes Service: gridknowledge-service (Namespace: gridknowledge) ]
        │
        ▼ (TargetPort 8000)
[ Kubernetes Pod: gridknowledge-app-xxxx ]
  ├── FastAPI + Uvicorn Application
  ├── Liveness & Readiness Probes (/api/health)
  ├── ConfigMap (gridknowledge-config)
  ├── Secret (gridknowledge-secrets)
  └── PersistentVolumeClaim (gridknowledge-data-pvc)
        └── Mounted at `/app/data` (Stores SQLite DB & documents)
```

---

## 2. Prerequisites & Tool Installation

Ensure you have **Docker** running before proceeding.

### 2.1 Install `kubectl` (Kubernetes CLI)
- **Windows (PowerShell with Winget or Chocolatey):**
  ```powershell
  winget install Kubernetes.kubectl
  # OR via Chocolatey:
  choco install kubernetes-cli
  ```
- **macOS (Homebrew):**
  ```bash
  brew install kubectl
  ```
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt update && sudo apt install -y kubectl
  ```

*Verify installation:*
```bash
kubectl version --client
```

---

### 2.2 Install `kind` (Kubernetes IN Docker)
- **Windows (PowerShell with Winget or Chocolatey):**
  ```powershell
  winget install Kubernetes.kind
  # OR via Chocolatey:
  choco install kind
  ```
- **macOS (Homebrew):**
  ```bash
  brew install kind
  ```
- **Linux:**
  ```bash
  curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64
  chmod +x ./kind
  sudo mv ./kind /usr/local/bin/kind
  ```

*Verify installation:*
```bash
kind version
```

---

## Step 1: Create the Local KinD Cluster

The repository includes a ready-to-use KinD cluster definition at [`k8s/kind-config.yaml`](file:///d:/GridKnowledge/k8s/kind-config.yaml). This configuration maps host port `8000` directly to NodePort `30080` so you can open the app in your browser without extra commands.

In your terminal (from the `GridKnowledge` project root):

```bash
kind create cluster --config k8s/kind-config.yaml --name gridknowledge
```

*Expected Output:*
```text
Creating cluster "gridknowledge" ...
 • Ensuring node image (kindest/node:v1.31.2) 🖼
 • Preparing nodes 📦
 • Writing configuration 📜
 • Starting control-plane 🕹️
 • Installing CNI 🔌
 • Installing StorageClass 💾
Set kubectl context to "kind-gridknowledge"
You can now use your cluster with:

kubectl cluster-info --context kind-gridknowledge
```

Verify your cluster nodes:
```bash
kubectl get nodes
```

---

## Step 2: Build the Docker Image Locally

Build the container image using the root `Dockerfile`:

```bash
docker build -t gridknowledge-rag:latest .
```

*Note: This builds the Python 3.11 image with all requirements, OCR tools, and application code.*

---

## Step 3: Load the Image into KinD

KinD runs Kubernetes inside Docker containers and does not automatically share your local Docker image cache. Load your built image directly into the KinD cluster:

```bash
kind load docker-image gridknowledge-rag:latest --name gridknowledge
```

*Expected Output:*
```text
Image: "gridknowledge-rag:latest" with ID "..." not yet present on node "gridknowledge-control-plane", loading...
```

Now Kubernetes pods can instantiate `gridknowledge-rag:latest` without needing a remote registry (Docker Hub / ECR).

---

## Step 4: Configure Secrets & Credentials

1. Copy the example secret template to create your actual secret file:
   ```bash
   # Windows PowerShell:
   Copy-Item k8s/secret.example.yaml k8s/secret.yaml

   # macOS / Linux:
   cp k8s/secret.example.yaml k8s/secret.yaml
   ```

2. Open `k8s/secret.yaml` in your editor and insert your actual API keys:
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: gridknowledge-secrets
     namespace: gridknowledge
   type: Opaque
   stringData:
     SECRET_KEY: "replace-with-a-random-secure-secret-key"
     JWT_SECRET: "replace-with-a-random-jwt-signing-secret"
     GROQ_API_KEY: "gsk_your_actual_groq_key"
     OPENAI_API_KEY: "sk-proj-your_actual_openai_key"
     PINECONE_API_KEY: "your_actual_pinecone_key"
     LANGCHAIN_API_KEY: ""
   ```

3. Apply the Secret:
   ```bash
   kubectl apply -f k8s/secret.yaml
   ```
   *(Note: `k8s/secret.yaml` is listed in `.gitignore` to prevent committing secrets to GitHub).*

---

## Step 5: Apply Kubernetes Manifests

Apply the remaining manifests (`namespace`, `configmap`, `pvc`, `deployment`, and `service`):

```bash
kubectl apply -f k8s/
```

*Or using Kustomize:*
```bash
kubectl apply -k k8s/
```

*Expected Output:*
```text
namespace/gridknowledge unchanged
configmap/gridknowledge-config created
persistentvolumeclaim/gridknowledge-data-pvc created
deployment.apps/gridknowledge-app created
service/gridknowledge-service created
```

---

## Step 6: Verify Pods & Services

### 6.1 Check Pod Status
```bash
kubectl get pods -n gridknowledge -w
```
Wait 15–30 seconds until the status changes from `ContainerCreating` to `Running` and `READY` is `1/1`:
```text
NAME                                 READY   STATUS    RESTARTS   AGE
gridknowledge-app-58f79d5f7c-x89qp   1/1     Running   0          25s
```

### 6.2 Check Persistent Volume Claim (PVC)
```bash
kubectl get pvc -n gridknowledge
```
*Expected: `STATUS: Bound` (using KinD's default `standard` local-path storage class).*

### 6.3 Check Service & NodePort
```bash
kubectl get svc -n gridknowledge
```
*Expected Output:*
```text
NAME                    TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
gridknowledge-service   NodePort   10.96.85.120   <none>        8000:30080/TCP   40s
```

### 6.4 View Live Application Logs
```bash
kubectl logs -f -l app.kubernetes.io/name=gridknowledge-rag -n gridknowledge
```
*(Press `Ctrl + C` to exit log stream).*

---

## Step 7: Access in Your Web Browser

Because `k8s/kind-config.yaml` configured port forwarding (`containerPort: 30080 ➔ hostPort: 8000`), you can access the application immediately:

👉 **Open in browser:**
```text
http://localhost:8000
```

### Alternative: Using `kubectl port-forward`
If you ever run KinD without extra port mappings, you can always forward traffic on-demand:
```bash
kubectl port-forward -n gridknowledge svc/gridknowledge-service 8000:8000
```
Then visit `http://localhost:8000`.

---

## 10. Useful Operations & Debugging

### Check Health Endpoint Inside Cluster
```bash
kubectl exec -n gridknowledge deployment/gridknowledge-app -- curl -s http://localhost:8000/api/health
```

### Open an Interactive Shell Inside the Pod
```bash
kubectl exec -it -n gridknowledge deployment/gridknowledge-app -- /bin/bash
```

### Describe Pod Details (Diagnosing Crashes / Errors)
```bash
kubectl describe pod -l app.kubernetes.io/name=gridknowledge-rag -n gridknowledge
```

### Updating Code & Redeploying
Whenever you make changes to your Python code or frontend:
```bash
# 1. Rebuild the image
docker build -t gridknowledge-rag:latest .

# 2. Reload image into KinD
kind load docker-image gridknowledge-rag:latest --name gridknowledge

# 3. Restart the deployment
kubectl rollout restart deployment/gridknowledge-app -n gridknowledge
```

---

## 11. Cluster Teardown (Clean Up)

When you are done testing and want to delete the local Kubernetes cluster and all resources:

```bash
kind delete cluster --name gridknowledge
```

*Expected Output:*
```text
Deleting cluster "gridknowledge" ...
Deleted nodes: ["gridknowledge-control-plane"]
```

---

*Documentation maintained by the GridKnowledge Core Architecture Team.*
