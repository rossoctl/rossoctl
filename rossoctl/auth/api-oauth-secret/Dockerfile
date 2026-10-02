# Use minimal Python base image
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

# Set work directory
WORKDIR /app

# Install dependencies first (better layer caching)
COPY auth/api-oauth-secret/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script
COPY auth/api-oauth-secret/register_api_client.py .

# Create non-root user for runtime security
RUN useradd -u 1001 -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER 1001

# Register API client
CMD ["python", "register_api_client.py"]
