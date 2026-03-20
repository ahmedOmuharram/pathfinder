import json

from openai import AsyncOpenAI

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONObject


async def _generate_name_and_description(
    *, strategy_compact: JSONObject, model: str
) -> tuple[str, str]:
    settings = get_settings()

    compact_json = json.dumps(strategy_compact, ensure_ascii=False)
    prompt = f"""You are generating metadata for a public strategy example.

Return STRICT JSON with keys:
- name: short, human-friendly title (max 80 chars)
- description: 3-8 sentences. Must be descriptive but MUST NOT be a step-by-step recipe.
  It MUST explicitly include the requirements/criteria represented in the strategy, including:
  - all searches used (searchName)
  - all parameter constraints used for each step (parameters key/value pairs)
  - boolean operators (INTERSECT/UNION/MINUS/RMINUS/COLOCATE) when present

Do not write "Step 1", "Step 2" or numbered steps.
Do not include markdown.

Strategy (compact JSON):
{compact_json}
"""

    async with AsyncOpenAI(api_key=settings.openai_api_key or None) as client:
        resp = await client.chat.completions.create(
            model=model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": prompt},
            ],
        )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        msg = "Empty LLM response"
        raise RuntimeError(msg)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise
    name = str(data.get("name") or "").strip()
    desc = str(data.get("description") or "").strip()
    if not name or not desc:
        msg = "LLM returned empty name/description"
        raise RuntimeError(msg)
    return name, desc
