# Simple AWS EC2 Deployment Guide — GridKnowledge RAG

Deploy **GridKnowledge RAG** on an AWS EC2 instance in **under 10 minutes** using just Docker. No complex setup, no Nginx, and no domain required.

---

## Quick Architecture

```
[ Your Browser ]
       │
       ▼ (HTTP : Port 8000)
[ AWS EC2 Public IP:8000 ]
       │
       ▼
[ Docker Container (FastAPI + RAG Engine) ]
       │
       ▼
[ Local SQLite Data + Cloud APIs (Groq / OpenAI / Pinecone) ]
```

---

## Step 1: Launch an EC2 Instance (AWS Console)

1. Log in to [AWS Management Console](https://console.aws.amazon.com/ec2/) and click **Launch Instance**.
2. **Name:** `gridknowledge-server`
3. **OS Image (AMI):** Select **Ubuntu 24.04 LTS** (or 22.04 LTS) — 64-bit (x86).
4. **Instance Type:**
   - Select **`t3.small`** or **`t3.medium`** (Recommended: 2 vCPU, 2GB–4GB RAM).
5. **Key Pair:** Select an existing key pair or click **Create new key pair** (`.pem` format) and download it (e.g. `my-key.pem`).
6. **Network Settings (Security Group Rules):**
   Click **Edit** and add these two inbound rules:

| Type | Protocol | Port Range | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | `0.0.0.0/0` (or My IP) | To connect to terminal |
| **Custom TCP** | TCP | `8000` | `0.0.0.0/0` (Anywhere) | To open app in web browser |

7. **Storage:** Change size from `8 GiB` to **`20 GiB`** (gp3).
8. Click **Launch Instance**.
9. In EC2 Dashboard, click on your instance and copy the **Public IPv4 address** (e.g., `3.85.120.45`).

---

## Step 2: Connect to Your EC2 Instance

Open **Terminal** (Mac/Linux) or **PowerShell** (Windows):

```bash
# Navigate to where your key is downloaded (e.g. Downloads folder)
cd ~/Downloads

# Set permissions (Mac/Linux only)
chmod 400 my-key.pem

# SSH into the server (replace with your key name and EC2 Public IP)
ssh -i my-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

---

## Step 3: Install Docker & Docker Compose (One-Liner)

Once logged into your EC2 terminal, run:

```bash
# 1. Update packages and install Docker
sudo apt update && sudo apt install -y docker.io docker-compose-v2

# 2. Allow your user to run Docker without sudo
sudo usermod -aG docker ubuntu

# 3. Apply group changes immediately
newgrp docker
```

*Verify installation:*
```bash
docker --version
docker compose version
```

---

## Step 4: Clone Repository & Add Your API Keys

```bash
# 1. Clone the repository
git clone https://github.com/bittush8789/gridknowledge-rag.git
cd gridknowledge-rag

# 2. Create your .env file from the example
cp .env.example .env

# 3. Edit .env to add your API keys
nano .env
```

Inside `nano`, enter your actual API keys:

```env
# Required API Keys
GROQ_API_KEY=gsk_your_groq_api_key_here
OPENAI_API_KEY=sk-proj-your_openai_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here

# Leave other defaults as they are
```

> **How to save in nano:** Press `Ctrl + O`, hit `Enter`, then press `Ctrl + X` to exit.

---

## Step 5: Start the Application

Run Docker Compose to build and start the application in the background:

```bash
docker compose up -d --build
```

Wait 1–2 minutes for the initial build to finish. Check the status:

```bash
docker compose ps
```

You should see `gridknowledge-rag` with status `Up` (healthy).

---

## Step 6: Open the Application in Your Browser! 🎉

Open any web browser and go to:

```text
http://<YOUR-EC2-PUBLIC-IP>:8000
```

*(Replace `<YOUR-EC2-PUBLIC-IP>` with your actual EC2 IP, for example: `http://3.85.120.45:8000`)*

**You're live!** The GridKnowledge RAG chat interface, document library, and search are ready to use.

---

## Useful Day-to-Day Commands

### View Live Application Logs
```bash
docker compose logs -f
```
*(Press `Ctrl + C` to stop watching logs)*

### Stop the Application
```bash
docker compose down
```

### Restart the Application
```bash
docker compose restart
```

### Update with Latest Code from GitHub
```bash
git pull origin main
docker compose up -d --build
```

---

## Optional: Run on Standard Port 80 (Without typing `:8000`)

If you want users to just visit `http://<YOUR-EC2-PUBLIC-IP>` without adding `:8000` at the end:

1. In AWS Console ➔ Security Groups ➔ Add inbound rule: **HTTP (Port 80)** from `0.0.0.0/0`.
2. Edit `docker-compose.yml`:
   ```bash
   nano docker-compose.yml
   ```
   Change line 10 from:
   ```yaml
   ports:
     - "8000:8000"
   ```
   to:
   ```yaml
   ports:
     - "80:8000"
   ```
3. Restart container:
   ```bash
   docker compose down && docker compose up -d
   ```
4. Now simply visit: `http://<YOUR-EC2-PUBLIC-IP>`

---

## Troubleshooting

| Problem | Cause | Quick Fix |
| :--- | :--- | :--- |
| **Page won't load in browser** | Security Group missing port 8000 | In AWS EC2 console ➔ Security Groups ➔ Edit Inbound Rules ➔ Add **Custom TCP Port 8000** from `0.0.0.0/0`. |
| **Build freezes or crashes** | Low RAM on small instance | Add 2GB swap space: `sudo fallocate -l 2G /swap && sudo chmod 600 /swap && sudo mkswap /swap && sudo swapon /swap` |
| **Invalid API Key error** | Missing keys in `.env` | Run `nano .env` and check your `GROQ_API_KEY`, `OPENAI_API_KEY`, or `PINECONE_API_KEY`. Then run `docker compose restart`. |
