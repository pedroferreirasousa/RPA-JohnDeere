FROM python:3.11-slim

# Dependências de sistema para o Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget curl \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    xvfb x11vnc novnc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

RUN mkdir -p db data

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
