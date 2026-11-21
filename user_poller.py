import time
import logging
import threading
from typing import Optional, Callable
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import settings
from db import is_message_already_drafted

logger = logging.getLogger("user_poller")

class UserDMPoller:
    """
    Background worker that monitors Anuj's personal 1-on-1 Slack DMs
    using the User OAuth Token and triggers AI drafting for incoming messages.
    """

    def __init__(
        self,
        user_token: Optional[str] = None,
        bot_token: Optional[str] = None,
        approver_user_id: Optional[str] = None,
        poll_interval: int = 5
    ):
        self.user_token = user_token or settings.SLACK_USER_TOKEN
        self.bot_token = bot_token or settings.SLACK_BOT_TOKEN
        self.approver_user_id = approver_user_id or settings.SLACK_APPROVER_USER_ID
        self.poll_interval = poll_interval
        
        self.user_client = WebClient(token=self.user_token) if self.user_token else None
        self.bot_client = WebClient(token=self.bot_token) if self.bot_token else None
        
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.missing_scope_warned = False
        self.bot_user_id: Optional[str] = None
        if self.bot_client:
            try:
                auth = self.bot_client.auth_test()
                self.bot_user_id = auth.get("user_id")
            except Exception as e:
                logger.debug(f"Could not fetch bot_user_id: {e}")

        # Look back up to 1 hour (3600s) on startup to catch recent unreplied chats
        self.start_timestamp = str(time.time() - 3600)

    def start(self, callback_fn: Callable):
        if not self.user_client:
            logger.info("No SLACK_USER_TOKEN provided; personal DM poller disabled.")
            return

        self.callback_fn = callback_fn
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="user-dm-poller")
        self._thread.start()
        logger.info("👀 Personal DM poller started (monitoring incoming chats every 5s)...")

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            try:
                self._poll_once()
            except Exception as e:
                logger.debug(f"Poller loop exception: {e}")
            time.sleep(self.poll_interval)

    def _poll_once(self):
        if not self.user_client:
            return

        try:
            res = self.user_client.conversations_list(types="im", limit=50)
        except SlackApiError as e:
            if "missing_scope" in str(e) and not self.missing_scope_warned:
                logger.warning(
                    "⚠️  To monitor personal 1-on-1 DMs, your User Token needs 'im:read' and 'im:history' scopes.\n"
                    "    Add them at: api.slack.com/apps -> OAuth & Permissions -> User Token Scopes -> Reinstall App."
                )
                self.missing_scope_warned = True
            return

        for ch in res.get("channels", []):
            ch_id = ch.get("id")
            other_user = ch.get("user")
            
            # Skip DM with self or the bot
            if other_user == self.approver_user_id or (self.bot_user_id and other_user == self.bot_user_id):
                continue

            try:
                history = self.user_client.conversations_history(channel=ch_id, limit=2)
                messages = history.get("messages", [])
                if not messages:
                    continue

                latest_msg = messages[0]
                msg_ts = latest_msg.get("ts", "0")
                sender = latest_msg.get("user")
                text = latest_msg.get("text", "").strip()

                # If Anuj was the last person to speak in this chat, he already replied, so skip
                if sender == self.approver_user_id:
                    continue

                # Process if:
                # 1. Newer than start timestamp (within 1h)
                # 2. Sent by the other person (not Anuj)
                # 3. Not a bot
                # 4. Contains text
                # 5. Not already drafted in SQLite
                if (
                    float(msg_ts) > float(self.start_timestamp)
                    and not latest_msg.get("bot_id")
                    and text
                    and not is_message_already_drafted(msg_ts)
                ):
                    logger.info(f"📨 New personal DM detected from {sender} in {ch_id}: '{text}'")
                    self.callback_fn(
                        client=self.bot_client,
                        sender_id=sender,
                        channel_id=ch_id,
                        message_ts=msg_ts,
                        thread_ts=latest_msg.get("thread_ts"),
                        incoming_text=text,
                        is_dm=True
                    )
            except SlackApiError:
                pass
