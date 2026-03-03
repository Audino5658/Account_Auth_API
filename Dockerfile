# Use a lightweight Python image
FROM python:3.11-slim

# Install uv (The fast package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency definition
COPY pyproject.toml .

# Create virtual environment and install dependencies
RUN uv venv .venv
# Install dependencies using uv pip interface
RUN uv pip install .

# Copy the application code
COPY acct_auth_app ./acct_auth_app

# Make sure the venv is on the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port
EXPOSE 8000

# Run the application (use PORT env var if provided, else default to 8000)
CMD ["sh", "-c", "uvicorn acct_auth_app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
