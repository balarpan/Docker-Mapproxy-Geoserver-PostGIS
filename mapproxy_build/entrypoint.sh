#!/bin/sh

cd /mapproxy

# create config files if they do not exist yet
TMPLT_DIR="/mapproxy/config_template"
CONFIG_DIR="/mapproxy/config"
for file in "$TMPLT_DIR"/*; do
  filename=$(basename "$file")
  if [ ! -f "$CONFIG_DIR/$filename" ]; then
    echo "..Copying '$filename' to '$CONFIG_DIR'.."
    cp "$file" "$CONFIG_DIR/$filename"
    chmod 666 "$CONFIG_DIR/$filename"
  fi
done

#if [ ! -f /mapproxy/config/mapproxy.yaml ] && [ "$MULTIAPP_MAPPROXY" != "true" ]; then
#  echo "No mapproxy configuration found. Creating one from template."
#  mapproxy-util create -t base-config config
#  cp /mapproxy/config_template/mapproxy-example.yaml /mapproxy/config/mapproxy.yaml
#fi

#set done to 1 if a TERM or INT signal is sent
done=0
trap 'done=1' TERM INT

UWSGI_ADD_OPTIONS=""
if [ -n "$MAPPROXY_ALPINE" ]; then
  UWSGI_ADD_OPTIONS="--plugin python3"
fi

# run uswgi and nginx in parallel
uwsgi $UWSGI_ADD_OPTIONS --ini /mapproxy/config/uwsgi.conf &
echo "uswgi started"

# check once a second if done is set
while [ $done = 0 ]; do
  sleep 1 &
  wait
done
