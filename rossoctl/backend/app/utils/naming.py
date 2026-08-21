# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Helpers for deriving valid Kubernetes resource names from user-supplied text.
"""

import re

# RFC-1123 DNS label — the shape of a Kubernetes resource / namespace name:
# lowercase alphanumeric plus '-', starting and ending with an alphanumeric, ≤63 chars.
# Single source of truth for this pattern across the backend (routers previously each
# defined their own identical ``re.compile(...)`` — chat.py, acp.py, agents_authbridge.py).
#
# Two forms:
#   * K8S_NAME_PATTERN — regex string, for FastAPI ``Path(pattern=..., max_length=...)`` so
#     malformed path params are rejected with 422 before any handler/logger runs (#2395).
#   * K8S_NAME_RE — compiled, for direct ``.fullmatch()`` / ``.match()`` validation.
# The length bound (``{0,61}`` between the anchors) makes the regex self-sufficient, so it
# holds standalone as well as behind Path's max_length.
K8S_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$"
K8S_NAME_MAX_LENGTH = 63
K8S_NAME_RE = re.compile(K8S_NAME_PATTERN)


def sanitize_k8s_name(name: str) -> str:
    """Sanitize a name to be valid for Kubernetes resource names.

    Falls back to ``"resource"`` when the input sanitizes to nothing (empty or
    all-punctuation), since a Kubernetes name may not be empty.
    """
    out = "".join(c.lower() if c.isalnum() or c in ("-", ".") else "-" for c in name)
    out = out.strip("-.")
    return out or "resource"
