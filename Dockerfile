FROM python:3.11-slim
LABEL org.opencontainers.image.authors="Felix Kröhnert"
LABEL org.opencontainers.image.title="UncivMailer"
LABEL org.opencontainers.image.base.name="UncivMailer"
LABEL org.opencontainers.image.version="1.0"
LABEL org.opencontainers.image.description="Mailing Turn-notifications containerized."

WORKDIR /app
RUN apt update && apt install -y inotify-tools
COPY watcher.py /app/watcher.py

ENTRYPOINT ["python3", "watcher.py"]

