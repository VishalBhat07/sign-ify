FROM python:3.11-slim

WORKDIR /app

# Copy the core project directories
COPY Sign2Text/ /app/Sign2Text/
COPY crypto/ /app/crypto/

# Install dependencies
RUN pip install --no-cache-dir -r /app/Sign2Text/requirements.txt

# Hugging Face Spaces port requirement
ENV PORT=7860
# HF handles SSL proxying, so we disable local Flask SSL
ENV DISABLE_SSL=1 

EXPOSE 7860

WORKDIR /app/Sign2Text

# Start the application
CMD ["python", "app_conference_secure.py"]
