FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for pandas/openpyxl
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create logs directory
RUN mkdir -p logs

EXPOSE 8002

CMD ["sh", "-c", "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8002"]
