#!/bin/bash

CONFIG_FILE="mosquitto.conf"
CONTAINER_NAME="mqtt-broker"

# Create config file
cat > $CONFIG_FILE << EOL
listener 1883
allow_anonymous true
EOL

# Stop and remove existing container
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

# Start new container
docker run -d \
  --name $CONTAINER_NAME \
  -p 1883:1883 \
  -v "$(pwd)/$CONFIG_FILE:/mosquitto/config/$CONFIG_FILE" \
  eclipse-mosquitto:latest

echo "MQTT broker started. Check logs with: docker logs $CONTAINER_NAME"