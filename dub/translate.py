"""Dublaj için LLM ile çeviri (OpenRouter üzerinden, model seçilebilir).

Segmentler tek tek değil, BATCH_SIZE'lık bloklar hâlinde çevrilir; model cümlenin öncesini ve sonrasını
görerek doğal bir çeviri yapabilsin diye. Tutarlılık için iki aşama var:

1. Analiz: bütün döküm bir kez gönderilir. Model konuyu, üslubu, konuşmacıları ve sözlüğü çıkarır.
   Sözlük: özel isimler, marka/program adları, terimler ve çevrilmeden kalması gereken ifadeler
   (ör. İngilizce dersinde öğretilen deyim) ile her birinin hedef dildeki karşılığı.
2. Çeviri: her blokla birlikte analiz özeti, sözlük, önceki blokların son birkaç satırı (kaynak + çeviri)
   ve sonraki birkaç satır (yalnız kaynak) gönderilir. Model yeni bir terim karar verirse onu döndürür,
   sözlüğe eklenir ve sonraki bloklarda kullanılır.

Her satıra konuşma süresi de verilir; çeviri o sürede söylenebilecek uzunlukta tutulur.
"""
from __future__ import annotations

import json
import re
import time

import requests

from dub.common import load_api_key

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

LANG_NAMES = {"tr": "Turkish", "en": "English", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
              "pt": "Portuguese", "ru": "Russian", "ar": "Arabic", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
              "nl": "Dutch", "pl": "Polish", "hi": "Hindi"}


class OpenRouterChat:
    """OpenRouter chat/completions için küçük istemci: JSON yanıt, yeniden deneme, kullanım ve maliyet toplamı."""

    def __init__(self, model: str, api_key: str | None = None, temperature: float = 0.3,
                 timeout: int = 300, retries: int = 2):
        self.model = model
        self.api_key = api_key or load_api_key()
        self.temperature = temperature
        self.timeout = timeout
        self.retries = retries
        self.reset_usage()

    def reset_usage(self) -> None:
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "latency_sec": 0.0}

    def json(self, system: str, user: str, schema: dict | None = None) -> dict:
        """schema verilirse yapılandırılmış çıktı (json_schema, strict) istenir. Sadece json_object modunda
        bazı sağlayıcılar önce bozuk bir JSON yazıp ardından "düzeltme" ekliyordu."""
        fmt = ({"type": "json_schema", "json_schema": {"name": "response", "strict": True, "schema": schema}}
               if schema else {"type": "json_object"})
        body = {"model": self.model, "temperature": self.temperature, "usage": {"include": True},
                "response_format": fmt,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        last_err = None
        for attempt in range(self.retries + 1):
            t0 = time.time()
            try:
                r = requests.post(CHAT_URL, headers={"Authorization": f"Bearer {self.api_key}"}, json=body,
                                  timeout=self.timeout)
                j = r.json()
            except (requests.RequestException, ValueError) as e:
                last_err = str(e)
            else:
                self._count(j.get("usage") or {}, time.time() - t0)
                if r.status_code == 200 and j.get("choices"):
                    try:
                        return parse_json(j["choices"][0]["message"]["content"])
                    except ValueError as e:
                        last_err = f"JSON çözülemedi: {e}"
                else:
                    last_err = f"HTTP {r.status_code}: {j.get('error')}"
            if attempt < self.retries:
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"LLM çağrısı başarısız ({self.model}): {last_err}")

    def _count(self, usage: dict, latency: float) -> None:
        self.usage["calls"] += 1
        self.usage["prompt_tokens"] += usage.get("prompt_tokens") or 0
        self.usage["completion_tokens"] += usage.get("completion_tokens") or 0
        self.usage["cost_usd"] = round(self.usage["cost_usd"] + float(usage.get("cost") or 0), 6)
        self.usage["latency_sec"] = round(self.usage["latency_sec"] + latency, 2)


def parse_json(text: str) -> dict:
    """Modelin yanıtından JSON nesnesini çıkarır (```json bloklarına ve öncesindeki metne dayanıklı)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b <= a:
            raise ValueError(text[:200])
        return json.loads(text[a:b + 1])


def _obj(**props) -> dict:
    """strict json_schema nesnesi: bütün alanlar zorunlu, fazlası yasak."""
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_STR = {"type": "string"}
TERMS_SCHEMA = {"type": "array", "items": _obj(source=_STR, target=_STR, note=_STR)}
ANALYZE_SCHEMA = _obj(summary=_STR, tone=_STR,
                      speakers={"type": "array", "items": _obj(label=_STR, description=_STR)},
                      glossary=TERMS_SCHEMA)
TRANSLATE_SCHEMA = _obj(translations={"type": "array", "items": _obj(id={"type": "integer"}, text=_STR)},
                        new_terms=TERMS_SCHEMA)


ANALYZE_SYSTEM = """You prepare a transcript for professional dubbing from {src} into {tgt}.
Read the whole transcript and return a JSON object:
{{
  "summary": "2-4 sentences: what the content is, genre, setting",
  "tone": "register and style to keep in {tgt} (formal/casual, humor, slang, catchphrases)",
  "speakers": [{{"label": "<speaker label>", "description": "who they are, how they talk, how they address others"}}],
  "glossary": [
    {{"source": "term as written in the transcript", "target": "what to say in {tgt}", "note": "why"}}
  ]
}}
Glossary: person names, brand/product/show names, places, technical terms, recurring phrases or jokes, and any
words that must stay untranslated (e.g. an English expression being taught in a language lesson keeps its
English form). "target" equals "source" when it must stay as-is. Include only items that matter for consistency."""

TRANSLATE_SYSTEM = """You are a dubbing translator from {src} into {tgt}. The translation will be spoken by a
voice actor over the original video, so it must sound like natural, idiomatic spoken {tgt}, as a native speaker
would say it in that situation, not a literal rendering.

