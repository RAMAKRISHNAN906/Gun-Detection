FROM python:3.11-slim

# Force fresh build v2
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install torch CPU
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    torchvision==0.17.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install all packages in one shot so pip resolves compatibility
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    flask==3.1.0 \
    gunicorn==21.2.0 \
    ultralytics==8.1.0 \
    opencv-python-headless==4.9.0.80 \
    Pillow==10.4.0 \
    matplotlib==3.8.4 \
    reportlab==4.2.2 \
    werkzeug==3.0.3

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "300", "--workers", "1", "app:app"]
