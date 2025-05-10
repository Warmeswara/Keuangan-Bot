FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt requirements.txt
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot/main.py"]
