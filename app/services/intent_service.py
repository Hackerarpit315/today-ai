import re
from typing import Any
from app.schemas.intent import IntentRequest, IntentResponse


def _extract_entities(text: str) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    urls = re.findall(r"https?://[^\s]+", text)
    if urls:
        entities["urls"] = urls
    organizations = ["Google", "Microsoft", "Apple", "Amazon", "OpenAI", "GitHub", "AKTU", "NPTEL", "TryHackMe"]
    found_orgs = [n for n in organizations if re.search(rf"\b{re.escape(n)}\b", text, re.I)]
    if found_orgs:
        entities["organizations"] = found_orgs
    locations = ["Bareilly", "Delhi", "Lucknow", "Meerut", "Noida", "India"]
    found_locations = [n for n in locations if re.search(rf"\b{re.escape(n)}\b", text, re.I)]
    if found_locations:
        entities["locations"] = found_locations
    time_match = re.search(r"\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:am|pm)?\b", text, re.I)
    if time_match:
        entities["clock_time"] = time_match.group(0)
    return entities


def _time_reference(text: str) -> str | None:
    lower = text.lower()
    if re.search(r"\b(tomorrow|kal|कल)\b", text, re.I):
        return "tomorrow"
    if re.search(r"\b(today|aaj|आज)\b", text, re.I):
        return "today"
    if re.search(r"\b(yesterday|kal tha|kal tha)\b", lower):
        return "yesterday"
    if re.search(r"\b(parso|परसों)\b", text, re.I):
        return "day_after_tomorrow_or_before"
    if "next week" in lower or "agle hafte" in lower or "अगले हफ्ते" in text:
        return "next_week"
    return None


def _classify(text: str) -> tuple[str, float]:
    lower = text.lower().strip()
    if not lower:
        return "unknown", 0.0
    reminder = ["remind me", "reminder", "yaad dilana", "yaad dila dena", "याद दिलाना", "रिमाइंडर"]
    research = ["research", "research karo", "find out", "search", "जानकारी खोज", "research करो", "pata karo", "पता करो"]
    command = ["open ", "close ", "send ", "delete ", "start ", "stop ", "kholo", "bhejo", "hatao", "chalao", "खोलो", "भेजो", "हटाओ"]
    task = ["need to", "have to", "want to", "jana hai", "karna hai", "bharna hai", "banana hai", "submit karna", "complete karna", "करना है", "जाना है", "भरना है", "बनाना है", "जमा करना है"]
    info = ["what is", "what are", "kaise", "kya hai", "batao", "explain", "जानकारी", "क्या है", "बताओ", "समझाओ"]
    if any(x in lower for x in reminder): return "reminder", 0.95
    if any(x in lower for x in research): return "research", 0.95
    if "?" in text or lower.startswith(("what ", "why ", "when ", "where ", "who ", "how ")): return "question", 0.95
    if any(x in lower for x in command): return "command", 0.90
    if any(x in lower for x in task): return "task", 0.95
    if any(x in lower for x in info): return "information_request", 0.90
    return "unknown", 0.50


def process_intent(payload: IntentRequest) -> IntentResponse:
    intent, confidence = _classify(payload.content)
    return IntentResponse(request_id=payload.request_id, intent=intent, goal=payload.content.strip(), entities=_extract_entities(payload.content), time_reference=_time_reference(payload.content), confidence=confidence)
