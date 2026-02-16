FROM python:3.11-slim

# Clean apt cache and install ffmpeg and dependencies
RUN apt-get clean && rm -rf /var/lib/apt/lists/* && \
    apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker script
COPY ffmpegWorkerPython.py .

# Expose port
EXPOSE 8000

# Run worker
CMD ["python", "ffmpegWorkerPython.py"]
