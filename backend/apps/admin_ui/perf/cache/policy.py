"""Cache policy definitions for hot endpoints.

This module centralizes TTL/stale settings so router/service code stays
consistent and easy to tune during perf work.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CachePolicy:
    """Cache policy for a hot read endpoint.

    Attributes:
        ttl_seconds: Fresh TTL for cache entries.
        stale_seconds: Additional stale window for SWR (0 disables SWR).
    """

    ttl_seconds: float
    stale_seconds: float = 0.0


# Default policies used across admin_ui hot reads.
HOT_READ_POLICY = CachePolicy(ttl_seconds=2.0, stale_seconds=10.0)

