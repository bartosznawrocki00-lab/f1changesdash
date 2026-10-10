"""PDF -> tekst -> lista zmian (JSON) przez API Claude'a."""
import io
import json
import os

import pdfplumber

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

SYSTEM = (
    "You extract car upgrade information from FIA Formula 1 'car presentation' documents. "
    "Return ONLY a JSON array, no markdown, no commentary. Each item: "
    '{"team": str, "component": str, "description": str}. '
    "One item per distinct changed component (e.g. 'Front wing', 'Floor', 'Rear wing', 'Cooling'). "
    "Use the team's short name (e.g. 'Ferrari', 'McLaren'). "
    "Keep 'description' to one short sentence in your own words. "
    "If the document lists no upgrades, return []. Never invent anything not present in the text."
)


def pdf_to_text(pdf_bytes: bytes) -> str:
    parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
            for table in page.extract_tables():
                for row in table:
                    parts.append(" | ".join(c or "" for c in row))
    return "\n".join(parts)


def extract_upgrades(text: str) -> list[dict]:
    import anthropic  # import tutaj, żeby dashboard działał bez klucza API

    client = anthropic.Anthropic()  # czyta ANTHROPIC_API_KEY ze środowiska
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": text[:60000]}],
    )
    raw = resp.content[0].text
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"Model nie zwrócił JSON-a: {raw[:200]}")
    items = json.loads(raw[start : end + 1])
    return [
        {"team": i["team"], "component": i["component"], "description": i.get("description", "")}
        for i in items
        if isinstance(i, dict) and i.get("team") and i.get("component")
    ]
