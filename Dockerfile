# Dublaj web arayüzü. GPU için ana makinede NVIDIA sürücüsü ve NVIDIA Container Toolkit gerekir.
# PyTorch'un PyPI tekerlekleri CUDA kütüphanelerini kendisi getiriyor; CUDA taban imajı gerekmiyor.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/huggingface \
    TORCH_HOME=/cache/torch

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY dub/ dub/

EXPOSE 8000
CMD ["python", "-m", "dub.web", "--host", "0.0.0.0", "--port", "8000"]
