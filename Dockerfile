FROM python:3.11-alpine AS build
RUN apk add --no-cache gcc musl-dev libpcap-dev git linux-headers
WORKDIR /app

ADD https://api.github.com/repos/ChuckMash/ESPythoNOW/commits/test /dev/null
RUN git clone --depth 1 --branch test https://github.com/ChuckMash/ESPythoNOW.git /tmp/repo && \
    cp /tmp/repo/ESPythoNOW.py /tmp/repo/requirements.txt /app/ && \
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
     networkmanager networkmanager-cli net-tools \
    bash

WORKDIR /app

COPY --from=build /app /app

RUN pip install --no-cache-dir -r requirements.txt && \
    rm /app/requirements.txt

COPY run.sh /app/run.sh

RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
