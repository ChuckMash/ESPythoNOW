FROM python:3.11-alpine AS build
RUN apk add --no-cache gcc musl-dev libpcap-dev git linux-headers
WORKDIR /app

ADD https://api.github.com/repos/ChuckMash/ESPythoNOW/commits/main_homeassistant /dev/null
RUN git clone --depth 1 --branch main_homeassistant https://github.com/ChuckMash/ESPythoNOW.git /tmp/repo && \
    cp /tmp/repo/ESPythoNOW.py /app/ && \
    cp /tmp/repo/requirements.txt /app/ && \
    cp /tmp/repo/addon-espythonow/run.sh /app/ && \
    rm -rf /tmp/repo

FROM python:3.11-alpine
RUN apk add --no-cache \
    libpcap \
    libpcap-dev \
    gcc \
    musl-dev \
    iw \
    iproute2 \
    wireless-tools \
    networkmanager-cli \
    bash

WORKDIR /app

COPY --from=build /app /app

RUN pip install --no-cache-dir -r requirements.txt && \
    rm /app/requirements.txt

RUN chmod +x /app/run.sh
CMD ["/app/run.sh"]
