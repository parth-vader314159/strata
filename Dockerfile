# Multi-stage: the runtime image carries no compiler and no build cache.
# A smaller image is a smaller air-gap bundle, which is a faster USB stick.
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
LABEL org.opencontainers.image.title="STRATA" \
      org.opencontainers.image.description="Universal log pre-processing — layered, legible, nothing rewritten" \
      org.opencontainers.image.version="2.0.0"

# Non-root. The intake gateway listens on a network port and parses hostile
# input; if it is ever compromised, root would hand the attacker the host.
# Privileged ports are mapped from the host instead (514 -> 5514).
RUN useradd --create-home --shell /usr/sbin/nologin strata
COPY --from=build /install /usr/local
WORKDIR /app
COPY --chown=strata:strata . /app
RUN mkdir -p /app/var && chown -R strata:strata /app/var /app/grammars
USER strata

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8400 5514/udp 5601

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8400/api/health')" || exit 1

CMD ["python", "strata.py", "console", "--host", "0.0.0.0", "--port", "8400"]
