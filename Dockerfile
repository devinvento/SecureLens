FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl wget nmap unzip \
    postgresql-client redis-tools \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first (better Docker cache)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install theHarvester separately
RUN git clone https://github.com/laramies/theHarvester.git /opt/theHarvester
WORKDIR /opt/theHarvester
RUN pip3 install .

# Install Go for building Amass
RUN wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz -O /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

ENV PATH="/usr/local/go/bin:$PATH"

# Install Amass (latest version via Go)
RUN go install github.com/owasp-amass/amass/v4/...@master && \
    mv $(go env GOPATH)/bin/amass /usr/local/bin/amass

# Copy project
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","4567","--reload"]
