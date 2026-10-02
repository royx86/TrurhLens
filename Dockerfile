FROM node:22-bookworm-slim AS frontend-build

WORKDIR /usr/src/app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY --from=frontend-build /usr/src/app/frontend/dist ./frontend/dist

RUN printf '%s\n' \
    'server {' \
    '    listen 8080;' \
    '    server_name _;' \
    '    root /app/frontend/dist;' \
    '' \
    '    location /api/ {' \
    '        proxy_pass http://127.0.0.1:8000;' \
    '        proxy_set_header Host $host;' \
    '        proxy_set_header X-Real-IP $remote_addr;' \
    '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '        proxy_set_header X-Forwarded-Proto $scheme;' \
    '    }' \
    '' \
    '    location = /health {' \
    '        proxy_pass http://127.0.0.1:8000/health;' \
    '        proxy_set_header Host $host;' \
    '    }' \
    '' \
    '    location /docs {' \
    '        proxy_pass http://127.0.0.1:8000;' \
    '        proxy_set_header Host $host;' \
    '    }' \
    '' \
    '    location /openapi.json {' \
    '        proxy_pass http://127.0.0.1:8000;' \
    '        proxy_set_header Host $host;' \
    '    }' \
    '' \
    '    location / {' \
    '        try_files $uri $uri/ /index.html;' \
    '    }' \
    '}' \
    > /etc/nginx/sites-available/default

EXPOSE 8080

CMD ["sh", "-c", "nginx_port=${PORT:-8080}; sed -i \"s/listen 8080/listen ${nginx_port}/\" /etc/nginx/sites-available/default; uvicorn app.main:app --host 127.0.0.1 --port 8000 & exec nginx -g 'daemon off;'"]
