import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/traxia",
)

# Role the Cloud API uses for gateway operations — never traxia_app
SERVICE_ROLE: str = "traxia_service"

# JWT_SECRET must be set via environment variable — no default is provided so a
# misconfigured deployment fails immediately rather than silently using a weak key.
_jwt_secret = os.environ.get("JWT_SECRET")
if not _jwt_secret:
    raise ValueError("JWT_SECRET environment variable is required")
JWT_SECRET: str = _jwt_secret

# RTSP_ENCRYPTION_KEY must be set — same fail-fast contract as JWT_SECRET.
# Fernet key: URL-safe base64-encoded 32 bytes.
# Generate: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
_rtsp_key = os.environ.get("RTSP_ENCRYPTION_KEY")
if not _rtsp_key:
    raise ValueError("RTSP_ENCRYPTION_KEY environment variable is required")
RTSP_ENCRYPTION_KEY: str = _rtsp_key

JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_TTL_HOURS: int = 24
REFRESH_TOKEN_TTL_DAYS: int = 90

# Grace window after token rotation: how long the previous hash remains valid.
# Covers the case where a refresh response is lost in transit and the gateway
# retries with the old token. Within this window the first presenter wins;
# a second attempt with the same old hash is rejected.
REFRESH_GRACE_SECONDS: int = int(os.environ.get("REFRESH_GRACE_SECONDS", "90"))

# SuperAdmin / Platform-Admin JWT secret — intentionally separate from JWT_SECRET
# so that a leaked tenant JWT cannot be replayed as a SuperAdmin token.
# If omitted in non-production environments the server raises on first SA endpoint call.
PLATFORM_ADMIN_SECRET: str = os.environ.get("PLATFORM_ADMIN_SECRET", "")

# Supabase Auth integration (MFA relay)
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Anthropic API — Copiloto and audit tasks (SDD §12.5)
# Must be set in production; omitting it disables copilot endpoints gracefully.
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
# Model IDs live in config (never hardcoded) so QA can swap without deploy.
ANTHROPIC_MODEL_COPILOT: str = os.environ.get("ANTHROPIC_MODEL_COPILOT", "claude-haiku-4-5-20251001")
ANTHROPIC_MODEL_AUDIT: str = os.environ.get("ANTHROPIC_MODEL_AUDIT", "claude-sonnet-4-6")

# Cloudflare R2 — snapshot storage (SDD §7, §3.1 decision 12).
# All four must be set together; if any is absent, snapshot upload/presign is skipped
# and findings are served without snapshot_url (same code path, no crash).
R2_ACCOUNT_ID: str = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID: str = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_SNAPSHOTS: str = os.environ.get("R2_BUCKET_SNAPSHOTS", "traxia-snapshots")
# Override the S3 endpoint — used in local E2E tests to point at MinIO instead of R2.
# When empty, the endpoint is built from R2_ACCOUNT_ID (production Cloudflare R2 path).
R2_ENDPOINT_URL: str = os.environ.get("R2_ENDPOINT_URL", "")
# Public-facing endpoint for presigned URLs — may differ from R2_ENDPOINT_URL when
# the internal S3 host (e.g. "minio") differs from the externally reachable host
# (e.g. "localhost:9000").  Applies only to generate_presigned_url calls.
# In production (real R2) this is always empty and the endpoint is self-consistent.
R2_PUBLIC_ENDPOINT_URL: str = os.environ.get("R2_PUBLIC_ENDPOINT_URL", "")

# Presigned URL TTL for snapshot access (seconds).  Short-lived to prevent link sharing.
R2_PRESIGN_TTL_SECONDS: int = int(os.environ.get("R2_PRESIGN_TTL_SECONDS", "300"))

# E2E model serving — allows the FAKE_MODEL_SERVE endpoint to serve real YOLO weights.
# When set, the manifest SHA256/size matches the real file; the edge pre-caches it.
REAL_MODEL_SHA256: str = os.environ.get("REAL_MODEL_SHA256", "")
REAL_MODEL_SIZE: int = int(os.environ.get("REAL_MODEL_SIZE", "0"))
