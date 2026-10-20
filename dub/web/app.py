"""Dublaj web arayüzü: dosya yükle, dilleri seç, ilerlemeyi izle, sonucu indir.

Çalıştırma (~/.venvs/dub ortamında):
    ~/.venvs/dub/bin/python -m dub.web            # http://localhost:8000
    ~/.venvs/dub/bin/python -m dub.web --port 8080

İşler tek bir arka plan iş parçacığında sırayla çalışır (GPU aynı anda tek işi kaldırıyor). Her iş
data/web/<id>/ altında tutulur: input.<uzantı>, job.json (durum) ve hattın bütün adım çıktıları.
"""
from __future__ import annotations

import queue
import shutil
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from dub.common import DATA, load_json, save_json
from dub.pipeline import STEPS, default_pipeline
from dub.translate import LANG_NAMES

JOBS_DIR = DATA / "web"
STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_MB = 1024
ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
LANG_TR = {"tr": "Türkçe", "en": "İngilizce", "de": "Almanca", "fr": "Fransızca", "es": "İspanyolca",
           "it": "İtalyanca", "pt": "Portekizce", "ru": "Rusça", "ar": "Arapça", "ja": "Japonca", "ko": "Korece",
           "zh": "Çince", "nl": "Felemenkçe", "pl": "Lehçe", "hi": "Hintçe"}
# Kullanıcıya sunulan dosyalar: adım JSON'ları ve final çıktılar
DOWNLOADS = [s[1] for s in STEPS] + ["final/dub.mp4", "final/dub.m4a", "final/dub.wav"]


