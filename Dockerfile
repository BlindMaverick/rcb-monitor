FROM python:3.12-slim

WORKDIR /app

# Persist state file across restarts
VOLUME /app/data

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY monitor.py .

# Use /app/data for the state file
ENV STATE_DIR=/app/data

CMD ["python", "-u", "monitor.py"]
