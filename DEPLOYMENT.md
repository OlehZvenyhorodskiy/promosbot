# Google Cloud & Production Deployment Guide

This guide explains how to host **Belgium Promo's Telegram Bot** (@belgiumpromos_bot) on European cloud infrastructure (Belgium / Netherlands / Frankfurt), configure keep-alive pings, and forward supermarket newsletters.

---

## 1. Hosting on European Google Cloud Data Centers

To achieve the fastest response times for users in Belgium, deploy to Google Cloud's European data centers:
- **Belgium (`europe-west1`)**: St. Ghislain, Belgium (lowest latency to Belgian store websites).
- **Netherlands (`europe-west4`)**: Eemshaven, Netherlands.
- **Frankfurt (`europe-west3`)**: Direct proximity to Telegram's European MTProto core.

---

### Option A: Google Cloud Run (Recommended Container Service)

Cloud Run provides generous free tier allocations (2 million requests/month, 360,000 vCPU-seconds, and 180 GB-hours of memory).

1. **Build and push the container**:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/belgium-promos-bot
   ```

2. **Deploy directly in Belgium (`europe-west1`)**:
   ```bash
   gcloud run deploy belgium-promos-bot \
     --image gcr.io/YOUR_PROJECT_ID/belgium-promos-bot \
     --platform managed \
     --region europe-west1 \
     --allow-unauthenticated \
     --set-env-vars BOT_TOKEN="YOUR_BOT_TOKEN",PORT="8080",KEEP_ALIVE_URL="https://YOUR_SERVICE_URL/ping" \
     --min-instances 1 \
     --memory 512Mi
   ```

   *Setting `--min-instances 1` keeps the instance active so Telegram long-polling stays connected without sleep latency.*

---

### Option B: Google Compute Engine European VM

Deploy on a lightweight Debian VM in Belgium or the Netherlands:

1. **Create the VM in Belgium or Netherlands**:
   ```bash
   # Create in Belgium (europe-west1-b)
   gcloud compute instances create promos-bot-vm \
     --machine-type=e2-small \
     --zone=europe-west1-b \
     --image-family=debian-12 \
     --image-project=debian-cloud \
     --boot-disk-size=20GB
   ```

2. **Deploy with Docker Compose**:
   ```bash
   gcloud compute ssh promos-bot-vm --zone=europe-west1-b

   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose git

   git clone <YOUR_REPO_URL> promos-bot
   cd promos-bot

   sudo docker-compose up -d --build
   ```

---

## 2. Keep-Alive / Anti-Sleep Configuration

The application includes an internal web server on port 8080.
- Endpoint: `GET /ping`
- Endpoint: `GET /health`

To ensure zero downtime:
1. **Built-in self-ping**: Set `KEEP_ALIVE_URL=https://your-service-url/ping` in `.env`. The bot pings itself every 5 minutes in an asynchronous background loop.
2. **External Pinger**: Add `https://your-service-url/ping` to [UptimeRobot](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org) set to ping every 5 minutes.

---

## 3. Supermarket Newsletter Ingestion

Supermarkets (Colruyt, Delhaize, Carrefour, Lidl) frequently send weekly promo newsletters. The bot accepts inbound HTML flyers and extracts deals into Telegram cards:

- **Endpoint**: `POST /api/v1/inbound-newsletter`
- **Payload** (JSON):
  ```json
  {
    "sender": "promo@colruyt.be",
    "subject": "Rode Prijzen deze week",
    "html": "<html><body>...raw email body...</body></html>"
  }
  ```

---

## 4. Local Execution & Testing

```bash
# 1. Activate environment
.venv\Scripts\activate

# 2. Run bot and web server
python -m src.main
```

Open Telegram and test [@belgiumpromos_bot](https://t.me/belgiumpromos_bot).
