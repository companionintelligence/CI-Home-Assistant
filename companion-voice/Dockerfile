# Home Assistant app: the published Voice Bridge image, started with options
# read from /data/options.json (see run.py). Built on the Supervisor device.
# Pinned by tag and digest. ci-ha-voice-bridge has no 0.1.0 tag in GHCR.
FROM ghcr.io/companionintelligence/ci-ha-voice-bridge:1.0.0-rc.1@sha256:8e6732f2e1249a915523bcaae3e087fb2a6a50ebd78144cc810e4c4e937ca2c1

USER root
COPY run.py /app/run.py
RUN chown bridge:bridge /app/run.py
USER bridge

EXPOSE 10700

CMD ["python", "run.py"]
