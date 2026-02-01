#!/bin/sh
echo "Starting EDP Voucher Monitor..."
echo "noVNC available at port 6080"
exec /usr/bin/supervisord -c /etc/supervisord.conf
