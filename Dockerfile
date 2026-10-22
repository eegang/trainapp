FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# База в /app/data — на Bothost это персистентная папка, на VPS — volume из compose.
ENV DB_PATH=/app/data/training_bot.db

CMD ["python", "main.py"]
