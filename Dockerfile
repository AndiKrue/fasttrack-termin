# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
# One image for the web app and the Telegram bot: Python, a JRE for the Zetaris JDBC driver,
# Node for the Meterless H-MEM bridge.
FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless nodejs npm \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY meterless/package.json meterless/
RUN cd meterless && npm install --no-audit --no-fund
COPY . .
ENV FT_HOST=0.0.0.0 FT_PORT=8765 PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "-m", "fasttrack.app"]
