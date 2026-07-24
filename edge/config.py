import os

CLOUD_API_URL: str = os.environ.get("CLOUD_API_URL", "http://localhost:8000")
GATEWAY_ID: str = os.environ.get("GATEWAY_ID", "")
VERTICAL_TYPE: str = os.environ.get("VERTICAL_TYPE", "retail")

# Directory where downloaded model checkpoints are cached
CACHE_DIR: str = os.environ.get("CACHE_DIR", "/tmp/traxia_model_cache")

# Token file persists the access/refresh pair across process restarts
TOKEN_FILE: str = os.environ.get("TOKEN_FILE", "/tmp/traxia_tokens.json")

# RTSP source URLs, comma-separated
RTSP_URLS: list[str] = [u for u in os.environ.get("RTSP_URLS", "").split(",") if u]

# Target capture FPS after downsampling (3–10 per SDD §7.2)
CAPTURE_FPS: int = int(os.environ.get("CAPTURE_FPS", "3"))

# SQLite queue path
QUEUE_DB: str = os.environ.get("QUEUE_DB", "/tmp/traxia_queue.db")

# Queue eviction: delete items older than this many days
QUEUE_RETENTION_DAYS: int = int(os.environ.get("QUEUE_RETENTION_DAYS", "7"))

# Exponential backoff: base seconds and ceiling
BACKOFF_BASE_SECONDS: float = float(os.environ.get("BACKOFF_BASE_SECONDS", "2.0"))
BACKOFF_MAX_SECONDS: float = float(os.environ.get("BACKOFF_MAX_SECONDS", "300.0"))
