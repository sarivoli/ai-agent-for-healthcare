"""
Text Normalization & LLM Payload Extractor Utility.
Safely extracts and cleans plain-text and Markdown content from LLM response messages,
handling string, list of dict parts (e.g. Gemini 3.6 Flash / LangChain multimodal/stream chunks),
and nested envelope objects, while preventing JSON / Python repr string leakage.
"""

from typing import Any, List, Dict, Union
import ast
import json
import re


def extract_message_text(content: Any) -> str:
    """
    Extracts unified plain text/Markdown from an LLM response payload.
    
    Handles:
    1. Plain string (e.g. "Here is the summary...")
    2. Stringified Python list or JSON (e.g. "[{'type': 'text', 'text': '...'}]")
    3. List of content parts/chunks (e.g. [{'type': 'text', 'text': '...'}, {'type': 'text', 'text': '...'}])
    4. BaseMessage or AIMessage instances
    5. Strips base64/cryptographic signatures, thinking tags, or raw token metadata envelopes.
    """
    if content is None:
        return ""

    # If it's a message object with a content attribute
    if hasattr(content, "content"):
        content = getattr(content, "content")

    # If already a string, check if it's accidentally a serialized Python list or JSON
    if isinstance(content, str):
        trimmed = content.strip()
        # Detect Python repr or JSON array of dicts with 'text' or 'type'
        if (
            (trimmed.startswith("[{'") or trimmed.startswith('[{"') or trimmed.startswith("[{ '") or trimmed.startswith('[{ "'))
            and trimmed.endswith("]")
        ):
            try:
                parsed = ast.literal_eval(trimmed)
                if isinstance(parsed, list):
                    return extract_message_text(parsed)
            except Exception:
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, list):
                        return extract_message_text(parsed)
                except Exception:
                    # Regex fallback to extract 'text' properties
                    parts = re.findall(r"['\"]text['\"]\s*:\s*['\"]((?:\\.|[^'\"])*)['\"]", trimmed)
                    if parts:
                        return "".join(parts).replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")
        return content

    # If it is a list of parts (standard in LangChain for Gemini / Claude / GPT multimodal)
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                # Extract text field if present
                if "text" in item and item["text"] is not None:
                    parts.append(str(item["text"]))
                elif "content" in item and item["content"] is not None:
                    parts.append(str(item["content"]))
                # If there's an 'extras' or 'signature' or other non-text field, ignore it!
            elif isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(str(getattr(item, "text")))
            else:
                parts.append(str(item))
        # Concatenate parts seamlessly without inserting newline in the middle of words/tables
        return "".join(parts)

    return str(content)
