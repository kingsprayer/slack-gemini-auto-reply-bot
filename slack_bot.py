import logging
import os
from typing import Dict, Any, Optional
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError

from config import settings, validate_config
from db import (
    init_db, create_draft, get_draft, update_draft_status, set_approval_message_ts
)
from ai_engine import ai_engine
from blocks import build_approval_blocks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("slack_bot")

# Create App without# Provide a safe fallback token so the module can load and display configuration errors cleanly
app = App(
    token=settings.SLACK_BOT_TOKEN or "xoxb-placeholder",
    token_verification_enabled=False
)

@app.middleware
def log_all_payloads(body, next):
    """Logs every incoming payload received over Socket Mode."""
    event_type = body.get("event", {}).get("type") or body.get("type")
    logger.info(f"⚡ Received Slack Socket Mode Event: {event_type}")
    return next()

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def get_user_display_name(client, user_id: str) -> str:
    """Fetches user's real or display name from Slack."""
    try:
        res = client.users_info(user=user_id)
        if res.get("ok"):
            user = res.get("user", {})
            return user.get("profile", {}).get("real_name") or user.get("name") or user_id
    except SlackApiError as e:
        logger.warning(f"Could not fetch user info for {user_id}: {e}")
    return user_id

def get_recent_messages(client, channel_id: str, thread_ts: Optional[str] = None) -> list:
    """Fetches up to 5 recent messages in thread or channel for AI context."""
    history = []
    # In personal DMs, the bot is not a member, so use the User Token to fetch history
    active_client = client
    if channel_id.startswith("D") and settings.SLACK_USER_TOKEN:
        from slack_sdk import WebClient
        active_client = WebClient(token=settings.SLACK_USER_TOKEN)

    try:
        if thread_ts:
            res = active_client.conversations_replies(channel=channel_id, ts=thread_ts, limit=6)
        else:
            res = active_client.conversations_history(channel=channel_id, limit=6)
            
        if res.get("ok"):
            messages = res.get("messages", [])
            for m in reversed(messages):
                speaker = "Bot" if m.get("bot_id") else f"<@{m.get('user', 'User')}>"
                history.append({"speaker": speaker, "text": m.get("text", "")})
    except SlackApiError as e:
        logger.warning(f"Failed to fetch conversation context: {e}")
    return history


# -------------------------------------------------------------------------
# Slack Event Listeners
# -------------------------------------------------------------------------

@app.event("message")
def handle_incoming_message(event, client, say):
    """Processes incoming direct messages or channel messages."""
    channel_type = event.get("channel_type")
    user_id = event.get("user")
    bot_id = event.get("bot_id")
    text = event.get("text", "").strip()
    channel_id = event.get("channel")
    message_ts = event.get("ts")
    subtype = event.get("subtype")
    thread_ts = event.get("thread_ts") or (message_ts if channel_type != "im" else None)

    logger.info(f"📨 Message event: user={user_id}, channel_type={channel_type}, subtype={subtype}, text='{text}'")

    # Ignore bot messages, message edits/deletions, or empty messages
    if bot_id or not text or not user_id or subtype:
        return

    # In channels, avoid replying to the approver's own chat unless explicitly mentioned
    if channel_type != "im" and user_id == settings.SLACK_APPROVER_USER_ID:
        return

    # We process Direct Messages (DMs)
    if channel_type == "im":
        is_self_test = (user_id == settings.SLACK_APPROVER_USER_ID)
        if is_self_test:
            logger.info("🧪 Approver is testing the bot directly in DM.")

        process_incoming_for_approval(
            client=client,
            sender_id=user_id,
            channel_id=channel_id,
            message_ts=message_ts,
            thread_ts=thread_ts,
            incoming_text=text,
            is_dm=True
        )

@app.event("app_mention")
def handle_app_mention(event, client, say):
    """Processes messages when the bot is directly mentioned in channels."""
    user_id = event.get("user")
    text = event.get("text", "").strip()
    channel_id = event.get("channel")
    message_ts = event.get("ts")
    thread_ts = event.get("thread_ts") or message_ts

    logger.info(f"📢 App mention: user={user_id}, channel={channel_id}, text='{text}'")

    if not user_id or not text:
        return

    process_incoming_for_approval(
        client=client,
        sender_id=user_id,
        channel_id=channel_id,
        message_ts=message_ts,
        thread_ts=thread_ts,
        incoming_text=text,
        is_dm=False
    )

