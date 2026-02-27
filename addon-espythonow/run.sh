#!/usr/bin/env bash
set -euo pipefail

if [ -f /data/options.json ]; then
    echo "[ESPythoNOW] Home Assistant mode"    
    exec python3 -u /app/ESPythoNOW.py --config=/data/options.json
    
else
    echo "[ESPythoNOW] Docker mode"
    exec python3 -u /app/ESPythoNOW.py \
      --interface="${INTERFACE}" \
      --channel="${CHANNEL}" \
      --set_interface="${SET_INTERFACE}" \
      --mtu="${MTU}" \
      --rate="${RATE}" \
      --send_raw="${SEND_RAW}" \
      --no_wait="${NO_WAIT}" \
      --retry_limit="${RETRY_LIMIT}" \
      --repeat="${REPEAT}" \
      --accept_broadcast="${ACCEPT_BROADCAST}" \
      --accept_all="${ACCEPT_ALL}" \
      --accept_ack="${ACCEPT_ACK}" \
      --block_on_send="${BLOCK_ON_SEND}" \
      ${PRIMARY_KEY:+--primary_key="$PRIMARY_KEY"} \
      ${LOCAL_KEY:+--local_key="$LOCAL_KEY"} \
      --mqtt_host="${MQTT_HOST}" \
      --mqtt_port="${MQTT_PORT}" \
      --mqtt_username="${MQTT_USERNAME}" \
      --mqtt_password="${MQTT_PASSWORD}" \
      --mqtt_keepalive="${MQTT_KEEPALIVE}" \
      --mqtt_raw="${MQTT_RAW}" \
      --mqtt_hex="${MQTT_HEX}" \
      --mqtt_json="${MQTT_JSON}" \
      --mqtt_ack="${MQTT_ACK}"
fi
