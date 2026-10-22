FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# База лежит в /data (именуемый volume), переживающем пересборки образа.
ENV DB_PATH=/data/training_bot.db

CMD ["python", "main.py"]
