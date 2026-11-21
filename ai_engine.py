import logging
from typing import List, Dict, Optional
from config import settings

logger = logging.getLogger("ai_engine")

class AIEngine:
    """Handles drafting responses using the Google Gemini API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.client = None
        
        if self.api_key and not self.api_key.startswith("your-gemini"):
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI Client: {e}")

    def generate_draft(
        self,
        incoming_message: str,
        sender_name: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        Generates a context-aware draft reply for an incoming Slack message.
        """
        if not self.client:
            # Fallback if API key has not yet been supplied
            return (
                f"Hi {sender_name}, thanks for reaching out. "
                "I have received your message and will get back to you shortly!"
            )

        system_instruction = custom_instructions or settings.AI_PERSONA_PROMPT

        # Build conversation context
        context_parts = [
            f"You are drafting a Slack reply on behalf of your user to {sender_name}."
        ]
        
        if conversation_history:
            context_parts.append("Recent conversation history (oldest to newest):")
            for msg in conversation_history[-6:]:
                speaker = msg.get("speaker", "Unknown")
                text = msg.get("text", "")
                context_parts.append(f"- {speaker}: {text}")

        context_parts.append(f"\nNew incoming message from {sender_name}:\n\"{incoming_message}\"")
        context_parts.append(
            "\nTask: Write ONLY the exact response text to send. "
            "Do NOT include greetings like 'Subject:' or meta comments like 'Here is a draft:'. "
            "Write in first-person as the user."
        )

        prompt = "\n".join(context_parts)

        candidate_models = [self.model, "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"]
        # Deduplicate while preserving order
        seen = set()
        models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

        from google.genai import types
        last_error = None
        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                    )
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_error = e
                logger.warning(f"Model {model_name} failed: {e}. Trying fallback model...")

        logger.error(f"All Gemini models failed. Last error: {last_error}")
        return (
            f"Hi {sender_name}, thanks for reaching out. "
            "I received your message and will review it as soon as possible."
        )

ai_engine = AIEngine()
