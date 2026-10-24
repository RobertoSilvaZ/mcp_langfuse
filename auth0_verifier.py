"""Auth0 JWT verification for MCP HTTP requests (fail closed)."""
import asyncio
import os
import time

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier

AUTH0_DOMAIN = os.environ["AUTH0_DOMAIN"].strip().removeprefix("https://").rstrip("/")
ISSUER = f"https://{AUTH0_DOMAIN}/"
AUDIENCE = os.environ["AUTH0_AUDIENCE"]
ALLOWED_SUBJECTS = frozenset(x.strip() for x in os.environ["AUTH0_ALLOWED_SUBJECTS"].split(",") if x.strip())
if not ALLOWED_SUBJECTS:
    raise ValueError("AUTH0_ALLOWED_SUBJECTS must contain at least one Auth0 user_id (sub).")
if not AUTH0_DOMAIN or "/" in AUTH0_DOMAIN or not AUDIENCE.startswith("https://"):
    raise ValueError("Invalid Auth0 domain or audience.")

JWKS = PyJWKClient(f"{ISSUER}.well-known/jwks.json", cache_jwk_set=True, lifespan=300)


def _verify(token: str) -> AccessToken | None:
    try:
        key = JWKS.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token, key, algorithms=["RS256"], audience=AUDIENCE,
            issuer=ISSUER, options={"require": ["exp", "iat", "sub"]},
            leeway=30,
        )
        subject = payload["sub"]
        if subject not in ALLOWED_SUBJECTS:
            return None
        scopes = payload.get("scope", "").split()
        if "mcp:read" not in scopes:
            return None
        return AccessToken(
            token=token,
            client_id=str(payload.get("azp") or payload.get("client_id") or subject),
            scopes=scopes,
            expires_at=int(payload["exp"]),
            resource=AUDIENCE,
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


class Auth0TokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        # PyJWKClient performs blocking HTTPS discovery: avoid blocking MCP's event loop.
        return await asyncio.to_thread(_verify, token)
