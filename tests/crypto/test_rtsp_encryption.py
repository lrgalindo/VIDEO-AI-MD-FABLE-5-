"""Tests for RTSP URL Fernet encryption (Ítem 2 of Fase A hardening).

Verifies:
  - encrypt_rtsp_url() returns bytes that are NOT the plaintext URL
  - decrypt_rtsp_url() round-trips correctly
  - A row stored in the cameras table has opaque ciphertext (not the URL)
  - Wrong key cannot decrypt (raises InvalidToken)

These tests require:
  DATABASE_URL pointing at the test DB
  RTSP_ENCRYPTION_KEY set (done by tests/conftest.py)
"""

import os
import uuid

import psycopg2
import psycopg2.extras
import pytest
from cryptography.fernet import Fernet, InvalidToken

from cloud.crypto import decrypt_rtsp_url, encrypt_rtsp_url

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/traxia",
)


# ── Unit tests (no DB) ──────────────────────────────────────────────────────

def test_encrypt_is_not_plaintext():
    url = "rtsp://secret-cam.prod.local/live"
    ct = encrypt_rtsp_url(url)
    assert isinstance(ct, bytes)
    assert url.encode() not in ct
    assert b"rtsp" not in ct  # ciphertext must be opaque


def test_round_trip():
    url = "rtsp://192.168.1.42:554/channel1"
    assert decrypt_rtsp_url(encrypt_rtsp_url(url)) == url


def test_wrong_key_raises():
    url = "rtsp://cam.example.com/live"
    ct = encrypt_rtsp_url(url)

    wrong_key = Fernet.generate_key()
    with pytest.raises(InvalidToken):
        Fernet(wrong_key).decrypt(ct)


def test_two_encryptions_differ():
    """Fernet uses a random IV — same URL must produce different ciphertexts."""
    url = "rtsp://cam.example.com/live"
    assert encrypt_rtsp_url(url) != encrypt_rtsp_url(url)


# ── DB integration test ─────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = psycopg2.connect(_DB_URL)
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def test_stored_ciphertext_is_not_plaintext_in_db(db):
    """Insert a camera with a real encrypted URL; verify the stored bytes are not the URL."""
    url = "rtsp://super-secret-cam.internal/stream"
    ciphertext = encrypt_rtsp_url(url)

    tenant_id = str(uuid.uuid4())
    site_id = str(uuid.uuid4())
    cam_id = str(uuid.uuid4())

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, name, vertical_type, status) "
            "VALUES (%s, 'CryptoTestTenant', 'retail', 'active')",
            (tenant_id,),
        )
        cur.execute(
            "INSERT INTO sites (id, tenant_id, name, status) VALUES (%s, %s, 'CryptoSite', 'active')",
            (site_id, tenant_id),
        )
        cur.execute(
            "INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) "
            "VALUES (%s, %s, 'CryptoCam', %s, 'test-key-v1', 'active')",
            (cam_id, site_id, psycopg2.Binary(ciphertext)),
        )

        # Read the raw bytes back as stored
        cur.execute("SELECT rtsp_url_ciphertext FROM cameras WHERE id = %s", (cam_id,))
        row = cur.fetchone()
        stored_bytes = bytes(row[0])

        # The stored bytes must NOT contain the plaintext URL
        assert url.encode() not in stored_bytes, (
            "SECURITY FAILURE: plaintext RTSP URL found in stored ciphertext"
        )
        assert b"rtsp" not in stored_bytes, (
            "SECURITY FAILURE: 'rtsp' prefix visible in ciphertext"
        )

        # But we can round-trip via decrypt
        assert decrypt_rtsp_url(stored_bytes) == url
