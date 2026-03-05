FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    nmap \
    git \
    curl \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install security tools - clone only (dependencies can be installed per-tool as needed)
RUN git clone --depth 1 https://github.com/laramies/theHarvester.git /opt/theHarvester || true

RUN git clone --depth 1 https://github.com/thewhiteh4t/FinalRecon.git /opt/FinalRecon || true

RUN git clone --depth 1 https://github.com/m4ll0k/SecretFinder.git /opt/SecretFinder || true

RUN git clone --depth 1 https://github.com/m8sec/pymeta.git /opt/pymeta || true

RUN git clone --depth 1 https://github.com/alpkeskin/mosint.git /opt/mosint || true

RUN git clone --depth 1 https://github.com/mxrch/GHunt.git /opt/GHunt || true

RUN git clone --depth 1 https://github.com/j3ssie/osmedeus.git /opt/osmedeus || true

# Install Amass binary
RUN wget -q https://github.com/owasp-amass/amass/releases/download/v3.23.1/amass_linux_amd64.zip -O /tmp/amass.zip \
    && unzip -q /tmp/amass.zip -d /opt/amass \
    && mv /opt/amass/amass_linux_amd64/amass /usr/local/bin/ \
    && rm -rf /tmp/amass.zip /opt/amass || true

# Install ffuf binary
RUN wget -q https://github.com/ffuf/ffuf/releases/download/v2.1.0/ffuf_2.1.0_linux_amd64.tar.gz -O /tmp/ffuf.tar.gz \
    && mkdir -p /opt/ffuf \
    && tar -xzf /tmp/ffuf.tar.gz -C /opt/ffuf \
    && mv /opt/ffuf/ffuf /usr/local/bin/ \
    && rm -rf /tmp/ffuf.tar.gz /opt/ffuf || true

# Install common security wordlists (optional)
RUN mkdir -p /usr/share/seclists && \
    wget -q https://github.com/danielmiessler/SecLists/archive/refs/heads/master.zip -O /tmp/seclists.zip && \
    unzip -q /tmp/seclists.zip -d /usr/share/seclists && \
    mv /usr/share/seclists/SecLists-master/* /usr/share/seclists/ && \
    rm -rf /tmp/seclists.zip /usr/share/seclists/SecLists-master || true

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4567", "--reload"]
