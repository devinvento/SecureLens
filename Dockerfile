FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl wget nmap unzip \
    postgresql-client redis-tools \
    gcc libpq-dev \
    ruby ruby-dev \
    build-essential \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------
# Install theHarvester
# ---------------------------
RUN git clone https://github.com/laramies/theHarvester.git /opt/theHarvester
WORKDIR /opt/theHarvester
RUN pip3 install .

# ---------------------------
# Install Go
# ---------------------------
RUN wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz -O /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

ENV PATH="/usr/local/go/bin:/root/go/bin:$PATH"

# ---------------------------
# Install Amass
# ---------------------------
RUN go install github.com/owasp-amass/amass/v4/...@master && \
    mv /root/go/bin/amass /usr/local/bin/amass

# ---------------------------
# Install Mosint
# ---------------------------
RUN go install github.com/alpkeskin/mosint/v3/cmd/mosint@latest && \
    mv /root/go/bin/mosint /usr/local/bin/mosint

# ---------------------------
# Install PyMeta
# ---------------------------
RUN pip install pymeta

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"

# ---------------------------
# Install GHunt
# ---------------------------


# Clone GHunt
RUN git clone https://github.com/mxrch/GHunt.git /opt/ghunt

# Install GHunt dependencies system-wide
RUN cd /opt/ghunt && poetry config virtualenvs.create false && poetry install --no-root

# Create a wrapper so you can run "ghunt" globally
RUN echo '#!/bin/bash\npython3 /opt/ghunt/main.py "$@"' > /usr/local/bin/ghunt \
    && chmod +x /usr/local/bin/ghunt

# Clone WhatWeb repo and install
RUN git clone https://github.com/urbanadventurer/WhatWeb.git /opt/whatweb && \
    cd /opt/whatweb && \
    gem build whatweb.gemspec && \
    gem install whatweb-*.gem && \
    ln -s /usr/local/bin/whatweb /usr/bin/whatweb || true


RUN go install github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    mv /root/go/bin/httpx /usr/local/bin/httpx

# ---------------------------
# Install Masscan
# ---------------------------
RUN git clone https://github.com/robertdavidgraham/masscan.git /opt/masscan && \
    cd /opt/masscan && \
    make -j && \
    cp bin/masscan /usr/local/bin/masscan












# ---------------------------
# Copy project
# ---------------------------
WORKDIR /app
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","4567","--reload"]