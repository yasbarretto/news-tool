"""
qa.py — automated QA. Claude reviews the video's script against the source
headlines and returns a pass/warn report matching the dashboard's four checks.
"""
import os, json
import anthropic

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def run_auto_qa(script, headlines):
    prompt = f"""You are the automated QA reviewer for an AI news video, checking it BEFORE it is published.

SOURCE HEADLINES the video was built from:
{json.dumps(headlines[:15], indent=2)}

THE VIDEO SCRIPT (anchor speech + on-screen headlines + b-roll prompts):
{json.dumps(script, indent=2)}

Return ONLY JSON (no markdown) in exactly this shape:
{{
  "facts":  "ok",
  "visual": "ok",
  "brand":  "ok",
  "audio":  "ok",
  "notes": []
}}

Set a field to "warn" (and add a short note) if you find a problem:
- facts:  claims not supported by the source headlines, invented numbers, or wrong proper nouns (e.g. "open AI" when it means the company "OpenAI").
- visual: b-roll prompts that name real people, show logos/readable text, or depict sensitive/violent content.
- brand:  unprofessional, offensive, or potentially defamatory tone.
- audio:  numbers/tickers not spelled out for clean text-to-speech, or text likely to mispronounce.
Each note: one short, specific sentence. Empty notes list if everything passes."""
    msg = _client.messages.create(
        model="claude-sonnet-4-6", max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text[text.find("{"):text.rfind("}") + 1])
