ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    chromium-chromedriver \
    xvfb \
    x11vnc \
    novnc \
    supervisor \
    ttf-freefont \
    font-noto

# Create virtual environment and install Python packages
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir selenium requests

# Set up directories
RUN mkdir -p /data/chrome-profile /app /var/log/supervisor

# Copy application files
COPY edp_monitor.py /app/
COPY run.sh /app/
COPY supervisord.conf /etc/supervisord.conf
RUN chmod +x /app/run.sh

# Expose noVNC port
EXPOSE 6080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
