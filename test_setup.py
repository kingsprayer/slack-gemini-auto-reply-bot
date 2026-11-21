import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Settings, validate_config
from db import init_db, create_draft, get_draft, update_draft_status, list_pending_drafts
from ai_engine import AIEngine
from blocks import build_approval_blocks

class TestSlackAutoReplySetup(unittest.TestCase):

    def setUp(self):
        self.test_db_path = str(Path(__file__).resolve().parent / "test_drafts.db")
        init_db(self.test_db_path)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_database_crud(self):
        """Verify that drafts are correctly created, queried, and updated in SQLite."""
        draft = create_draft(
            channel_id="D123456",
            message_ts="1700000001.000100",
            sender_id="U999999",
            sender_name="Alice Smith",
            incoming_text="Hey, do you have time for a quick sync at 3pm?",
            drafted_reply="Hi Alice, 3pm works great for me. Let's connect then!",
            db_path=self.test_db_path
        )
        self.assertIsNotNone(draft)
        self.assertEqual(draft["sender_name"], "Alice Smith")
        self.assertEqual(draft["status"], "PENDING")

        pending = list_pending_drafts(self.test_db_path)
        self.assertEqual(len(pending), 1)

        # Update status
        update_draft_status(draft["id"], status="SENT", final_reply="Approved and sent text", db_path=self.test_db_path)
        updated = get_draft(draft["id"], self.test_db_path)
        self.assertEqual(updated["status"], "SENT")
        self.assertEqual(updated["final_reply"], "Approved and sent text")

        # Now pending should be 0
        self.assertEqual(len(list_pending_drafts(self.test_db_path)), 0)

    def test_approval_blocks_structure(self):
        """Verify that Block Kit structure contains required sections and action buttons."""
        blocks = build_approval_blocks(
            draft_id=42,
            sender_id="U12345",
            sender_name="Bob",
            channel_id="D98765",
            incoming_text="Can you review the PR?",
            drafted_reply="Sure Bob, reviewing it now.",
            is_dm=True
        )
        self.assertTrue(any(b.get("type") == "header" for b in blocks))
        
        # Check action buttons
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        self.assertEqual(len(action_blocks), 1)
        action_ids = [el.get("action_id") for el in action_blocks[0].get("elements", [])]
        self.assertIn("approve_and_send", action_ids)
        self.assertIn("open_edit_modal", action_ids)
        self.assertIn("dismiss_draft", action_ids)

    def test_ai_engine_fallback(self):
        """Verify AIEngine produces clean fallback text when API key is not configured."""
        engine = AIEngine(api_key="")
        reply = engine.generate_draft(
            incoming_message="Hello!",
            sender_name="Charlie"
        )
        self.assertIn("Charlie", reply)
        self.assertIsInstance(reply, str)

if __name__ == "__main__":
    unittest.main()
