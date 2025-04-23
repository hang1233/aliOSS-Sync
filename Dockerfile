FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 2003

CMD ["gunicorn", "--bind", "0.0.0.0:2003", "app:app"] 