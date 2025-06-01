FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Install system dependencies, including antiword
RUN sed -i 's/main/main contrib non-free/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    antiword \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
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
    odt2txt \
    unrar \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-pol \
 && rm -rf /var/lib/apt/lists/*

# Install Poetry and configure it
RUN pip install poetry && poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --only main

# Install Playwright dependencies
RUN playwright install

# Run the application
CMD ["uvicorn", "minerva.api.main:app", "--host", "0.0.0.0", "--port", "8000"]