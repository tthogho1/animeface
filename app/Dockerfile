FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY animeface ./animeface
RUN useradd --system --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "animeface.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
