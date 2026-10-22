# Callie as a hosted service:  docker build -t callie .   (see docs/HOSTING.md)
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CALLIE_MODE=hosted CALLIE_HOME=/data
WORKDIR /app
COPY requirements-base.txt .
RUN pip install -r requirements-base.txt
COPY VERSION ./
COPY server ./server
COPY pipeline ./pipeline
COPY audio ./audio
COPY conversation ./conversation
COPY client ./client
RUN useradd --create-home callie && mkdir -p /data && chown callie /data
USER callie
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*", "--no-server-header"]
