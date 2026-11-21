# 🤖 Slack AI Auto-Reply Bot (Human-in-the-Loop)

Automate your incoming Slack Direct Messages and channel mentions with AI-drafted replies powered by **Google Gemini**, with a **one-click human approval gate** before any message is sent.

---

## 🌟 How It Works

1. **Incoming Message**: Someone sends you a Direct Message or mentions you (`@YourName`) in a channel.
2. **Context & AI Drafting**: The bot reads the recent conversation history and uses **Gemini 2.5 Flash** to draft a context-aware, natural response matching your tone.
3. **Approval Card**: The bot sends a private interactive card to your Slackbot DM with:
   - The sender's name and original message.
   - The AI's proposed response.
   - Three action buttons:
     - `[✅ Approve & Send]`: Immediately posts the reply to the sender.
     - `[✏️ Edit Draft]`: Opens a modal for you to tweak the text before sending.
     - `[❌ Dismiss]`: Discards the draft.
4. **Audit Trail**: Every incoming message and decision is tracked in a local SQLite database (`drafts.db`).

---

## 🚀 Quick Setup Guide

### Step 1: Install Dependencies
In this directory:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Step 2: Configure Your Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** -> **From scratch**.
2. Name your app (e.g., `AssistantBot`) and select your Slack workspace.

#### A. Enable Socket Mode (No Webhook / ngrok Needed!)
* In the left menu, click **Socket Mode**.
* Toggle **Enable Socket Mode** to **On**.
* You will be prompted to generate an **App-Level Token**:
  * Name: `SocketModeToken`
  * Add scope: `connections:write`
* Copy the token starting with `xapp-...` — this is your `SLACK_APP_TOKEN`.

#### B. Configure Bot Scopes
* Go to **OAuth & Permissions** in the left menu.
* Scroll down to **Scopes** -> **Bot Token Scopes** and add:
  * `chat:write` (Post messages)
  * `im:history` (Read direct messages)
  * `im:read` (View direct message channels)
  * `im:write` (Start direct message threads)
  * `app_mentions:read` (Listen to `@mentions`)
  * `users:read` (Lookup sender display names)
* *(Optional)* If you want approved replies to appear as sent by **YOU directly** instead of the bot:
  * Under **User Token Scopes**, add `chat:write`.
  * After installation, copy the `xoxp-...` token and put it in `SLACK_USER_TOKEN`.

#### C. Enable Event Subscriptions
* In the left menu, go to **Event Subscriptions** and toggle **Enable Events** to **On**.
* Under **Subscribe to bot events**, add:
  * `message.im` (Triggered on new incoming DMs)
  * `app_mention` (Triggered when bot or mention is tagged)
* Click **Save Changes**.

#### D. Enable Interactivity
* In the left menu, click **Interactivity & Shortcuts** and toggle **Interactivity** to **On**.
* Click **Save Changes** (Socket Mode routes interactive buttons automatically without a Request URL).

#### E. Install to Workspace & Get Tokens
* In the left menu, go to **Install App** and click **Install to Workspace**.
* Authorize the app.
* Copy the **Bot User OAuth Token** (`xoxb-...`) — this is your `SLACK_BOT_TOKEN`.

---

### Step 3: Find Your Slack User ID
1. Open Slack, click your profile picture in the bottom-left or top-right.
2. Click the three dots `...` next to your profile name.
3. Click **Copy member ID** (starts with `U...`, e.g., `U0123456789`).
4. This is your `SLACK_APPROVER_USER_ID`.

---

### Step 4: Configure `.env`
Copy the template and fill in your values:
```bash
cp .env.example .env
```

Edit `.env`:
```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_APPROVER_USER_ID=U0123456789
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

---

### Step 5: Test & Run
Run the unit tests to verify the SQLite database, AI engine, and Block Kit card builder:
```bash
python3 test_setup.py
```

Start the bot:
```bash
python3 slack_bot.py
```

You will see:
```text
⚡ Starting Slack Auto-Reply Bot in Socket Mode...
[INFO] Bolt app is running!
```

---

## 🛡️ Privacy & Safety Guarantees
* **No Unapproved Dispatches**: The bot will **never** send a reply directly to a sender without your explicit interaction with `[✅ Approve & Send]` or `[✏️ Edit Draft]`.
* **Zero Self-Loops**: The bot ignores messages sent by yourself and other bots.
* **Local Persistence**: All pending drafts and status logs are stored locally on your machine in `drafts.db`.
