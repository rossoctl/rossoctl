# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Helpers for deriving valid Kubernetes resource names from user-supplied text.
"""


def sanitize_k8s_name(name: str) -> str:
    """Sanitize a name to be valid for Kubernetes resource names.

    Falls back to ``"resource"`` when the input sanitizes to nothing (empty or
    all-punctuation), since a Kubernetes name may not be empty.
    """
    out = "".join(c.lower() if c.isalnum() or c in ("-", ".") else "-" for c in name)
    out = out.strip("-.")
    return out or "resource"