def process_incoming_for_approval(
    client,
    sender_id: str,
    channel_id: str,
    message_ts: str,
    thread_ts: Optional[str],
    incoming_text: str,
    is_dm: bool = True
):
    """Orchestrates AI drafting and sends approval card to the approver."""
    logger.info(f"Received message from {sender_id} in {channel_id}: '{incoming_text}'")

    sender_name = get_user_display_name(client, sender_id)
    history = get_recent_messages(client, channel_id, thread_ts=thread_ts)

    # Generate draft with Gemini
    drafted_reply = ai_engine.generate_draft(
        incoming_message=incoming_text,
        sender_name=sender_name,
        conversation_history=history
    )

    # Persist in SQLite
    draft = create_draft(
        channel_id=channel_id,
        message_ts=message_ts,
        sender_id=sender_id,
        incoming_text=incoming_text,
        drafted_reply=drafted_reply,
        sender_name=sender_name,
        thread_ts=thread_ts
    )

    # Deliver interactive approval card to the designated approver's Slackbot DM
    try:
        blocks = build_approval_blocks(
            draft_id=draft["id"],
            sender_id=sender_id,
            sender_name=sender_name,
            channel_id=channel_id,
            incoming_text=incoming_text,
            drafted_reply=drafted_reply,
            is_dm=is_dm
        )
        
        dm_response = client.chat_postMessage(
            channel=settings.SLACK_APPROVER_USER_ID,
            text=f"Pending Approval: Reply to {sender_name}",
            blocks=blocks
        )
        if dm_response.get("ok"):
            set_approval_message_ts(draft["id"], dm_response.get("ts"))
            logger.info(f"Approval card sent to {settings.SLACK_APPROVER_USER_ID} for draft #{draft['id']}")
    except SlackApiError as e:
        logger.error(f"Failed to deliver approval card: {e}", exc_info=True)

# -------------------------------------------------------------------------
# Interactive Block Kit Actions (Approval / Edit / Dismiss)
# -------------------------------------------------------------------------

@app.action("approve_and_send")
def handle_approval(ack, body, client):
    """Dispatches the approved drafted reply to Slack."""
    ack()
    draft_id = int(body["actions"][0]["value"])
    draft = get_draft(draft_id)

    if not draft or draft["status"] != "PENDING":
        return

    reply_text = draft["drafted_reply"]
    channel_id = draft["channel_id"]
    # For DMs, post directly to the chat unless it was already an ongoing thread.
    # For channels, reply in thread to avoid spamming the main channel.
    post_thread_ts = draft["thread_ts"] if channel_id.startswith("D") else (draft["thread_ts"] or draft["message_ts"])

    try:
        # If a User Token is configured, send directly as the User; otherwise as Bot
        token = settings.SLACK_USER_TOKEN if settings.SLACK_USER_TOKEN else settings.SLACK_BOT_TOKEN
        
        client.chat_postMessage(
            token=token,
            channel=channel_id,
            text=reply_text,
            thread_ts=post_thread_ts
        )
        update_draft_status(draft_id, status="SENT", final_reply=reply_text)

        # Update the original approval card in approver's DM
        card_channel = (
            body.get("container", {}).get("channel_id")
            or body.get("channel", {}).get("id")
            or settings.SLACK_APPROVER_USER_ID
        )
        client.chat_update(
            channel=card_channel,
            ts=body["container"]["message_ts"],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Approved & Sent to {draft['sender_name']}* (<@{draft['sender_id']}>):\n> {reply_text}"
                    }
                }
            ],
            text=f"Approved & Sent to {draft['sender_name']}"
        )
        logger.info(f"Draft #{draft_id} successfully sent and card updated.")
    except SlackApiError as e:
        logger.error(f"Failed to send approved message for draft #{draft_id}: {e}")

@app.action("dismiss_draft")
def handle_dismiss(ack, body, client):
    """Dismisses the draft without sending any message."""
    ack()
    draft_id = int(body["actions"][0]["value"])
    draft = get_draft(draft_id)

    if not draft or draft["status"] != "PENDING":
        return

    update_draft_status(draft_id, status="REJECTED")

    try:
        card_channel = (
            body.get("container", {}).get("channel_id")
            or body.get("channel", {}).get("id")
            or settings.SLACK_APPROVER_USER_ID
        )
        client.chat_update(
            channel=card_channel,
            ts=body["container"]["message_ts"],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Dismissed draft reply to {draft['sender_name']}* (<@{draft['sender_id']}>)."
                    }
                }
            ],
            text=f"Dismissed reply to {draft['sender_name']}"
        )
        logger.info(f"Draft #{draft_id} dismissed.")
    except SlackApiError as e:
        logger.error(f"Failed to update card for dismissed draft #{draft_id}: {e}")

