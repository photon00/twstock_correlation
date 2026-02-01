FROM python:3.10-slim

WORKDIR /app

# Build deps for lxml (twstock); must install before pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]