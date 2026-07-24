# validate_inference/Dockerfile
#
# Heavy image for real YOLO inference validation.
# NOT used in CI (that image is docker/edge/Dockerfile — intentionally ultralytics-free).
# Used for: pre-release model validation, checkpoint smoke tests.
#
# Build: docker build -f validate_inference/Dockerfile -t traxia-validate .
# Run:   docker run --rm traxia-validate
#        docker run --rm -v /host/yolo_retail.pt:/model/yolo_retail.pt:ro \
#                        traxia-validate --model /model/yolo_retail.pt

FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ultralytics + deps (large; ~1.5 GB with PyTorch)
COPY validate_inference/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy edge source (needed by test_pipeline_e2e.py)
COPY edge/ ./edge/
COPY validate_inference/validate_yolo.py .
COPY validate_inference/test_pipeline_e2e.py .

ENTRYPOINT ["bash", "-c", \
    "python3 validate_yolo.py \"$@\" && python3 test_pipeline_e2e.py \"$@\"", "--"]
CMD ["--model", "yolov8n.pt"]
