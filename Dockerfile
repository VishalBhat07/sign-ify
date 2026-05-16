FROM python:3.11-slim

# Set up the non-root user required by Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy and install requirements first (better caching)
COPY --chown=user Sign2Text/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the core project directories
COPY --chown=user Sign2Text/ /app/Sign2Text/
COPY --chown=user crypto/ /app/crypto/

# Hugging Face Spaces port requirement
ENV PORT=7860
# HF handles SSL proxying, so we disable local Flask SSL
ENV DISABLE_SSL=1 

EXPOSE 7860

WORKDIR /app/Sign2Text

# Start the application
CMD ["python", "app_conference_secure.py"]
