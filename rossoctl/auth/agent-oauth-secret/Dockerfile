# This file has been modified with the assistance of Bob

# Use minimal Python base image
FROM python:3.15-slim@sha256:94d3426f1def7db4a106a232ac121bfd975393e5dfd40a619b955fae45fe7913

# Set work directory
WORKDIR /app

# Install dependencies from requirements.txt
COPY auth/agent-oauth-secret/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities from unified context
COPY common/ ./common/

# Copy auth shared utilities
COPY auth/shared_utils.py ./rossoctl/auth/

# Copy the script
COPY auth/agent-oauth-secret/agent_oauth_secret.py .

# Create non-root user for runtime security
RUN useradd -u 1001 -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER 1001

# Run the agent OAuth setup
CMD ["python", "agent_oauth_secret.py"]