FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies early to cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the bot code
COPY . .

# Default command
CMD ["python3", "main.py"]
