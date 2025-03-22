# type: ignore
"""Mock OIDC server for demo/experimentation."""


import base64
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from jose import jwt

app = FastAPI()

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
CLIENT_ID = os.environ.get("CLIENT_ID", "stac")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "secret")
REDIRECT_URI = os.environ.get(
    "REDIRECT_URI", "http://localhost:8000/docs/oauth2-redirect"
)
ISSUER = os.environ.get("ISSUER", "http://localhost:3000")

# Key paths - determine from current file location
APP_DIR = Path(__file__).parent
PRIVATE_KEY_PATH = APP_DIR / "private_key.pem"
JWKS_PATH = APP_DIR / "jwks.json"


def load_or_generate_keys():
    """Load keys from files if they exist, otherwise generate and save them."""
    # If both files exist, load them
    if PRIVATE_KEY_PATH.exists() and JWKS_PATH.exists():
        private_key = PRIVATE_KEY_PATH.read_text()
        jwks = json.loads(JWKS_PATH.read_text())
        return private_key, jwks

    # Otherwise, generate new keys
    private_key, jwks = generate_key_pair()

    # Save the keys
    PRIVATE_KEY_PATH.write_text(private_key)
    JWKS_PATH.write_text(json.dumps(jwks, indent=2))

    return private_key, jwks


# Generate RSA key pair
def generate_key_pair():
    """Generate RSA key pair and return private and public keys."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    # Convert public key components to base64url format
    def int_to_base64url(value):
        """Convert an integer to base64url format."""
        value_hex = format(value, "x")
        # Ensure even length
        if len(value_hex) % 2 == 1:
            value_hex = "0" + value_hex
        value_bytes = bytes.fromhex(value_hex)
        return base64.urlsafe_b64encode(value_bytes).rstrip(b"=").decode("ascii")

    return (
        private_pem.decode("utf-8"),
        {
            "keys": [
                {
                    "jwk": {
                        "kty": "RSA",
                        "use": "sig",
                        "kid": "1",  # Key ID
                        "alg": "RS256",
                        "n": int_to_base64url(public_numbers.n),
                        "e": int_to_base64url(public_numbers.e),
                    },
                }
            ]
        },
    )


# Load or generate key pair on startup
PRIVATE_KEY, JWKS = load_or_generate_keys()

# In-memory storage
authorization_codes = {}
pkce_challenges = {}
access_tokens = {}

# Mock client registry
clients = {
    CLIENT_ID: {
        "client_secret": CLIENT_SECRET,
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code"],
    }
}


def generate_token(
    subject: str, expires_delta: timedelta = timedelta(minutes=15)
) -> str:
    """Generate a JWT token."""
    now = datetime.now(datetime.UTC)
    claims = {
        "iss": ISSUER,
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "scope": "openid profile",
        "kid": "1",  # Match the key ID from JWKS
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "1"})


@app.get("/.well-known/openid-configuration")
async def openid_configuration():
    """Return OpenID Connect configuration."""
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        "claims_supported": ["sub", "iss", "iat", "exp"],
        "code_challenge_methods_supported": ["S256"],
    }


@app.get("/.well-known/jwks.json")
async def jwks():
    """Return JWKS (JSON Web Key Set)."""
    return JWKS


@app.get("/authorize")
async def authorize(
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

    # Validate client
    if client_id not in clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    # Validate redirect URI
    if redirect_uri not in clients[client_id]["redirect_uris"]:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")

    # Validate PKCE if provided
    if code_challenge is not None:
        if code_challenge_method != "S256":
            raise HTTPException(status_code=400, detail="Only S256 PKCE is supported")

    # Generate authorization code
    code = os.urandom(32).hex()

    # Store authorization details
    authorization_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
    }

    # Store PKCE challenge if provided
    if code_challenge:
        pkce_challenges[code] = code_challenge

    # Redirect back to client with the code
    params = {"code": code, "state": state}
    return RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}")


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
    else:
        # If not PKCE, verify client secret
        if not client_secret:
            raise HTTPException(status_code=400, detail="Client secret required")

        if client_secret != clients[client_id]["client_secret"]:
            raise HTTPException(status_code=400, detail="Invalid client secret")

    # Clean up the used code and PKCE challenge
    del authorization_codes[code]
    if code in pkce_challenges:
        del pkce_challenges[code]

    # Generate access token
    access_token = generate_token("user123")

    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,  # 15 minutes
            "scope": auth_details["scope"],
        }
    )

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
