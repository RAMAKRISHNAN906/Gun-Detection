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

# Install torch CPU first
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    torchvision==0.17.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install all other packages together so pip resolves numpy compatibility
RUN pip install --no-cache-dir \
    "numpy==1.26.4" \
    "flask==3.1.0" \
    "ultralytics==8.1.0" \
    "opencv-python-headless==4.9.0.80" \
    "Pillow>=10.0.0" \
    "matplotlib>=3.7.0" \
    "reportlab>=4.0.0" \
    "werkzeug>=3.0.0"

# Force reinstall numpy to ensure single clean version
RUN pip install --no-cache-dir --force-reinstall numpy==1.26.4

COPY . .

EXPOSE 8080

CMD ["python", "app.py"]