class JobStore:
    """İşlerin bellekteki durumu; her değişiklik job.json'a da yazılır (sunucu yeniden başlarsa geçmiş kalır)."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}
        for f in root.glob("*/job.json"):
            job = load_json(f)
            if job["status"] in ("queued", "running"):  # sunucu kapanırken yarıda kalmış
                job.update(status="error", error="Sunucu yeniden başlatıldı, iş yarıda kaldı")
                save_json(f, job)
            self.jobs[job["id"]] = job

    def dir(self, job_id: str) -> Path:
        return self.root / job_id

    def create(self, job: dict) -> None:
        with self.lock:
            self.jobs[job["id"]] = job
            save_json(self.dir(job["id"]) / "job.json", job)

    def update(self, job_id: str, **fields) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.update(fields)
            save_json(self.dir(job_id) / "job.json", job)

    def get(self, job_id: str) -> dict:
        with self.lock:
            if job_id not in self.jobs:
                raise HTTPException(404, "İş bulunamadı")
            return dict(self.jobs[job_id])

    def all(self) -> list[dict]:
        with self.lock:
            return sorted((dict(j) for j in self.jobs.values()), key=lambda j: j["created"], reverse=True)

    def delete(self, job_id: str) -> None:
        with self.lock:
            self.jobs.pop(job_id, None)
        shutil.rmtree(self.dir(job_id), ignore_errors=True)


store = JobStore(JOBS_DIR)
work: queue.Queue[str] = queue.Queue()
pending: list[str] = []  # sıradaki işler (sıra numarası göstermek için)


def worker() -> None:
    pipe = None
    while True:
        job_id = work.get()
        if job_id in pending:
            pending.remove(job_id)
        job = store.jobs.get(job_id)
        if job is None:  # sıradayken silinmiş
            continue
        d = store.dir(job_id)
        store.update(job_id, status="running", started=time.time(), message="Başlıyor")
        last_save = [0.0]

        def progress(key, frac, overall, msg):
            # Segment başına çok sık çağrılıyor; diske en fazla saniyede bir yaz
            now = time.time()
            if frac in (0.0, 1.0) or now - last_save[0] > 1.0:
                last_save[0] = now
                store.update(job_id, step=key, step_progress=round(frac, 3), progress=round(overall, 3), message=msg)
            else:
                store.jobs[job_id].update(step=key, step_progress=round(frac, 3), progress=round(overall, 3),
                                          message=msg)

        try:
            pipe = pipe or default_pipeline()
            res = pipe.run(d / job["input"], job["target"], job["source"] or None, d, progress=progress)
            store.update(job_id, status="done", progress=1.0, finished=time.time(), message="Hazır",
                         files=res["files"])
        except Exception as e:
            traceback.print_exc()
            store.update(job_id, status="error", finished=time.time(), error=f"{type(e).__name__}: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=worker, daemon=True).start()
    yield


app = FastAPI(title="Dublaj", lifespan=lifespan)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def config():
    langs = [{"code": c, "name": LANG_TR.get(c, n)} for c, n in LANG_NAMES.items()]
    return {"languages": sorted(langs, key=lambda x: x["name"]), "max_upload_mb": MAX_UPLOAD_MB,
            "accept": sorted(ALLOWED_EXT), "steps": [{"key": k, "label": label} for k, _, label, _ in STEPS]}


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...), target: str = Form(...), source: str = Form("")):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Desteklenmeyen dosya türü: {ext or '?'}")
    if target not in LANG_NAMES or (source and source not in LANG_NAMES):
        raise HTTPException(400, "Geçersiz dil")
    if source == target:
        raise HTTPException(400, "Kaynak ve hedef dil aynı")
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = store.dir(job_id)
    d.mkdir(parents=True)
    size = 0
    with open(d / f"input{ext}", "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB << 20:
                f.close()
                shutil.rmtree(d, ignore_errors=True)
                raise HTTPException(413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor")
            f.write(chunk)
    store.create({"id": job_id, "filename": file.filename, "input": f"input{ext}", "size": size,
                  "source": source, "target": target, "status": "queued", "progress": 0.0, "step": None,
                  "step_progress": 0.0, "message": "Sırada", "created": time.time(), "error": None, "files": {}})
    pending.append(job_id)
    work.put(job_id)
    return store.get(job_id)


@app.get("/api/jobs")
def list_jobs():
    return [with_queue(j) for j in store.all()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return with_queue(store.get(job_id))


@app.get("/api/jobs/{job_id}/segments")
def segments(job_id: str):
    """Çeviri bittiyse segmentler (orijinal + çeviri), değilse boş liste."""
    path = store.dir(job_id) / "03_translation.json"
    if not path.exists():
        return {"segments": [], "glossary": []}
    t = load_json(path)
    return {"segments": [{k: s[k] for k in ("id", "speaker", "start", "end", "text", "translation")}
                         for s in t["segments"]], "glossary": t.get("glossary", [])}


@app.get("/api/jobs/{job_id}/files/{name:path}")
def download(job_id: str, name: str, inline: bool = False):
    store.get(job_id)
    if name not in DOWNLOADS:
        raise HTTPException(404, "Dosya bulunamadı")
    path = store.dir(job_id) / name
    if not path.exists():
        raise HTTPException(404, "Dosya henüz hazır değil")
    job = store.get(job_id)
    stem = Path(job["filename"]).stem
    filename = f"{stem}_{job['target']}{path.suffix}" if name.startswith("final/") else f"{stem}_{path.name}"
    return FileResponse(path, filename=None if inline else filename)


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    """Hata alan işi yeniden sıraya koyar; tamamlanmış adımlar kayıtlı dosyalarından okunur."""
    job = store.get(job_id)
    if job["status"] != "error":
        raise HTTPException(409, "Sadece hata alan iş yeniden denenebilir")
    store.update(job_id, status="queued", error=None, message="Sırada")
    pending.append(job_id)
    work.put(job_id)
    return with_queue(store.get(job_id))


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    job = store.get(job_id)
    if job["status"] == "running":
        raise HTTPException(409, "Çalışan iş silinemez")
    if job_id in pending:
        pending.remove(job_id)
    store.delete(job_id)
    return {"ok": True}


def with_queue(job: dict) -> dict:
    job["queue_position"] = pending.index(job["id"]) + 1 if job["id"] in pending else None
    job["source_name"] = LANG_TR.get(job["source"], "Otomatik") if job["source"] else "Otomatik"
    job["target_name"] = LANG_TR.get(job["target"], job["target"])
    return job
