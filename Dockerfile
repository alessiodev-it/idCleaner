# { 1: True, 0: False }
# python:3.12 | python:3.12-slim | python:3.12-alpine | gcr.io/distroless/python3-debian12

FROM python:3.12-slim

# '.pyc' and 'docker logs'
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# no pip dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends <LIBRARY> \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 'copy' prj and 'build' future data-files
COPY . .
RUN mkdir -p data records

CMD ["python", "main.py"]
