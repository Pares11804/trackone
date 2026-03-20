# TrackOne client agent — build from repository root:
#   docker build -f trackoneagent/Dockerfile -t trackone-agent:latest .
#
# Run (set URL + token):
#   docker run -d --name trackone-agent --restart unless-stopped \
#     -e TRACKONE_CONTROL_URL=http://192.168.1.50:8000 \
#     -e TRACKONE_API_TOKEN=your_token_here \
#     trackone-agent:latest

FROM python:3.12-slim-bookworm

WORKDIR /app

COPY trackoneagent/requirements.txt /app/trackoneagent/requirements.txt
RUN pip install --no-cache-dir -r /app/trackoneagent/requirements.txt

COPY trackoneagent /app/trackoneagent
COPY monitoring_scripts /app/monitoring_scripts

ENV PYTHONUNBUFFERED=1

# /app is bundle root (parent of trackoneagent/ + monitoring_scripts/)
CMD ["python", "-m", "trackoneagent"]
