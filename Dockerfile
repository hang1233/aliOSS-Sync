FROM node:16-alpine as frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

EXPOSE 2003

CMD ["gunicorn", "--bind", "0.0.0.0:2003", "--timeout", "3600", "--workers", "2", "app:app"] 