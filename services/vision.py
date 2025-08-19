import base64, json, mimetypes, os
from typing import Dict, List

MODEL_DEFAULT = os.getenv("MODEL", "gpt-4o-mini")
try:
    from openai import OpenAI
    client = OpenAI()
except Exception:
    client = None

PROMPT = """You are labeling the contents of a garage storage box from one photo.
Return STRICT JSON only:
{
  "box_name": "short, sensible name",
  "items": [{"name": "string", "confidence": 0.0}],
  "notes": "one or two short helpful notes"
}
- Use 0.00–1.00 for confidence.
- Combine duplicates; keep names simple and generic.
- If unsure, include lower confidence items instead of omitting everything.
"""

def _encode_image(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def detect_items_json(image_path: str) -> Dict:
    if not client:
        return {"box_name": "Unlabeled Box", "items": [], "notes": "Vision disabled."}
    data_url = _encode_image(image_path)
    resp = client.chat.completions.create(
        model=MODEL_DEFAULT,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": [
                {"type":"text","text": PROMPT},
                {"type":"image_url","image_url":{"url": data_url}},
            ]},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"box_name": "Unlabeled Box", "items": [], "notes": raw[:200]}
    name = (parsed.get("box_name") or "Unlabeled Box").strip()
    items = []
    for it in (parsed.get("items") or []):
        n = (it.get("name") or "").strip()
        if not n:
            continue
        try:
            c = float(it.get("confidence", 0))
        except Exception:
            c = 0.0
        items.append({"name": n, "confidence": max(0.0, min(1.0, c))})
    return {"box_name": name, "items": items, "notes": (parsed.get("notes") or "")[:300]}
