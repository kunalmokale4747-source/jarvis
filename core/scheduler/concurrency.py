"""Cross-service in-process lock.

This protects the single API process against duplicate concurrent processing.
It does not protect separate API worker processes.
"""

from __future__ import annotations

import threading

PROCESSING_LOCK = threading.Lock()
