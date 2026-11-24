# Backend Dockerfile: Python 3.11 with OpenCV & CUDA support libraries
FROM python:3.11-slim

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho OpenCV trong môi trường Debian Bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Tạo thư mục storage
RUN mkdir -p storage/uploads storage/outputs storage/coach_samples

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