Rules:
- Translate meaning, intent, humor and tone. Use idioms and colloquial forms of {tgt} where the source is casual.
- Follow the glossary exactly. Keep names and terms consistent with earlier lines.
- Timing: each line has the seconds available. Keep the translation speakable within that time at a natural pace;
  prefer shorter phrasing over dropping meaning. Never merge, split or reorder lines.
- Hesitations, fillers and cut-off words (um, eee, "bütün--") may be rendered with a natural {tgt} equivalent
  or dropped if they carry no meaning.
- Lines in "context_before" and "context_after" are for context only; do not translate them.
- If you decide on the {tgt} form of a new name, term or recurring phrase that is not in the glossary, add it to
  "new_terms".

Return a JSON object:
{{"translations": [{{"id": <line id>, "text": "<{tgt} translation>"}}, ...],
  "new_terms": [{{"source": "...", "target": "...", "note": "..."}}]}}
Return exactly one translation for every id in "lines"."""


class LLMTranslator:
    def __init__(self, model: str = "anthropic/claude-sonnet-5.5", batch_size: int = 20,
                 context_before: int = 5, context_after: int = 3, api_key: str | None = None):
        self.llm = OpenRouterChat(model, api_key)
        self.batch_size = batch_size
        self.context_before = context_before
        self.context_after = context_after

    @property
    def model(self) -> str:
        return self.llm.model

    def analyze(self, segments: list[dict], src: str, tgt: str) -> dict:
        system = ANALYZE_SYSTEM.format(src=LANG_NAMES.get(src, src), tgt=LANG_NAMES.get(tgt, tgt))
        transcript = "\n".join(f"[{s['speaker']}] {s['text']}" for s in segments)
        out = self.llm.json(system, transcript, ANALYZE_SCHEMA)
        out.setdefault("glossary", [])
        return out

    def translate(self, segments: list[dict], src: str, tgt: str, analysis: dict | None = None,
                  on_batch=None) -> dict:
        """segments: [{"id", "speaker", "duration", "text"}]. Döner: {"translations": {id: metin},
        "glossary": [...], "batches": [...]}. on_batch(sonuç) her bloktan sonra çağrılır (ara kayıt için)."""
        analysis = analysis or self.analyze(segments, src, tgt)
        glossary = list(analysis.get("glossary", []))
        system = TRANSLATE_SYSTEM.format(src=LANG_NAMES.get(src, src), tgt=LANG_NAMES.get(tgt, tgt))
        done: dict[int, str] = {}
        batches = []

        for b in range(0, len(segments), self.batch_size):
            lines = segments[b:b + self.batch_size]
            before = segments[max(0, b - self.context_before):b]
            after = segments[b + len(lines):b + len(lines) + self.context_after]
            payload = {
                "summary": analysis.get("summary"), "tone": analysis.get("tone"),
                "speakers": analysis.get("speakers"), "glossary": glossary,
                "context_before": [{"speaker": s["speaker"], "source": s["text"], "translation": done.get(s["id"])}
                                   for s in before],
                "lines": [{"id": s["id"], "speaker": s["speaker"], "seconds": round(s["duration"], 1),
                           "source": s["text"]} for s in lines],
                "context_after": [{"speaker": s["speaker"], "source": s["text"]} for s in after],
            }
            got = self._translate_batch(system, payload, {s["id"] for s in lines})
            done.update(got["translations"])
            known = {g["source"].lower() for g in glossary}
            new = [t for t in got.get("new_terms") or [] if t.get("source") and t["source"].lower() not in known]
            glossary += new
            batches.append({"ids": [s["id"] for s in lines], "new_terms": new, "retried": got["retried"]})
            if on_batch:
                on_batch({"translations": done, "glossary": glossary, "batches": batches})

        return {"translations": done, "glossary": glossary, "batches": batches}

    def _translate_batch(self, system: str, payload: dict, ids: set[int]) -> dict:
        """Bloğu çevirir; eksik ya da fazla id dönerse eksikleri bir kez daha ister."""
        out = self.llm.json(system, json.dumps(payload, ensure_ascii=False, indent=1), TRANSLATE_SCHEMA)
        got = {int(t["id"]): t["text"].strip() for t in out.get("translations", [])
               if str(t.get("id", "")).isdigit() and int(t["id"]) in ids and t.get("text")}
        retried = sorted(ids - got.keys())
        if retried:
            payload = dict(payload, lines=[ln for ln in payload["lines"] if ln["id"] in retried])
            again = self.llm.json(system, json.dumps(payload, ensure_ascii=False, indent=1), TRANSLATE_SCHEMA)
            got.update({int(t["id"]): t["text"].strip() for t in again.get("translations", [])
                        if str(t.get("id", "")).isdigit() and int(t["id"]) in ids and t.get("text")})
            missing = sorted(ids - got.keys())
            if missing:
                raise RuntimeError(f"LLM şu satırları çevirmedi: {missing}")
        return {"translations": got, "new_terms": out.get("new_terms"), "retried": retried}
