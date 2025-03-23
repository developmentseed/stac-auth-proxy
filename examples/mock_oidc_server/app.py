# type: ignore
# ruff: noqa
"""Mock OIDC server for demo/experimentation."""

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import jwt

app = FastAPI()

# Configure templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
    max_age=86400,  # 24 hours
)

# Configuration
ISSUER = os.environ.get("ISSUER", "http://localhost:3000")
AVAILABLE_SCOPES = os.environ.get("SCOPES", "")


@dataclass
class KeyPair:
    cache_dir: Path
    key_id: str = "1"

    jwks: dict = field(init=False)
    private_key: str = field(init=False)

    def __post_init__(self):
        private_key_path = self.cache_dir / "private_key.pem"
        jwks_path = self.cache_dir / "jwks.json"

        if private_key_path.exists() and jwks_path.exists():
            self.jwks = json.loads(jwks_path.read_text())
            self.private_key = private_key_path.read_text()
            return

        # Generate keys
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key = private_key.public_key()
        public_numbers = public_key.public_numbers()

        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": self.key_id,
                    "alg": "RS256",
                    "n": int_to_base64url(public_numbers.n),
                    "e": int_to_base64url(public_numbers.e),
                }
            ]
        }
        self.private_key = private_pem.decode("utf-8")

        private_key_path.write_text(self.private_key)
        jwks_path.write_text(json.dumps(self.jwks, indent=2))

    @staticmethod
    def int_to_base64url(value):
        """Convert an integer to base64url format."""
        value_hex = format(value, "x")
        # Ensure even length
        if len(value_hex) % 2 == 1:
            value_hex = "0" + value_hex
        value_bytes = bytes.fromhex(value_hex)
        return base64.urlsafe_b64encode(value_bytes).rstrip(b"=").decode("ascii")


# Load or generate key pair on startup
KEY_PAIR = KeyPair(Path(__file__).parent)

# In-memory storage
authorization_codes = {}
pkce_challenges = {}
access_tokens = {}
auth_requests = {}


@app.get("/")
async def root():
    return {
        "message": "If you're using this in production, you are going to have a bad time."
    }


@app.get("/.well-known/openid-configuration")
async def openid_configuration():
    """Return OpenID Connect configuration."""
    scopes_set = set(["openid", "profile", *AVAILABLE_SCOPES.split(",")])
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": sorted(scopes_set),
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        "claims_supported": ["sub", "iss", "iat", "exp"],
        "code_challenge_methods_supported": ["S256"],
    }


@app.get("/.well-known/jwks.json")
async def jwks():
    """Return JWKS (JSON Web Key Set)."""
    return KEY_PAIR.jwks


@app.get("/authorize")
async def authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str = "",
    code_challenge: Optional[str] = None,
    code_challenge_method: Optional[str] = None,
):
    """Handle authorization request."""
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Invalid response type")

    # Validate PKCE if provided
    if code_challenge is not None:
        if code_challenge_method != "S256":
            raise HTTPException(status_code=400, detail="Only S256 PKCE is supported")

    # Store the auth request details
    request_id = os.urandom(16).hex()
    auth_requests[request_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }

    # Show login page
    scopes = sorted(set(("openid profile " + scope).split()))
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "request_id": request_id,
            "client_id": client_id,
            "scopes": scopes,
        },
    )


@app.post("/login")
async def login(request_id: str = Form(...)):
    """Handle login form submission."""
    # Retrieve the stored auth request
    if request_id not in auth_requests:
        raise HTTPException(status_code=400, detail="Invalid request")

    auth_request = auth_requests.pop(request_id)

    # Generate authorization code
    code = os.urandom(32).hex()

    # Store authorization details
    authorization_codes[code] = {
        "client_id": auth_request["client_id"],
        "redirect_uri": auth_request["redirect_uri"],
        "scope": " ".join(
            sorted(set(("openid profile " + auth_request["scope"]).split(" ")))
        ),
    }

    # Store PKCE challenge if provided
    if auth_request["code_challenge"]:
        pkce_challenges[code] = auth_request["code_challenge"]

    # Redirect back to client with the code
    params = {"code": code, "state": auth_request["state"]}
    return RedirectResponse(
        url=f"{auth_request['redirect_uri']}?{urlencode(params)}", status_code=303
    )


@app.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
):
    """Handle token request."""
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Invalid grant type")

    # Verify the authorization code exists
    if code not in authorization_codes:
        raise HTTPException(status_code=400, detail="Invalid authorization code")

    auth_details = authorization_codes[code]

    # Verify client_id matches the stored one
    if client_id != auth_details["client_id"]:
        raise HTTPException(status_code=400, detail="Client ID mismatch")

    # Verify redirect_uri matches the stored one
    if redirect_uri != auth_details["redirect_uri"]:
        raise HTTPException(status_code=400, detail="Redirect URI mismatch")

    # Check if PKCE was used in the authorization request
    if code in pkce_challenges:
        if not code_verifier:
            raise HTTPException(status_code=400, detail="Code verifier required")

        # Verify the code verifier
        code_challenge = pkce_challenges[code]
        computed_challenge = hashlib.sha256(code_verifier.encode()).digest()
        computed_challenge = (
            base64.urlsafe_b64encode(computed_challenge).decode().rstrip("=")
        )

        if computed_challenge != code_challenge:
            raise HTTPException(status_code=400, detail="Invalid code verifier")

    # Clean up the used code and PKCE challenge
    del authorization_codes[code]
    if code in pkce_challenges:
        del pkce_challenges[code]

    # Generate access token
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=15)

    return JSONResponse(
        content={
            "access_token": jwt.encode(
                {
                    "iss": ISSUER,
                    "sub": "user123",
                    "iat": now,
                    "exp": now + expires_delta,
                    "scope": auth_details["scope"],
                    "kid": KEY_PAIR.key_id,
                },
                KEY_PAIR.private_key,
                algorithm="RS256",
                headers={"kid": KEY_PAIR.key_id},
            ),
            "token_type": "Bearer",
            "expires_in": expires_delta.seconds,
            "scope": auth_details["scope"],
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8888)),
        reload=True,
    )
