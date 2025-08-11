# Use Python 3.12 slim image
FROM python:3.12-slim

# Install UV for dependency management
RUN pip install --no-cache-dir uv

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY aiseg2_publish.py aiseg2_clean.py main.py ./

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set Python to unbuffered mode
ENV PYTHONUNBUFFERED=1

# Default command runs the continuous execution mode
CMD ["uv", "run", "main.py"]