@app.action("open_edit_modal")
def handle_open_edit_modal(ack, body, client):
    """Opens a Slack modal enabling inline edits before dispatch."""
    ack()
    draft_id = int(body["actions"][0]["value"])
    draft = get_draft(draft_id)

    if not draft or draft["status"] != "PENDING":
        return

    trigger_id = body["trigger_id"]
    approval_card_ts = body["container"]["message_ts"]
    card_channel = (
        body.get("container", {}).get("channel_id")
        or body.get("channel", {}).get("id")
        or settings.SLACK_APPROVER_USER_ID
    )

    try:
        client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "submit_edited_reply",
                "private_metadata": f"{draft_id}:{approval_card_ts}:{card_channel}",
                "title": {"type": "plain_text", "text": "Edit & Send Reply"},
                "submit": {"type": "plain_text", "text": "Send Reply"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*To:* {draft['sender_name']}\n*Original Message:*\n> {draft['incoming_text']}"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "reply_input_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "edited_text_input",
                            "multiline": True,
                            "initial_value": draft["drafted_reply"]
                        },
                        "label": {"type": "plain_text", "text": "Your Message"}
                    }
                ]
            }
        )
    except SlackApiError as e:
        logger.error(f"Error opening edit modal: {e}")

@app.view("submit_edited_reply")
def handle_modal_submission(ack, body, client, view):
    """Processes edited text submitted from the modal and sends it."""
    ack()
    private_metadata = view["private_metadata"]
    parts = private_metadata.split(":")
    draft_id = int(parts[0])
    approval_card_ts = parts[1]
    card_channel = parts[2] if len(parts) > 2 else settings.SLACK_APPROVER_USER_ID

    edited_text = view["state"]["values"]["reply_input_block"]["edited_text_input"]["value"]
    draft = get_draft(draft_id)

    if not draft:
        return

    channel_id = draft["channel_id"]
    post_thread_ts = draft["thread_ts"] if channel_id.startswith("D") else (draft["thread_ts"] or draft["message_ts"])

    try:
        token = settings.SLACK_USER_TOKEN if settings.SLACK_USER_TOKEN else settings.SLACK_BOT_TOKEN
        client.chat_postMessage(
            token=token,
            channel=channel_id,
            text=edited_text,
            thread_ts=post_thread_ts
        )
        update_draft_status(draft_id, status="EDITED_AND_SENT", final_reply=edited_text)

        # Update the original approval card in DM
        client.chat_update(
            channel=card_channel,
            ts=approval_card_ts,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✏️ *Edited & Sent to {draft['sender_name']}* (<@{draft['sender_id']}>):\n> {edited_text}"
                    }
                }
            ],
            text=f"Edited & Sent to {draft['sender_name']}"
        )
        logger.info(f"Draft #{draft_id} edited, sent, and card updated.")
    except SlackApiError as e:
        logger.error(f"Failed to send edited message for draft #{draft_id}: {e}")

# -------------------------------------------------------------------------
# Entrypoint
# -------------------------------------------------------------------------

def main():
    init_db()
    warnings = validate_config()
    if warnings:
        logger.warning("Configuration checklist:")
        for w in warnings:
            logger.warning(f" - {w}")
        logger.info("Please fill in your .env file with the tokens specified in .env.example")

    if not settings.SLACK_APP_TOKEN or settings.SLACK_APP_TOKEN.startswith("xapp-your"):
        logger.error("Cannot start Socket Mode without a valid SLACK_APP_TOKEN.")
        return

    # Start background poller for personal 1-on-1 DMs (if user token is present)
    from user_poller import UserDMPoller
    poller = UserDMPoller()
    poller.start(process_incoming_for_approval)

    # Start optional cloud HTTP health check server if PORT is defined (e.g. Render, Railway, Cloud Run)
    port_env = os.environ.get("PORT")
    if port_env:
        try:
            from health_server import start_health_server
            start_health_server(int(port_env))
        except Exception as e:
            logger.warning(f"Failed to start health server: {e}")

    logger.info("⚡ Starting Slack Auto-Reply Bot in Socket Mode...")
    handler = SocketModeHandler(app, settings.SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    main()
