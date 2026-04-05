FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first (smaller, no CUDA)
RUN pip install --no-cache-dir torch==2.2.2+cpu torchvision==0.17.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install rest of dependencies
RUN pip install --no-cache-dir \
    flask==3.1.0 \
    ultralytics==8.3.50 \
    opencv-python-headless==4.10.0.84 \
    numpy>=1.24.0 \
    Pillow>=10.0.0 \
    matplotlib>=3.7.0 \
    reportlab>=4.0.0 \
    werkzeug>=3.0.0

COPY . .

EXPOSE 8080

CMD ["python", "app.py"]
