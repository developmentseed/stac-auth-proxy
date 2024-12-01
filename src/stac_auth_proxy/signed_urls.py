from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import hashlib
import base64
import urllib.parse


@dataclass
class SignedPayload:
    href: str
    exp: int
    meta: str
    sig: str

    @classmethod
    def build(cls, *, secret_key: str, href: str, exp: int, **meta_dict) -> str:
        """Generate a signed payload the given parameters using HMAC-SHA256."""
        b64_meta = base64.urlsafe_b64encode(stringify_dict(meta_dict).encode()).decode()

        params = {"href": href, "exp": exp, "meta": b64_meta}
        params_str = stringify_dict(params)

        signature = hmac.new(
            secret_key.encode(),
            params_str.encode(),
            hashlib.sha256,
        ).digest()
        b64_signature = base64.urlsafe_b64encode(signature).decode()

        return cls(
            href=href,
            exp=exp,
            meta=b64_meta,
            sig=b64_signature,
        )

    @property
    def valid_expiration(self) -> bool:
        """Verify that the signature is not expired."""
        return datetime.now(timezone.utc).timestamp() > self.exp

    @property
    def valid_signature(self) -> bool:
        """Verify that the payload is signed and not expired."""
        expected_signature = self.build(href=self.href, exp=self.exp, **self.meta)
        return hmac.compare_digest(expected_signature.sig, self.sig)

    @property
    def meta_dict(self):
        """Decoded meta data"""
        return {
            k: v[0]
            for k, v in urllib.parse.parse_qs(
                base64.urlsafe_b64decode(self.meta).decode()
            ).items()
        }

    def as_qs(self):
        """Return the query string"""
        return urllib.parse.urlencode(
            {
                "href": self.href,
                "exp": self.exp,
                "meta": self.meta,
                "sig": self.sig,
            }
        )


def stringify_dict(params: dict) -> str:
    """
    Sort the parameters and return them as a string.
    """
    return "&".join(f"{k}={params[k]}" for k in sorted(params))
