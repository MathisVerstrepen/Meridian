FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HOME=/home/browseruser

RUN python -m venv "$VIRTUAL_ENV"
COPY ./browser_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY ./browser_service/app /build/app
RUN python -m camoufox fetch "$(cat /build/app/camoufox_browser_version.txt)" \
    && PYTHONPATH=/build python -c "from app.camoufox_runtime import load_browser_version, preflight_camoufox_cache; preflight_camoufox_cache(load_browser_version(), True)" \
    && PYTHONPATH=/build python -c "from camoufox.async_api import launch_options; [launch_options(os=name, headless=True, browser='152.0.4-beta.27', debug=False) for name in ('linux', 'macos', 'windows')]" \
    && PYTHONPATH=/build python -c "from pathlib import Path; from app.artifacts import build_cache_manifest; Path('/build/app/camoufox_cache_manifest.sha256').write_text('\n'.join(build_cache_manifest()) + '\n')" \
    && chmod -R a-w /home/browseruser/.cache/camoufox

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin \
    HOME=/home/browseruser \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TMPDIR=/tmp \
    FONTCONFIG_FILE=/etc/browser-service/fonts.conf

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libgtk-3-0 libx11-xcb1 libasound2 libnss3 libnspr4 libatk1.0-0 \
       libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
       libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
       libatspi2.0-0 libdbus-glib-1-2 fontconfig fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/sbin/groupadd --system browseruser \
    && /usr/sbin/useradd --system --create-home --home-dir /home/browseruser -g browseruser browseruser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=browseruser:browseruser /home/browseruser/.cache/camoufox /home/browseruser/.cache/camoufox
COPY ./browser_service/fontconfig.conf /etc/browser-service/fonts.conf
WORKDIR /app
COPY --from=builder --chown=browseruser:browseruser /build/app /app/app
RUN mkdir -p /home/browseruser/.camoufox /home/browseruser/Downloads /home/browseruser/camoufox \
    && chown browseruser:browseruser \
       /home/browseruser/.camoufox /home/browseruser/Downloads /home/browseruser/camoufox \
    && chmod -R a-w \
       /home/browseruser/.cache/camoufox /home/browseruser/.camoufox \
       /home/browseruser/Downloads /home/browseruser/camoufox

EXPOSE 5010
USER browseruser
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5010", "--workers", "1", "--timeout-graceful-shutdown", "25", "--no-access-log"]
