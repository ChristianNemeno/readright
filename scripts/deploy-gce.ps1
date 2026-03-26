# Deploy the full ReadRight stack to a single GCE VM.
# Run from the Google Cloud SDK Shell or any PowerShell terminal:
#   cd "C:\Nemeno\3rd year\2nd sem\readright"
#   .\scripts\deploy-gce.ps1

$ErrorActionPreference = "Stop"

# ── Configuration ─────────────────────────────────────────────────────────────
$PROJECT   = if ($env:GCP_PROJECT)  { $env:GCP_PROJECT }  else { (gcloud config get-value project) }
$ZONE      = if ($env:GCP_ZONE)     { $env:GCP_ZONE }     else { "asia-southeast1-b" }
$VM_NAME   = "readright"
$MACHINE   = "e2-standard-4"
$REPO_ROOT = (Get-Location).Path

Write-Host "-> Project : $PROJECT"
Write-Host "-> Zone    : $ZONE"

# ── 1. Create VM if it doesn't exist ─────────────────────────────────────────
$vmExists = gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "-> Creating VM '$VM_NAME'..."
    gcloud compute instances create $VM_NAME `
        --zone=$ZONE `
        --project=$PROJECT `
        --machine-type=$MACHINE `
        --image-family="debian-12" `
        --image-project="debian-cloud" `
        --boot-disk-size="50GB" `
        --tags="readright" `
        --metadata="startup-script=#! /bin/bash
apt-get update -y
apt-get install -y docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker"

    Write-Host "-> Waiting 60s for VM startup script to finish..."
    Start-Sleep -Seconds 60
} else {
    Write-Host "-> VM '$VM_NAME' already exists, skipping creation."
}

# ── 2. Open firewall ports (ignore errors if rules already exist) ─────────────
Write-Host "-> Ensuring firewall rules..."
gcloud compute firewall-rules create "readright-frontend" `
    --project=$PROJECT --allow="tcp:3000" --target-tags="readright" 2>$null
gcloud compute firewall-rules create "readright-backend" `
    --project=$PROJECT --allow="tcp:8000" --target-tags="readright" 2>$null

# ── 3. Get external IP ────────────────────────────────────────────────────────
$EXTERNAL_IP = gcloud compute instances describe $VM_NAME `
    --zone=$ZONE --project=$PROJECT `
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
Write-Host "-> External IP: $EXTERNAL_IP"

# ── 4. Zip repo and copy to VM ────────────────────────────────────────────────
Write-Host "-> Zipping project files..."
$ZIP_PATH = "$env:TEMP\readright.zip"

# Remove old zip if exists
if (Test-Path $ZIP_PATH) { Remove-Item $ZIP_PATH }

# Collect files to zip (exclude heavy/generated folders)
$EXCLUDE = @('.venv', 'node_modules', 'dist', '.git', '.cache', 'uploads', '__pycache__')
$items = Get-ChildItem -Path $REPO_ROOT | Where-Object { $EXCLUDE -notcontains $_.Name }
Compress-Archive -Path $items.FullName -DestinationPath $ZIP_PATH -Force

Write-Host "-> Copying zip to VM..."
gcloud compute scp $ZIP_PATH "${VM_NAME}:/tmp/readright.zip" `
    --zone=$ZONE --project=$PROJECT

Remove-Item $ZIP_PATH

# ── 5. Build and start containers on the VM ───────────────────────────────────
Write-Host "-> Building and starting containers (first run takes 15-30 minutes)..."
$REMOTE_CMD = @"
set -e
apt-get install -y unzip 2>/dev/null || true
mkdir -p ~/readright
unzip -o /tmp/readright.zip -d ~/readright
cd ~/readright
export API_URL=http://${EXTERNAL_IP}:8000
sudo -E docker compose up --build -d
"@

gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT --command=$REMOTE_CMD

# ── 6. Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "✓ Deployed!"
Write-Host "  Frontend : http://${EXTERNAL_IP}:3000"
Write-Host "  API docs : http://${EXTERNAL_IP}:8000/docs"
Write-Host ""
Write-Host "To watch logs:"
Write-Host "  gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd ~/readright && sudo docker compose logs -f'"
Write-Host ""
Write-Host "To stop the VM (saves credits):"
Write-Host "  gcloud compute instances stop $VM_NAME --zone=$ZONE"
