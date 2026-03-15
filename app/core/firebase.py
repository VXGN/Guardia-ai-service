import time
import logging

import httpx
import jwt as pyjwt
from cryptography.x509 import load_pem_x509_certificate
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

_cert_cache: dict = {"certs": None, "expires_at": 0.0}


async def _get_google_certs() -> dict:
    """Fetch Google public certs with caching."""
    now = time.time()
    if _cert_cache["certs"] and now < _cert_cache["expires_at"]:
        return _cert_cache["certs"]

    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_CERTS_URL)
        resp.raise_for_status()
        certs = resp.json()

    max_age = 3600
    cache_control = resp.headers.get("cache-control", "")
    for part in cache_control.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                max_age = int(part.split("=")[1])
            except ValueError:
                pass

    _cert_cache["certs"] = certs
    _cert_cache["expires_at"] = now + max_age
    logger.debug("Refreshed Google public certs (TTL=%ds)", max_age)
    return certs


async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    settings: Settings = Depends(get_settings),
) -> dict:
    token = credentials.credentials
    project_id = settings.FIREBASE_PROJECT_ID

    if not project_id:
        raise HTTPException(500, "FIREBASE_PROJECT_ID not configured")

    try:
        certs = await _get_google_certs()

        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid")
        if kid not in certs:
            raise HTTPException(401, "Invalid token: unknown kid")

        cert = load_pem_x509_certificate(certs[kid].encode())
        public_key = cert.public_key()

        payload = pyjwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
        )
        return payload
    except HTTPException:
        raise
    except pyjwt.InvalidIssuerError as e:
        unverified = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        logger.warning(
            "Invalid Firebase token issuer. token_iss=%r token_aud=%r expected_issuer=%r expected_aud=%r",
            unverified.get("iss"),
            unverified.get("aud"),
            f"https://securetoken.google.com/{project_id}",
            project_id,
        )
        raise HTTPException(401, "Invalid token") from e
    except pyjwt.InvalidAudienceError as e:
        unverified = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        logger.warning(
            "Invalid Firebase token audience. token_iss=%r token_aud=%r expected_issuer=%r expected_aud=%r",
            unverified.get("iss"),
            unverified.get("aud"),
            f"https://securetoken.google.com/{project_id}",
            project_id,
        )
        raise HTTPException(401, "Invalid token") from e
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError as e:
        logger.warning("Invalid Firebase token: %s", e)
        raise HTTPException(401, "Invalid token")
    except Exception as e:
        logger.error("Firebase auth error: %s", e)
        raise HTTPException(401, "Authentication failed")
