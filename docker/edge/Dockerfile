FROM python:3.11-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Install only runtime deps — ultralytics/PyTorch intentionally excluded
# to keep the image small; gateway falls back to synthetic inference (STUB mode)
RUN pip install --no-cache-dir requests opencv-python-headless
COPY edge/ ./edge/
CMD ["python", "-m", "edge.gateway"]
