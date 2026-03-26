#!/usr/bin/env bash
# Deploy the full ReadRight stack (frontend + backend) to a single GCE VM
# using docker compose.
#
# Prerequisites:
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
#
# Usage:
#   ./scripts/deploy-gce.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT="${GCP_PROJECT:-$(gcloud config get-value project)}"
ZONE="${GCP_ZONE:-asia-southeast1-b}"
VM_NAME="readright"
MACHINE_TYPE="e2-standard-4"   # 4 vCPU / 16 GB RAM — needed for Whisper on CPU

# ── 1. Create VM if it doesn't exist ─────────────────────────────────────────
if gcloud compute instances describe "${VM_NAME}" --zone="${ZONE}" --project="${PROJECT}" &>/dev/null; then
  echo "→ VM '${VM_NAME}' already exists, skipping creation."
else
  echo "→ Creating VM '${VM_NAME}'..."
  gcloud compute instances create "${VM_NAME}" \
    --zone="${ZONE}" \
    --project="${PROJECT}" \
    --machine-type="${MACHINE_TYPE}" \
    --image-family="debian-12" \
    --image-project="debian-cloud" \
    --boot-disk-size="50GB" \
    --tags="readright" \
    --metadata="startup-script=#!/bin/bash
      apt-get update -y
      apt-get install -y docker.io docker-compose-plugin
      systemctl enable docker
      systemctl start docker
      usermod -aG docker \$(logname 2>/dev/null || echo debian)"

  echo "→ Waiting for VM to initialize (30s)..."
  sleep 30
fi

# ── 2. Open firewall ports (safe to re-run) ───────────────────────────────────
echo "→ Ensuring firewall rules..."
gcloud compute firewall-rules create "readright-frontend" \
  --project="${PROJECT}" --allow="tcp:3000" --target-tags="readright" \
  2>/dev/null || true
gcloud compute firewall-rules create "readright-backend" \
  --project="${PROJECT}" --allow="tcp:8000" --target-tags="readright" \
  2>/dev/null || true

# ── 3. Get external IP ────────────────────────────────────────────────────────
EXTERNAL_IP=$(gcloud compute instances describe "${VM_NAME}" \
  --zone="${ZONE}" --project="${PROJECT}" \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo "→ VM external IP: ${EXTERNAL_IP}"

# ── 4. Copy repo to VM ────────────────────────────────────────────────────────
echo "→ Copying project files to VM..."
# Pack only what docker compose needs (excludes .venv, node_modules, etc.)
tar \
  --exclude='./.venv' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./.git' \
  --exclude='./.cache' \
  --exclude='./uploads' \
  --exclude='./validation/results' \
  -czf /tmp/readright.tar.gz .

gcloud compute scp /tmp/readright.tar.gz "${VM_NAME}:/tmp/readright.tar.gz" \
  --zone="${ZONE}" --project="${PROJECT}"

rm /tmp/readright.tar.gz

# ── 5. Build and start on the VM ─────────────────────────────────────────────
echo "→ Building and starting containers on VM (this takes a while the first time)..."
gcloud compute ssh "${VM_NAME}" --zone="${ZONE}" --project="${PROJECT}" \
  --command="
    set -e
    mkdir -p ~/readright
    tar -xzf /tmp/readright.tar.gz -C ~/readright
    cd ~/readright
    export API_URL=http://${EXTERNAL_IP}:8000
    sudo -E docker compose up --build -d
  "

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "✓ Deployed!"
echo "  Frontend : http://${EXTERNAL_IP}:3000"
echo "  API docs : http://${EXTERNAL_IP}:8000/docs"
echo ""
echo "Useful commands (run from your machine):"
echo "  View logs : gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command='cd ~/readright && sudo docker compose logs -f'"
echo "  SSH in    : gcloud compute ssh ${VM_NAME} --zone=${ZONE}"
echo "  Rebuild   : gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command='cd ~/readright && sudo API_URL=http://${EXTERNAL_IP}:8000 docker compose up --build -d'"
