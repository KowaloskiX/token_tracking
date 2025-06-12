# -------------------------------------------------------------------------- #
# STAGE 1: Builder
#
# This stage installs all dependencies, including heavy build tools,
# and prepares the Python environment.
# -------------------------------------------------------------------------- #
FROM python:3.12-slim AS builder

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install poetry and dependencies (excluding torch - we'll install CPU version separately)
RUN pip install poetry
COPY poetry.lock pyproject.toml ./
RUN poetry install --only main --no-cache --no-root

# Install CPU-only PyTorch for production (smaller image size, no CUDA bloat)
RUN pip install --no-cache-dir torch>=2.6.0 torchvision>=0.21.0 --index-url https://download.pytorch.org/whl/cpu


# -------------------------------------------------------------------------- #
# STAGE 2: Final Production Image (API)
#
# This stage is the lean final image. It copies only the necessary
# runtime dependencies and our application code from the builder stage.
# -------------------------------------------------------------------------- #
FROM python:3.12-slim

# Install RUNTIME system dependencies
RUN sed -i 's/main/main contrib non-free/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    antiword \
    curl \
    libnss3 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    wget \
    xvfb \
    libreoffice \
    libreoffice-writer \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-pol \
    odt2txt \
    unrar \
 && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
WORKDIR /app
COPY . ./

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Set up runtime environment
ENV HF_HOME=/app/.cache/huggingface
VOLUME ["/app/.cache/huggingface"]

CMD ["uvicorn", "minerva.api.main:app", "--host", "0.0.0.0", "--port", "8000"]