"""JWKS (JSON Web Key Set) generation for OAuth2 token validation.

CIPHER-031: OAuth2 Token Validation
- Generates JWKS endpoint at /oauth/.well-known/jwks.json
- Public keys for Bearer token signature validation
- Redis-stored public keys for distributed validation
"""
from __future__ import annotations

import json
import os
from cryptography.hazmat.primitives import serialization
import base64
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import logging
import warnings

logger = logging.getLogger(__name__)

# Generate RSA key pair for JWKS
def generate_jwks_keys(key_size: int = 2048) -> dict:
    """Generate RSA key pair and return as JWKS dict.

    Returns:
        dict with 'keys' list containing JWK key objects suitable for
        /oauth/.well-known/jwks.json endpoint response.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # Serialize public key to PEM
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Build JWK key object
    from cryptography.hazmat.primitives.asymmetric import rsa as rsa_mod

    # Extract modulus and public exponent
    numbers = private_key.public_key().public_numbers()
    modulus_base64 = base64.urlsafe_b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")).decode().rstrip("=")
    exponent_base64 = base64.urlsafe_b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")).decode().rstrip("=")

    jwk_key = {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": os.environ.get("JEFREY_JWKS_KID", "jefrey-default"),
        "n": modulus_base64,
        "e": exponent_base64,
    }

    return {"keys": [jwk_key]}
def generate_jwsk_keys(*args, **kwargs) -> dict:  # compat typo — deprecated
    warnings.warn("generate_jwsk_keys typo deprecated, use generate_jwks_keys", DeprecationWarning, stacklevel=2)
    return generate_jwks_keys(*args, **kwargs)



# Write JWKS to file for endpoint
def write_jwks_file(keys: dict, path: str = "src/jefrey/oauth2/jwks.json") -> str:
    """Write JWKS keys to JSON file at specified path.

    Creates parent directories if needed.

    Args:
        keys: JWKS dict from generate_jwsk_keys()
        path: Output file path (default: src/jefrey/oauth2/jwks.json)

    Returns:
        Absolute path to written file
    """
    output_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", path.replace("src/", ""))
    # Simpler: just write relative to the module
    real_path = os.path.join(os.path.dirname(__file__), path.split("/")[-1] if "/" in path else path)
    
    # Actually write to the specified path relative to project root
    real_path = os.path.join(os.getcwd(), "src", "jefrey", "oauth2", "jwks.json")
    
    os.makedirs(os.path.dirname(real_path), exist_ok=True)
    
    with open(real_path, "w") as f:
        json.dump(keys, f, indent=2)
    
    logger.info("JWKS written to %s", real_path)
    return real_path


# Generate and write JWKS
def generate_and_write_jwks(key_size: int = 2048, path: str = "src/jefrey/oauth2/jwks.json") -> str:
    """Generate RSA key pair and write JWKS JSON file.

    Convenience function for initial setup and rotation.

    Args:
        key_size: RSA key size in bits (default 2048)
        path: Output file path relative to project root

    Returns:
        Path to written JWKS file
    """
    keys = generate_jwks_keys(key_size=key_size)
    return write_jwks_file(keys=keys, path=path)
def generate_and_write_jwsk(*args, **kwargs) -> str:  # compat typo — deprecated
    warnings.warn("generate_and_write_jwsk typo deprecated, use generate_and_write_jwks", DeprecationWarning, stacklevel=2)
    return generate_and_write_jwks(*args, **kwargs)



# In-memory JWKS cache (for fast endpoint response)
_jwks_cache: dict | None = None
_jwks_generation_time: float = 0.0
_JWKS_TTL_SECONDS = 86400  # 24 hours


def get_jwks(force_refresh: bool = False) -> dict:
    """Get JWKS from cache or generate fresh keys.

    Implements TTL-based caching to avoid unnecessary key generation.

    Args:
        force_refresh: If True, bypass cache and regenerate keys

    Returns:
        JWKS dict with 'keys' list
    """
    global _jwks_cache, _jwks_generation_time

    import time as time_module

    if _jwks_cache is None or force_refresh:
        _jwks_cache = generate_jwks_keys()
        _jwks_generation_time = time_module.time()
        logger.info("JWKS cache refreshed (force=%s)", force_refresh)

    elapsed = time_module.time() - _jwks_generation_time
    if elapsed > _JWKS_TTL_SECONDS and not force_refresh:
        _jwks_cache = generate_jwks_keys()
        _jwks_generation_time = time_module.time()
        logger.info("JWKS cache expired after %.1f hours, refreshed", elapsed / 3600)

    return _jwks_cache