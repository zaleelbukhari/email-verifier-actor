"""
Email Verifier Pro — Usage Analytics

Tracks lifetime usage statistics across all actor runs using
a persistent named key-value store.

You can view these stats anytime in your Apify Console by
navigating to: Storage > Key-Value Stores > email-verifier-pro-stats
"""

from datetime import datetime, timezone

from apify import Actor


STATS_STORE_NAME = "email-verifier-pro-stats"
STATS_KEY = "lifetime_stats"


async def get_stats() -> dict:
    """Retrieve current lifetime statistics."""
    try:
        store = await Actor.open_key_value_store(name=STATS_STORE_NAME)
        stats = await store.get_value(STATS_KEY)
        return stats or _default_stats()
    except Exception:
        return _default_stats()


async def increment_stats(emails_verified: int = 0) -> dict:
    """
    Increment lifetime stats after a successful run.

    Args:
        emails_verified: Number of emails verified in this run.

    Returns:
        Updated stats dict.
    """
    store = await Actor.open_key_value_store(name=STATS_STORE_NAME)
    current = await store.get_value(STATS_KEY) or _default_stats()

    current["total_emails_verified"] = (
        current.get("total_emails_verified", 0) + emails_verified
    )
    current["total_runs"] = current.get("total_runs", 0) + 1
    current["last_run_at"] = datetime.now(timezone.utc).isoformat()

    await store.set_value(STATS_KEY, current)
    return current


def _default_stats() -> dict:
    """Return default stats structure."""
    return {
        "total_emails_verified": 0,
        "total_runs": 0,
        "last_run_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
