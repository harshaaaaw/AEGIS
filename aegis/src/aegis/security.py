"""Security primitives: JWT authN (OIDC-style) + SSRF guard + secret policy.

No invented crypto: uses PyJWT (HS256) for token issue/verify and the
standard library `ipaddress` + `urllib` for SSRF classification. The
secret policy enforces a minimum entropy so we never accept an 11-byte key
(the kind that triggered InsecureKeyLengthWarning in tests).
"""
from __future__ import annotations

import ipaddress
import logging
import os
import time

import jwt

MIN_SECRET_BYTES = 32  # RFC 7518 §3.2 minimum for SHA-256 HMAC


class AuthError(Exception):
    """Typed auth failure, never a bare except."""


class WeakSecretError(Exception):
    """Raised when a signing secret is below the entropy floor."""


def require_strong_secret(secret: str) -> None:
    if secret is None or len(secret.encode()) < MIN_SECRET_BYTES:
        raise WeakSecretError(
            f"signing secret must be >= {MIN_SECRET_BYTES} bytes; "
            f"got {len(secret.encode()) if secret else 0}")


def make_token(tenant_id: str, sub: str, secret: str,
               roles: list[str] | None = None, ttl_s: int = 3600) -> str:
    require_strong_secret(secret)
    now = int(time.time())
    return jwt.encode(
        {"tenant_id": tenant_id, "sub": sub, "roles": roles or [],
         "iat": now, "exp": now + ttl_s},
        secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict:
    require_strong_secret(secret)
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:  # typed, includes exp/iat/Signature failures
        raise AuthError(f"invalid token: {e}") from e


# ---- SSRF guard --------------------------------------------------------------

# Link-local / metadata / loopback ranges must never be fetched by an agent tool.
_BLOCKED_NETS = [
    ipaddress.ip_network("169.254.0.0/16"),   # cloud metadata
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),          # ULA
    ipaddress.ip_network("fe80::/10"),         # link-local
]


def is_ssrf_safe(url: str) -> bool:
    """True only if the URL host resolves to a public, non-reserved address.

    We resolve the hostname via DNS (default-deny on resolution failure) and
    block any resolved address in a private/link-local/metadata range. This
    catches 'localhost', cloud metadata IPs, and RFC1918 hosts; public domains
    resolve to public IPs and are allowed.
    """
    from socket import getaddrinfo
    from urllib.parse import urlparse
    host = urlparse(url).hostname
    if not host:
        return False
    host = host.strip("[]")
    try:
        # resolve to all A/AAAA records; if ANY is reserved, deny
        infos = getaddrinfo(host, None)
    except OSError:
        return False  # unresolved / malformed -> deny by default
    for info in infos:
        addr = str(info[4][0]).split("%")[0]  # strip IPv6 zone
        try:
            ipa = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if any(ipa in net for net in _BLOCKED_NETS):
            return False
    return True


# ---- structured logging ------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """JSON-structured logger so operators can grep/alert on fields."""
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(
            '{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'))
        log.addHandler(h)
        log.setLevel(os.environ.get("AEGIS_LOG_LEVEL", "INFO"))
    return log
