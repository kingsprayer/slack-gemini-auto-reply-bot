# 24/7 Cloud Deployment Guide

This guide explains how to deploy your Slack Auto-Reply Bot to run continuously in the cloud, so it works **24/7 even when your PC is turned off or asleep**.

Because the bot uses **Slack Socket Mode (`xapp-...`)**, it connects outbound to Slack over WebSockets. **No static IP, domain name, or open ports are required.**

---

## 🔑 Environment Variables Needed in the Cloud

Whichever platform you choose, configure these variables in their dashboard:

| Variable Name | Value Description |
| :--- | :--- |
| `SLACK_BOT_TOKEN` | Your Bot User OAuth Token (`xoxb-...`) |
| `SLACK_USER_TOKEN` | Your User OAuth Token (`xoxp-...`) |
| `SLACK_APP_TOKEN` | Your App-Level Token with `connections:write` (`xapp-...`) |
| `SLACK_APPROVER_USER_ID` | Your Slack member ID (e.g. `U0BFBJYP2E6`) |
| `GEMINI_API_KEY` | Your Google Gemini API Key (`AQ.Ab8...`) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `PORT` | `8080` (used for cloud health check pings) |

---

## 🚀 Option 1: Railway (Recommended — 2-Minute Setup)

Railway is the fastest and most reliable cloud container platform for background Python bots.

1. **Push your code to GitHub**:
   - Go to [github.com/new](https://github.com/new) and create a **Private** repository (e.g. `slack-auto-reply-bot`).
   - Run these commands in your project terminal:
     ```bash
     git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/slack-auto-reply-bot.git
     git branch -M main
     git push -u origin main
     ```
2. **Deploy on Railway**:
   - Go to [railway.app](https://railway.app) and sign in with GitHub.
   - Click **New Project** -> **Deploy from GitHub repo** -> select `slack-auto-reply-bot`.
   - Go to **Variables** tab and click **Raw Editor**, then paste your environment variables.
   - Railway will automatically detect the `Dockerfile`, build it, and launch your bot 24/7!

---

## 🚀 Option 2: Render.com (Free Web Service)

Render allows you to host the bot for free as a Web Service.

1. **Push code to GitHub** (same as step 1 above).
2. **Deploy on Render**:
   - Go to [render.com](https://render.com) and sign in.
   - Click **New +** -> **Web Service**.
   - Connect your GitHub repository.
   - Settings:
     - **Runtime:** `Docker` (or `Python 3`)
     - **Build Command:** `pip install -r requirements.txt` (if Python)
     - **Start Command:** `python slack_bot.py`
     - **Instance Type:** `Free`
   - Under **Environment Variables**, add the 6 tokens listed above.
   - Click **Create Web Service**. The built-in `health_server.py` answers Render's health checks on port 8080 and keeps your bot alive!

---

## 🚀 Option 3: Dedicated Cloud VPS (AWS Lightsail / DigitalOcean / Oracle Cloud)

If you have a Linux virtual machine (Ubuntu / Debian):

1. **Clone the code to your server**:
   ```bash
   git clone https://github.com/<YOUR_GITHUB_USERNAME>/slack-auto-reply-bot.git
   cd slack-auto-reply-bot
   ```
2. **Create the `.env` file**:
   ```bash
   nano .env
   # Paste your tokens, save and exit
   ```
3. **Start with Docker Compose**:
   ```bash
   docker compose up -d
   ```
   Docker will restart the bot automatically on reboots or crashes (`restart: unless-stopped`).

---

## 🛑 How to Turn Off Local Mac Daemon

Once your cloud instance is running, disable the local Mac daemon so two copies don't run at the same time:

```bash
launchctl unload ~/Library/LaunchAgents/com.antigravity.slackbot.plist
```
