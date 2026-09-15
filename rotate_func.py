# Module-level _rotate_hmac_key_internal for signing_routes.py
# Rotates HMAC key and updates kids dict for dual-verify support
def _rotate_hmac_key_internal() -> Tuple[str, str]:
    """Rotate HMAC key and update kids dict for dual-verify support."""
    import secrets, os
    if os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON"):
        import json
        keys = json.loads(os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON"))
        new_key = secrets.token_hex(32)
        keys["v2"] = new_key
        os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = json.dumps(keys, sort_keys=True)
        return new_key, "v2"
    else:
        new_key = secrets.token_hex(32)
        os.environ["JEFREY_EVENTBUS__HMAC_KID"] = "v2"
        os.environ["JEFREY_EVENTBUS__HMAC_KEY"] = new_key
        return new_key, "v2"