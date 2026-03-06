FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl wget nmap \
    postgresql-client redis-tools \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install theharvester separately
RUN git clone https://github.com/laramies/theHarvester.git /opt/theHarvester
WORKDIR /opt/theHarvester
RUN pip3 install .

# Copy dependency file first (better Docker cache)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","4567","--reload"]