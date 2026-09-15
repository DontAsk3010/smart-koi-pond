FROM python:3.12.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SMART_KOI_HOST=127.0.0.1 \
    SMART_KOI_PORT=8080 \
    SMART_KOI_HISTORIAN_PATH=/var/lib/smart-koi-pond/historian.jsonl

WORKDIR /opt/smart-koi-pond

RUN groupadd --system smartkoi \
    && useradd --system --gid smartkoi --home-dir /nonexistent --shell /usr/sbin/nologin smartkoi \
    && mkdir -p /var/lib/smart-koi-pond \
    && chown smartkoi:smartkoi /var/lib/smart-koi-pond

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

USER smartkoi

VOLUME ["/var/lib/smart-koi-pond"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; port = os.environ.get('SMART_KOI_PORT', '8080'); urllib.request.urlopen('http://127.0.0.1:' + port + '/api/health', timeout=3).read()"]

CMD ["smart-koi-pond-ui"]
