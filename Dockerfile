FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ruby ruby-dev \
    libyaml-dev \
    zlib1g-dev \
    libffi-dev \
    pkg-config \
    libimage-exiftool-perl \
    git curl wget nmap unzip \
    ca-certificates \
    golang \
    postgresql-client redis-tools \
    chromium \
    && update-ca-certificates \
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
RUN git clone https://github.com/m8r0wn/pymeta.git /opt/pymeta && \
    cd /opt/pymeta && \
    pip3 install .

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
    gem install bundler && \
    cd /opt/whatweb && \
    bundle install && \
    ln -s /opt/whatweb/whatweb /usr/local/bin/whatweb && \
    chmod +x /opt/whatweb/whatweb


# ---------------------------
# Install Masscan
# ---------------------------
RUN git clone https://github.com/robertdavidgraham/masscan.git /opt/masscan && \
    cd /opt/masscan && \
    make -j && \
    cp bin/masscan /usr/local/bin/masscan



# ---------------------------
# Install ffuf
# ---------------------------
RUN go install github.com/ffuf/ffuf@latest && \
    mv /root/go/bin/ffuf /usr/local/bin/ffuf

# ---------------------------
# Install GAU (Get All URLs)
# ---------------------------
RUN go install github.com/lc/gau/v2/cmd/gau@latest && \
    mv /root/go/bin/gau /usr/local/bin/gau


# Install SecretFinder
RUN git clone https://github.com/m4ll0k/SecretFinder.git /opt/SecretFinder && \
    pip3 install -r /opt/SecretFinder/requirements.txt && \
    chmod +x /opt/SecretFinder/SecretFinder.py

# Install LinkFinder
RUN git clone https://github.com/GerbenJavado/LinkFinder.git /opt/LinkFinder && \
    pip3 install -r /opt/LinkFinder/requirements.txt && \
    ln -s /opt/LinkFinder/linkfinder.py /usr/local/bin/linkfinder


# ---------------------------
# Install Gobuster
# ---------------------------
RUN go install github.com/OJ/gobuster/v3@latest && \
    mv /root/go/bin/gobuster /usr/local/bin/gobuster



# ---------------------------
# Install Gospider
# ---------------------------

RUN go install github.com/OJ/gobuster/v3@latest && \
    go install github.com/jaeles-project/gospider@latest && \
    mv /root/go/bin/gobuster /usr/local/bin/gobuster && \
    mv /root/go/bin/gospider /usr/local/bin/gospider


# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# ---------------------------
# Install feroxbuster
# ---------------------------

RUN git clone https://github.com/epi052/feroxbuster.git /opt/feroxbuster && \
    cd /opt/feroxbuster && \
    cargo build --release && \
    cp target/release/feroxbuster /usr/local/bin/feroxbuster

# ---------------------------
# Install SecLists
# ---------------------------

# RUN git clone https://github.com/danielmiessler/SecLists.git /opt/SecLists



# ---------------------------
# Copy project
# ---------------------------
WORKDIR /app
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","4567","--reload"]