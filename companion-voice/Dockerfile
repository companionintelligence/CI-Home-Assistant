# Home Assistant app: the published Voice Bridge image, started with options
# read from /data/options.json (see run.py). Built on the Supervisor device.
FROM ghcr.io/companionintelligence/ci-ha-voice-bridge:0.1.0

USER root
COPY run.py /app/run.py
RUN chown bridge:bridge /app/run.py
USER bridge

EXPOSE 10700

CMD ["python", "run.py"]
