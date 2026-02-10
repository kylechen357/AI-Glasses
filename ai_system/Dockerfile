# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for MCP servers
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install MCP dependencies
RUN npm install -g @modelcontextprotocol/server-filesystem

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/vector_db data/conversations logs

# Set environment variables
ENV PYTHONPATH=/app
ENV OLLAMA_HOST=0.0.0.0

# Expose ports
EXPOSE 8000 11434

# Create startup script
RUN echo '#!/bin/bash\n\
ollama serve &\n\
sleep 10\n\
ollama pull llama3.2\n\
python main.py api --host 0.0.0.0 --port 8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/status || exit 1

# Start the application
CMD ["/app/start.sh"]
