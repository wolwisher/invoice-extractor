"""LLM clients. Anything with an `extract(text, json_schema) -> dict` method works, which keeps
the pipeline testable without network calls and lets you swap providers."""
import json
import os
import urllib.request

PROMPT = """You extract data from business documents.
Return ONLY a JSON object that matches this JSON Schema:
{schema}

Rules:
- Copy values exactly as they appear in the document. Dates as YYYY-MM-DD. Numbers without currency symbols.
- If a value is not clearly present, use null. Never guess or calculate a value that isn't written.

Document:
\"\"\"
{text}
\"\"\""""


class OpenAIClient:
    """Calls the OpenAI Chat Completions API in JSON mode using only the standard library."""

    def __init__(self, api_key=None, model=None, timeout=60):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set OPENAI_API_KEY to use the OpenAI client")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout

    def extract(self, text: str, json_schema: dict) -> dict:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": PROMPT.format(schema=json.dumps(json_schema), text=text[:15000])}],
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.load(resp)
        return json.loads(payload["choices"][0]["message"]["content"])
