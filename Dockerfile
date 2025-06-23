# Use official Python 3.11 image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Expose the port for Flask (if needed)
EXPOSE 8080

# Start the bot
CMD ["python", "main.py"]
