# Module-level _rotate_hmac_key_internal for signing_routes.py
# Rotates HMAC key and updates kids dict for dual-verify support
def _rotate_hmac_key_internal() -> Tuple[str, str]:
    """Rotate HMAC key and update kids dict for dual-verify support.

    Behavior:
    - Multi-key mode (JEFREY_EVENTBUS__HMAC_KEYS_JSON): adds new key as next kid version
    - Single key mode: promotes current key to V1, new key becomes V2
    - Returns (new_key, new_kid) tuple
    """
    import secrets
    import os

    if os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON"):
        # Multi-key mode: add new key as next kid version
        keys = json.loads(os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON"))
        new_kid = "v2"
        new_key = secrets.token_hex(32)
        keys[new_kid] = new_key
        # Update env var (note: this only changes in-memory, .env would need separate write)
        os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = json.dumps(keys, sort_keys=True)
        return new_key, new_kid
    else:
        # Single key mode: generate new key and set kid to v2
        new_key = secrets.token_hex(32)
        os.environ["JEFREY_EVENTBUS__HMAC_KID"] = "v2"
        os.environ["JEFREY_EVENTBUS__HMAC_KEY"] = new_key
        return new_key, "v2"