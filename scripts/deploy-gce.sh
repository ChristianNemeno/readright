#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ENV="${SCRIPT_DIR}/../deploy.env"

if [ ! -f "${DEPLOY_ENV}" ]; then
  echo "Error: deploy.env not found. Copy deploy.env.example to deploy.env and fill in the required values."
  exit 1
fi

source "${DEPLOY_ENV}"

VM_NAME="readright"
MACHINE_TYPE="e2-standard-4"

# Create VM if it doesn't exist 
if gcloud compute instances describe "${VM_NAME}" \
  --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
  &>/dev/null; then
  echo "→ VM '${VM_NAME}' already exists, skipping creation."
else
  echo "→ Creating VM '${VM_NAME}'..."
  gcloud compute instances create "${VM_NAME}" \
    --zone="${GCP_ZONE}" \
    --project="${GCP_PROJECT}" \
    --machine-type="${MACHINE_TYPE}" \
    --image-family="debian-12" \
    --image-project="debian-cloud" \
    --boot-disk-size="50GB" \
    --tags="readright" \
    --metadata="startup-script=#!/bin/bash
      apt-get update -y
      apt-get install -y docker.io docker-compose-plugin git
      systemctl enable docker
      systemctl start docker
      usermod -aG docker debian"

  echo "→ Waiting for VM to initialize (30s)..."
  sleep 30
fi

# Open firewall ports (safe to re-run)
echo "→ Ensuring firewall rules..."
gcloud compute firewall-rules create "readright-frontend" \
  --project="${GCP_PROJECT}" --allow="tcp:3000" \
  --target-tags="readright" \
  2>/dev/null || true
gcloud compute firewall-rules create "readright-backend" \
  --project="${GCP_PROJECT}" --allow="tcp:8000" \
  --target-tags="readright" \
  2>/dev/null || true

#Get external IP
EXTERNAL_IP=$(gcloud compute instances describe "${VM_NAME}" \
  --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo "→ VM external IP: ${EXTERNAL_IP}"

# Clone or pull repo on the VM 
echo "→ Deploying latest code from GitHub..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
  --command="
    set -e
    if [ -d ~/readright/.git ]; then
      echo 'Repo exists, pulling latest...'
      cd ~/readright && git pull
    else
      echo 'Cloning repo...'
      git clone ${REPO_URL} ~/readright
    fi
  "

# Build and start containers 
echo "→ Building and starting containers (first run will be slow)..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${GCP_ZONE}" \
  --project="${GCP_PROJECT}" \
  --command="
    set -e
    cd ~/readright
    export API_URL=http://${EXTERNAL_IP}:8000
    sudo -E docker compose up --build -d
  "

#
echo ""
echo "✓ Deployed!"
echo "  Frontend : http://${EXTERNAL_IP}:3000"
echo "  API docs : http://${EXTERNAL_IP}:8000/docs"
echo ""
echo "Useful commands:"
echo "  Logs    : gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE} --command='cd ~/readright && sudo docker compose logs -f'"
echo "  SSH in  : gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE}"
echo "  Redeploy: just run this script again"
