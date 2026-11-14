# This file has been modified with the assistance of Bob

# Use minimal Python base image
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

# Set work directory
WORKDIR /app

# Install dependencies from requirements.txt
COPY auth/ui-oauth-secret/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities from unified context
COPY common/ ./common/

# Copy auth shared utilities
COPY auth/shared_utils.py ./rossoctl/auth/

# Copy the script
COPY auth/ui-oauth-secret/auth_secret.py .

# Create non-root user for runtime security
RUN useradd -u 1001 -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER 1001

# Register client
CMD ["python", "auth_secret.py"]