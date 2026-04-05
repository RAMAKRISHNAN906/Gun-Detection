FROM python:3.11-slim

# Force fresh build v3
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install torch CPU first
RUN pip install --no-cache-dir \
    torch==2.3.1+cpu \
    torchvision==0.18.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install everything else - let pip resolve numpy automatically
RUN pip install --no-cache-dir \
    flask==3.1.0 \
    werkzeug==3.1.3 \
    gunicorn==21.2.0 \
    ultralytics==8.3.50 \
    opencv-python-headless==4.10.0.84 \
    Pillow==10.4.0 \
    matplotlib==3.8.4 \
    reportlab==4.2.2

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "300", "--workers", "1", "app:app"]
