#!/bin/bash
echo "Starting EDP Voucher Monitor..."

# Start Xvfb
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x720x24 &
sleep 2

# Set display
export DISPLAY=:99

# Start x11vnc
echo "Starting x11vnc..."
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 &
sleep 2

# Start noVNC
echo "Starting noVNC on port 6080..."
/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080 &
sleep 2

echo "=============================================="
echo "  noVNC available at http://<your-ip>:6080"
echo "=============================================="

# Start monitor
echo "Starting EDP Monitor..."
exec python3 /app/edp_monitor.py
