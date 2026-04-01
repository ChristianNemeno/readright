#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# ReadRight — Production deploy to GCE with Caddy + HTTPS
# Domain: readright.nenome.online
#
# Prerequisites:
#   1. Authenticated with gcloud SDK locally (gcloud auth login)
#   2. deploy.env exists at the repo root
#   3. Commit and push Caddyfile + docker-compose.prod.yml to
#      GitHub before running — the VM clones from there
#
# DNS note:
#   After first run, point readright.nenome.online → the VM's
#   external IP printed below. Caddy won't issue a TLS cert
#   until DNS resolves to the VM. If Caddy starts before DNS
#   is set, just restart it after DNS propagates:
#     gcloud compute ssh readright-prod --zone=asia-southeast1-b \
#       --command="cd ~/readright && sudo docker compose -f docker-compose.prod.yml restart caddy"
#
# Usage: bash scripts/deploy-gce-prod.sh
# ============================================================

VM_NAME="readright-prod"
MACHINE_TYPE="e2-standard-4"
DISK_SIZE="20GB"
NETWORK_TAG="readright-prod"
SSH_OPTS="--strict-host-key-checking=no"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ENV="${SCRIPT_DIR}/../deploy.env"

if [ ! -f "${DEPLOY_ENV}" ]; then
  echo "Error: deploy.env not found at ${DEPLOY_ENV}"
  echo "Copy deploy.env.example to deploy.env and fill in values."
  exit 1
fi

# shellcheck source=/dev/null
source "${DEPLOY_ENV}"

echo "==> Project : ${GCP_PROJECT}"
echo "==> Zone    : ${GCP_ZONE}"
echo "==> VM name : ${VM_NAME}"
echo ""

# ── 1. Create VM if it doesn't exist ───────────────────────────────────────
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
    --boot-disk-size="${DISK_SIZE}" \
    --tags="${NETWORK_TAG}"

  # Wait for SSH to become available (retry up to ~3 min)
  echo "→ Waiting for SSH to become available..."
  for i in $(seq 1 18); do
    if gcloud compute ssh "${VM_NAME}" \
         --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
         --command="echo ok" ${SSH_OPTS} &>/dev/null; then
      echo "→ SSH ready."
      break
    fi
    echo "  (attempt ${i}/18, retrying in 10s...)"
    sleep 10
  done

fi

# ── Install dependencies (idempotent — safe to re-run) ─────────────────────
echo "→ Ensuring Docker and git are installed on VM..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${GCP_ZONE}" \
  --project="${GCP_PROJECT}" \
  ${SSH_OPTS} \
  --command="
    set -e
    sudo apt-get update -y -qq
    sudo apt-get install -y -qq docker.io docker-compose-plugin git
    sudo systemctl enable docker
    sudo systemctl start docker
  "

# ── 2. Firewall rules (idempotent) ─────────────────────────────────────────
echo "→ Ensuring firewall rules for HTTP/HTTPS..."
gcloud compute firewall-rules create "readright-prod-http" \
  --project="${GCP_PROJECT}" \
  --allow="tcp:80" \
  --target-tags="${NETWORK_TAG}" \
  --description="ReadRight prod: HTTP (Caddy ACME challenge)" \
  2>/dev/null || true

gcloud compute firewall-rules create "readright-prod-https" \
  --project="${GCP_PROJECT}" \
  --allow="tcp:443" \
  --target-tags="${NETWORK_TAG}" \
  --description="ReadRight prod: HTTPS (Caddy TLS termination)" \
  2>/dev/null || true

# ── 3. Get external IP ─────────────────────────────────────────────────────
EXTERNAL_IP=$(gcloud compute instances describe "${VM_NAME}" \
  --zone="${GCP_ZONE}" --project="${GCP_PROJECT}" \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "→ VM external IP: ${EXTERNAL_IP}"
echo ""
echo "  *** DNS reminder ***"
echo "  Set an A record: readright.nenome.online → ${EXTERNAL_IP}"
echo "  Caddy cannot issue a TLS cert until this resolves."
echo ""

# ── 4. Clone or pull repo on the VM ────────────────────────────────────────
echo "→ Syncing code from GitHub on the VM..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${GCP_ZONE}" \
  --project="${GCP_PROJECT}" \
  ${SSH_OPTS} \
  --command="
    set -e
    if [ -d ~/readright/.git ]; then
      echo 'Repo found, pulling latest...'
      cd ~/readright && git pull
    else
      echo 'Cloning repo...'
      git clone ${REPO_URL} ~/readright
    fi
  "

# ── 5. Build and start production stack ────────────────────────────────────
echo "→ Building and starting containers (first build is slow — Whisper models download on first assess)..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${GCP_ZONE}" \
  --project="${GCP_PROJECT}" \
  ${SSH_OPTS} \
  --command="
    set -e
    cd ~/readright
    sudo docker compose -f docker-compose.prod.yml up --build -d
    echo ''
    sudo docker compose -f docker-compose.prod.yml ps
  "

echo ""
echo "✓ Deployment complete!"
echo ""
echo "  URL   : https://readright.nenome.online"
echo "  VM IP : ${EXTERNAL_IP}"
echo ""
echo "Useful commands:"
echo "  Logs        : gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE} --command='cd ~/readright && sudo docker compose -f docker-compose.prod.yml logs -f'"
echo "  Caddy logs  : gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE} --command='cd ~/readright && sudo docker compose -f docker-compose.prod.yml logs caddy'"
echo "  SSH in      : gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE}"
echo "  Redeploy    : bash scripts/deploy-gce-prod.sh"
