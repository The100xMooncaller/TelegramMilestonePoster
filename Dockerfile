# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Now copy the rest of the app files
COPY . .

# Expose Flask port if your app uses Flask (optional, since it's a background worker)
EXPOSE 8080

# Start the bot
CMD ["python3", "main.py"]
