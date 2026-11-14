# Use minimal Python base image
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

# Set work directory
WORKDIR /app

# Install dependencies first (better layer caching)
COPY auth/mlflow-oauth-secret/requirements.txt .
RUN chmod 644 requirements.txt && pip install --no-cache-dir -r requirements.txt

# Copy scripts and ensure they're readable
COPY auth/mlflow-oauth-secret/mlflow_oauth_secret.py .
RUN chmod 644 mlflow_oauth_secret.py

# OpenShift runs as random UID, ensure /app is accessible
RUN chmod -R g=u /app

# Register client
CMD ["python", "mlflow_oauth_secret.py"]
