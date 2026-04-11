# Use Python slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install uv (the package manager used in the tutorial)
RUN pip install uv

# Copy your project files
COPY pyproject.toml .
COPY omni.py .

# Install dependencies using uv
RUN uv sync

# Set the entrypoint to run your server
ENTRYPOINT ["uv", "run", "omni.py"]
