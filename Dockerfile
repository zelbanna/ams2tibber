# docker build -t zelbanna/ams2tibber:latest -t zelbanna/ams2tibber:1.x.y .
# docker push -a zelbanna/ams2tibber

#
FROM python:3.12.6-slim-bookworm AS build-ams2tibber-image
RUN apt-get update && apt-get -y install python3-paho-mqtt
COPY . /app
COPY ./config /etc/ams2tibber

WORKDIR /app
LABEL org.opencontainers.image.authors="Zacharias El Banna  <zacharias@elbanna.se>"

# Command to run the Python script
ENV PATH=/root/.local/bin:$PATH
ENTRYPOINT ["/app/ams2tibber.py"]
# CMD ["-c","/etc/ams2tibber/ams2tibber.json"]
