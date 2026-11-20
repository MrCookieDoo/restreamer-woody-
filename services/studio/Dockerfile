FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY . ./
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-gi python3-gst-1.0 ca-certificates \
    gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gir1.2-gst-rtsp-server-1.0 \
    gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    fonts-dejavu-core && rm -rf /var/lib/apt/lists/* && \
    python3 -m venv --system-site-packages /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements-dev.txt && \
    useradd --uid 10001 --create-home studio && mkdir /data && chown studio /data && chmod -R a+rX /app
ENV PATH=/opt/venv/bin:$PATH
USER studio
EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz')"
CMD ["uvicorn", "woody.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
