"""Shared fixtures of the integration suite. `world4` (F4: farm A with 10 irrigated parcels, 3 assigned to a worker, injected clock) is
exposed here so that a test module that uses it without importing it (test_f4_test_hygiene.py) still finds it."""
from tests.integration._f4 import world4  # noqa: F401
