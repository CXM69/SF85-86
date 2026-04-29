FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    SF_VALIDATOR_MAX_UPLOAD_BYTES=26214400 \
    SF_VALIDATOR_SESSION_TTL_SECONDS=3600 \
    SF_VALIDATOR_TEMP_DIR=/tmp/sf-validator

WORKDIR /app

RUN groupadd --system sfvalidator \
    && useradd --system --gid sfvalidator --home-dir /app sfvalidator

COPY pyproject.toml requirements.txt ./
COPY sf_validator ./sf_validator

RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /tmp/sf-validator \
    && chown -R sfvalidator:sfvalidator /app /tmp/sf-validator

USER sfvalidator

EXPOSE 8000

CMD ["python", "-m", "sf_validator.web"]
