"""P4-07: Policy guest default + rate limit deny (Axiom #2, #5, CIPHER-026)."""
import pytest

def test_policy_context_guest_default():
    from src.jefrey.core.policy import PolicyContext
    ctx = PolicyContext()
    assert ctx.user_id is None
    assert ctx.user_role == "guest"


def test_policy_unknown_tool_deny():
    from src.jefrey.core.policy import PolicyContext, PolicyEngine
    eng = PolicyEngine()
    ctx = PolicyContext(user_id="u1", user_role="user")
    res = eng.decide("tool_that_does_not_exist_xyz", {}, ctx=ctx)
    # unknown tools must be deny (least privilege) — not allow
    assert res.decision.value in ("deny", "DENY") or str(res.decision).lower().startswith("deny")


def test_rate_limit_fail_closed_no_user_id():
    from src.jefrey.core.rate_limit import RateLimiter
    rl = RateLimiter(redis_url="redis://localhost:6379/0")
    # is_allowed_sync with empty user_id must deny without needing Redis
    dec = rl.is_allowed_sync("", "some_tool")
    assert dec == "deny"
