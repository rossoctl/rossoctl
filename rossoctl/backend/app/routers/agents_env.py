# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
.env import helpers for the agent creation UI.

Parses pasted ``.env`` content into structured env vars, and fetches ``.env``
files from a URL behind SSRF protection (private/loopback/link-local ranges are
rejected).

Split out of ``agents.py``; re-exported there for backwards compatibility.
Routes are attached to ``env_router`` and composed onto the main agents router
by ``agents.py`` -- see the ordering note there.
"""

import ipaddress
import json
import logging
import re
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import ROLE_OPERATOR, require_roles
from app.routers.agents_models import (
    FetchEnvUrlRequest,
    FetchEnvUrlResponse,
    ParseEnvRequest,
    ParseEnvResponse,
)

logger = logging.getLogger(__name__)

env_router = APIRouter()


BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]


def is_ip_blocked(ip_str: str) -> bool:
    """Check if IP is in blocked range for SSRF protection."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in BLOCKED_IP_RANGES)
    except ValueError:
        return False


@env_router.post(
    "/parse-env",
    response_model=ParseEnvResponse,
    dependencies=[Depends(require_roles(ROLE_OPERATOR))],
)
async def parse_env_file(request: ParseEnvRequest) -> ParseEnvResponse:
    """
    Parse .env file content and return structured environment variables.
    Supports:
    - Standard KEY=value format
    - Extended JSON format for secretKeyRef and configMapKeyRef

    Example extended format:
    SECRET_KEY='{"valueFrom": {"secretKeyRef": {"name": "openai-secret", "key": "apikey"}}}'
    """
    env_vars = []
    warnings = []

    lines = request.content.strip().split("\n")

    for line_num, line in enumerate(lines, 1):
        # Skip empty lines and comments
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse KEY=VALUE
        if "=" not in line:
            warnings.append(f"Line {line_num}: Invalid format, missing '='")
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Validate environment variable name
        env_var_pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        if not re.match(env_var_pattern, key):
            warnings.append(
                f"Line {line_num}: Invalid variable name '{key}'. "
                "Name must start with a letter or underscore and contain only "
                "letters, digits, and underscores."
            )
            continue

        # Remove quotes if present
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        # Try to parse as JSON (for extended format)
        if value.startswith("{") and value.endswith("}"):
            try:
                parsed = json.loads(value)
                if "valueFrom" in parsed:
                    env_var = {"name": key, "valueFrom": parsed["valueFrom"]}
                    env_vars.append(env_var)
                    continue
                else:
                    # It's valid JSON but not our expected format, treat as string
                    warnings.append(
                        f"Line {line_num}: JSON value without 'valueFrom' key, treating as string"
                    )
            except json.JSONDecodeError as e:
                warnings.append(f"Line {line_num}: Invalid JSON in value: {str(e)}")

        # Standard value
        env_vars.append({"name": key, "value": value})

    return ParseEnvResponse(envVars=env_vars, warnings=warnings if warnings else None)


@env_router.post(
    "/fetch-env-url",
    response_model=FetchEnvUrlResponse,
    dependencies=[Depends(require_roles(ROLE_OPERATOR))],
)
async def fetch_env_from_url(request: FetchEnvUrlRequest) -> FetchEnvUrlResponse:
    """
    Fetch .env file content from a remote URL.
    Supports HTTP/HTTPS URLs with security validations to prevent SSRF attacks.

    Example URLs:
    - https://raw.githubusercontent.com/rossoctl/examples/main/a2a/git_issue_agent/.env.openai
    - https://example.com/config/.env
    """
    import os
    import ssl
    from pathlib import Path

    logger.info(f"Fetching .env file from URL: {request.url}")

    # Log SSL/Certificate configuration
    logger.info(f"SSL_CERT_FILE env: {os.environ.get('SSL_CERT_FILE', 'NOT SET')}")
    logger.info(f"REQUESTS_CA_BUNDLE env: {os.environ.get('REQUESTS_CA_BUNDLE', 'NOT SET')}")
    logger.info(f"Default SSL context: {ssl.get_default_verify_paths()}")

    # Check if cert files exist
    cert_paths = [
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/ssl/certs/ca-bundle.crt",
        "/usr/local/share/ca-certificates/",
    ]
    for cert_path in cert_paths:
        exists = (
            Path(cert_path).exists() if cert_path.endswith(".crt") else Path(cert_path).is_dir()
        )
        logger.info(f"Certificate path {cert_path}: {'EXISTS' if exists else 'NOT FOUND'}")

    # Security validation - only allow http/https
    parsed_url = urlparse(request.url)
    if parsed_url.scheme not in ["http", "https"]:
        raise HTTPException(status_code=400, detail="Only HTTP/HTTPS URLs are supported")

    # Validate hostname exists
    if not parsed_url.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL: hostname not found")

    # Prevent SSRF attacks - block private IPs
    try:
        ip = socket.gethostbyname(parsed_url.hostname)
        logger.debug(f"Resolved {parsed_url.hostname} to {ip}")
        if is_ip_blocked(ip):
            logger.warning(f"Blocked private IP address: {ip}")
            raise HTTPException(
                status_code=400, detail="Private IP addresses are not allowed for security reasons"
            )
    except socket.gaierror as e:
        # Domain can't be resolved - log but let httpx handle it
        logger.warning(f"Could not resolve hostname {parsed_url.hostname}: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking IP for {parsed_url.hostname}: {e}")

    # Fetch content with timeout
    try:
        # Explicitly use system CA bundle instead of Kubernetes service account CA
        # Kubernetes sets SSL_CERT_FILE to /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        # which doesn't include public CAs like GitHub. We need to explicitly point to system CAs.
        ca_bundle_path = "/etc/ssl/certs/ca-certificates.crt"
        if not Path(ca_bundle_path).exists():
            # Fallback to alternative paths
            for fallback in ["/etc/ssl/certs/ca-bundle.crt", "/etc/pki/tls/certs/ca-bundle.crt"]:
                if Path(fallback).exists():
                    ca_bundle_path = fallback
                    break

        logger.info(f"Using CA bundle: {ca_bundle_path}")

        # Create SSL context with system certificates
        ssl_context = ssl.create_default_context(cafile=ca_bundle_path)

        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, verify=ssl_context
        ) as client:
            logger.debug(f"Making HTTP request to {request.url}")
            response = await client.get(request.url)
            response.raise_for_status()

            logger.info(f"Successfully fetched URL, content length: {len(response.text)} bytes")

            # Validate content isn't too large (max 1MB)
            content = response.text
            if len(content) > 1024 * 1024:
                raise HTTPException(status_code=413, detail="File content too large (max 1MB)")

            return FetchEnvUrlResponse(content=content, url=request.url)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching URL {request.url}: {e}")
        raise HTTPException(status_code=504, detail="Request timeout while fetching URL")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching URL {request.url}: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch URL: {e.response.status_code} {e.response.reason_phrase}",
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching URL {request.url}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching URL {request.url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
