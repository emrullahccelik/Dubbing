"""run_stt çıktılarını karşılaştırır: ikili WER, referansa göre farklar, kelime zaman damgası uyumu.

Kullanım:
    .venv/bin/python -m stt.compare --name test_en [--reference elevenlabs]
    .venv/bin/python -m stt.compare --name test_tr --lang tr

Referans metin olarak bir model anahtarı verilir (varsayılan: elevenlabs). Elde resmi birebir
döküm olmadığında bu bir "uzlaşı referansı"dır; farkların elle kontrol edilmesi gerekir.
Çıktı: outputs/stt/<name>/comparison.json
"""
from __future__ import annotations

import argparse
import difflib
import itertools
import json
import re

import jiwer
import numpy as np

from stt.common import ROOT

# Yazım farklarını hata saymamak için eşitlemeler
SPELLING = {"fei fei": "feifei", "faye faye": "feifei", "programme": "program"}


TR_ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
TR_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def tr_number(n: int) -> str:
    """Türkçe sayı okunuşu (0 - 999.999); 'bin' ve 'yüz' öncesinde 'bir' söylenmez."""
    if n == 0:
        return "sıfır"
    parts = []
    thousands, rest = divmod(n, 1000)
    if thousands:
        parts += ([] if thousands == 1 else [tr_number(thousands)]) + ["bin"]
    hundreds, rest = divmod(rest, 100)
    if hundreds:
        parts += ([] if hundreds == 1 else [TR_ONES[hundreds]]) + ["yüz"]
    tens, ones = divmod(rest, 10)
    parts += [x for x in (TR_TENS[tens], TR_ONES[ones]) if x]
    return " ".join(parts)


def norm(text: str, lang: str = "en") -> str:
    if lang == "tr":
        # Türkçe büyük/küçük harf: İ→i, I→ı; rakamları okunuşa çevir (1500 → bin beş yüz)
        text = text.replace("İ", "i").replace("I", "ı")
        text = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", text)
        text = re.sub(r"\d+", lambda m: tr_number(int(m.group())) if int(m.group()) < 10**6 else m.group(), text)
    t = text.lower()
    for a, b in SPELLING.items():
        t = t.replace(a, b)
    t = re.sub(r"[^\w' ]", " ", t)
    t = re.sub(r"(?<!\w)'|'(?!\w)", " ", t)  # tırnak olarak kullanılan kesme işaretleri
    return re.sub(r"\s+", " ", t).strip()


def speaker_agreement(a: list[dict], b: list[dict], step: float = 0.1) -> dict:
    """İki modelin konuşmacı etiketlerini 100 ms çerçevelerde karşılaştırır.
    Etiket isimleri modelden modele farklı olduğundan en iyi eşleme (permütasyon) aranır."""
    def frames(words, n):
        lab = np.full(n, -1)
        ids = sorted({str(w["speaker"]) for w in words if w.get("speaker") is not None})
        for w in words:
            if w.get("speaker") is None:
                continue
            i, j = int(w["start"] / step), int(w["end"] / step)
            lab[i:max(j, i + 1)] = ids.index(str(w["speaker"]))
        return lab, len(ids)
    end = max(w["end"] for w in a + b)
    n = int(end / step) + 1
    fa, na = frames(a, n)
    fb, nb = frames(b, n)
    both = (fa >= 0) & (fb >= 0)
    k = max(na, nb)
    best = 0.0
    for perm in itertools.permutations(range(k), na):
        best = max(best, float((np.array(perm)[fa[both]] == fb[both]).mean()))
    return {"agreement": round(best, 4), "overlap_sec": round(both.sum() * step, 1)}


def word_key(w: dict) -> str:
    return re.sub(r"[^\w']", "", w["word"].lower())


def timing_agreement(a: list[dict], b: list[dict]) -> dict:
    sm = difflib.SequenceMatcher(a=[word_key(w) for w in a], b=[word_key(w) for w in b], autojunk=False)
    ds = []
    for blk in sm.get_matching_blocks():
        ds += [abs(a[blk.a + i]["start"] - b[blk.b + i]["start"]) for i in range(blk.size)]
    ds = np.array(ds)
    return {"matched_words": len(ds), "start_mean_ms": round(ds.mean() * 1000),
            "start_p95_ms": round(np.percentile(ds, 95) * 1000), "start_max_ms": round(ds.max() * 1000)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="test_en")
    ap.add_argument("--reference", default="elevenlabs")
    ap.add_argument("--lang", default="en", help="tr: Türkçe harf ve sayı normalizasyonu")
    args = ap.parse_args()

    base = ROOT / "outputs" / "stt" / args.name
    res = {p.parent.name: json.loads(p.read_text()) for p in sorted(base.glob("*/transcript.json"))}
    texts = {k: norm(r["text"], args.lang) for k, r in res.items()}
    ref = texts[args.reference].split()

    out = {"reference": args.reference, "pairwise_wer": {}, "mean_wer_to_others": {}, "vs_reference": {},
           "timing": {}, "speaker_agreement": {}, "word_stats": {}}
    for a, b in itertools.combinations(res, 2):
        out["pairwise_wer"][f"{a}~{b}"] = round(jiwer.wer(texts[a], texts[b]), 4)
    for k in res:
        others = [v for pair, v in out["pairwise_wer"].items() if k in pair.split("~")]
        out["mean_wer_to_others"][k] = round(float(np.mean(others)), 4) if others else None
    for k, t in texts.items():
        hyp = t.split()
        sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
        diffs = [{"op": op, "ref": " ".join(ref[i1:i2]), "hyp": " ".join(hyp[j1:j2])}
                 for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
        out["vs_reference"][k] = {"wer": round(jiwer.wer(texts[args.reference], t), 4), "diffs": diffs}
    timed = [k for k, r in res.items() if r["words"]]
    for a, b in itertools.combinations(timed, 2):
        out["timing"][f"{a}~{b}"] = timing_agreement(res[a]["words"], res[b]["words"])
    diarized = [k for k, r in res.items() if r.get("has_speakers")]
    for a, b in itertools.combinations(diarized, 2):
        out["speaker_agreement"][f"{a}~{b}"] = speaker_agreement(res[a]["words"], res[b]["words"])
    for k in timed:
        w = res[k]["words"]
        out["word_stats"][k] = {"words": len(w), "zero_length": sum(1 for x in w if x["end"] <= x["start"])}

    (base / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "vs_reference"}, indent=1))
    for k, v in out["vs_reference"].items():
        print(k, v["wer"], v["diffs"])


if __name__ == "__main__":
    main()
