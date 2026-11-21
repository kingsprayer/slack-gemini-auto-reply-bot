from typing import List, Dict, Any

def build_approval_blocks(
    draft_id: int,
    sender_id: str,
    sender_name: str,
    channel_id: str,
    incoming_text: str,
    drafted_reply: str,
    is_dm: bool = True
) -> List[Dict[str, Any]]:
    """Builds interactive Slack Block Kit message with approval controls."""
    channel_reference = "Direct Message" if is_dm else f"<#{channel_id}>"
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔔 Pending Approval: Incoming Slack Message",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*From:* *{sender_name}* (<@{sender_id}>)\n*Location:* {channel_reference}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Original Message:*\n> {incoming_text}"
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Drafted Reply (by Gemini):*\n```{drafted_reply}```"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve & Send", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_and_send",
                    "value": str(draft_id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Edit Draft", "emoji": True},
                    "action_id": "open_edit_modal",
                    "value": str(draft_id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Dismiss", "emoji": True},
                    "style": "danger",
                    "action_id": "dismiss_draft",
                    "value": str(draft_id)
                }
            ]
        }
    ]
