# Use Python 3.9 slim image as base
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements file and install dependencies
# We copy this separately from the rest of the code to leverage Docker's caching
# If requirements don't change, this layer will be cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Set up health check to verify container is healthy
# This checks if the app is responding to requests
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Command to run the application
# The flags mean:
# --server.port=8501: Run on port 8501
# --server.address=0.0.0.0: Listen on all network interfaces (important for Docker)
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableXsrfProtection=false"]
