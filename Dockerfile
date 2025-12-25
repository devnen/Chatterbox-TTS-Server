FROM docker.io/nvidia/cuda:12.8.1-runtime-ubuntu22.04

ARG RUNTIME=nvidia

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
# Set the Hugging Face home directory for better model caching
ENV HF_HOME=/app/hf_cache

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a symlink for python3 to be python for convenience
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set up working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt
# Conditionally install NVIDIA dependencies if RUNTIME is set to 'nvidia'
COPY requirements-nvidia.txt .

RUN if [ "$RUNTIME" = "nvidia" ]; then \
    pip3 install --no-cache-dir -r requirements-nvidia.txt; \
    fi
# Copy the rest of the application code
COPY . .

# Create required directories for the application (fixed syntax error)
RUN mkdir -p model_cache reference_audio outputs voices logs hf_cache

# Expose the port the application will run on
EXPOSE 8004

# Command to run the application
CMD ["python3", "server.py"]