FROM python:3.13-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY queries.yml .

EXPOSE 9200

CMD ["python", "main.py"]
