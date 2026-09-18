FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sentinel_stack ./sentinel_stack
COPY ui ./ui
COPY scripts ./scripts
COPY kaspa.env.example ./

RUN pip install --no-cache-dir -e .

ENV SENTINEL_API_HOST=0.0.0.0
ENV SENTINEL_API_PORT=8790

EXPOSE 8790

CMD ["python", "-m", "sentinel_stack.api", "--host", "0.0.0.0", "--port", "8790"]
