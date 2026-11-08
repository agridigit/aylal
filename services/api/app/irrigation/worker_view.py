"""Single redaction point of every F4 output addressed to a worker (decisions point 19)."""
try:
    from app.domain.advice_worker_view import (
        STAFF_ROLES,
        WORKER_ADVICE_KEYS,
        WORKER_ASSUMPTION_KEYS,
        advice_view,
        worker_assumptions,
    )
except ImportError:  # worker image: flat copy of the same file
    from advice_worker_view import (  # type: ignore[no-redef,import-not-found,unused-ignore]
        STAFF_ROLES,
        WORKER_ADVICE_KEYS,
        WORKER_ASSUMPTION_KEYS,
        advice_view,
        worker_assumptions,
    )

__all__ = ["STAFF_ROLES", "WORKER_ADVICE_KEYS", "WORKER_ASSUMPTION_KEYS", "advice_view", "worker_assumptions"]
