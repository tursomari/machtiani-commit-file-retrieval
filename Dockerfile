# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libffi-dev \
    libssl-dev \
    libmagic1 \
    libmagic-dev \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install the specified version of Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION

# Set the working directory
WORKDIR /app

# Copy only the pyproject.toml and poetry.lock to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install Python dependencies via Poetry
RUN poetry install --no-root --only main

