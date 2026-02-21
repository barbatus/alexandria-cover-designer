FROM python:3.11-slim

WORKDIR /app

# System deps for pillow/opencv headless usage
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY .env.example .env.example

# Explicit static copy for webapp pages
COPY src/static/ src/static/

# Runtime directories
RUN mkdir -p tmp data "Output Covers" "Input Covers"

ENV HOST=0.0.0.0
ENV PORT=8001

EXPOSE 8001

CMD ["sh", "-c", "python3 scripts/quality_review.py --serve --host ${HOST:-0.0.0.0} --port ${PORT:-8001} --output-dir \"Output Covers\""]
