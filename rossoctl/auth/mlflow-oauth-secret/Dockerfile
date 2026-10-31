# Use minimal Python base image
FROM python:3.15-slim@sha256:94d3426f1def7db4a106a232ac121bfd975393e5dfd40a619b955fae45fe7913

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
