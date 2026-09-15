"""HMAC key rotation utilities for Jefrey EventBus.

Provides a rotate_hmac_key() function that:
1. Generates a new 32-byte hex HMAC key
2. Adds it to the keys dict as the next kid version
3. Can be called from a FastAPI endpoint
"""
from __future__ import annotations

import os
import secrets
import json
from typing import Dict, Tuple, Optional

# Kid version sequence
_KID_SEQUENCE = ["v1", "v2", "v3", "v4", "v5"]


def rotate_hmac_key() -> Tuple[str, str]:
    """Generate a new HMAC key and return (new_key_hex, new_kid).
    
    The new key is added to the existing keys dict (via env var JEFREY_EVENTBUS__HMAC_KEYS_JSON)
    or as the new V2 key if using single-key mode.
    
    Returns:
        Tuple of (new_key_hex_string, new_kid_string)
    """
    new_key = secrets.token_hex(32)  # 32 bytes = 256 bits
    
    # Try to get existing keys from env
    keys_json = os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", "")
    
    if keys_json:
        # Multi-key mode: add new key as next version
        try:
            existing_keys: Dict[str, str] = json.loads(keys_json)
        except json.JSONDecodeError:
            existing_keys = {}
        
        # Find the highest existing kid number
        existing_numbers = []
        for kid in existing_keys:
            for i, prefix in enumerate(_KID_SEQUENCE):
                if kid == prefix:
                    existing_numbers.append(i)
                    break
        
        next_num = max(existing_numbers) + 1 if existing_numbers else 1
        new_kid = _KID_SEQUENCE[min(next_num, len(_KID_SEQUENCE) - 1)]
        existing_keys[new_kid] = new_key
        
        # Update env var
        os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = json.dumps(existing_keys)
    else:
        # Single key mode: set as V2, V1 stays as current key
        key_v1 = os.getenv("JEFREY_EVENTBUS__HMAC_KEY", "")
        kid = os.getenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
        
        new_kid = "v2" if kid == "v1" else "v1"
        
        # Update env vars
        os.environ["JEFREY_EVENTBUS__HMAC_KEY"] = new_key if new_kid == "v1" else key_v1
        os.environ["JEFREY_EVENTBUS__HMAC_KEY_V2"] = new_key if new_kid == "v2" else key_v1
        os.environ["JEFREY_EVENTBUS__HMAC_KID"] = new_kid
    
    return new_key, new_kid