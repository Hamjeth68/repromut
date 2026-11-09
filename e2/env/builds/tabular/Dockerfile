# Build stage only (networked). Runtime containers are offline (see THREAT-MODEL.md).
FROM python@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d
ARG LOCK=lock.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libgomp1 && rm -rf /var/lib/apt/lists/*
COPY ${LOCK} /opt/lock.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -q --upgrade "pip==25.3" "setuptools==80.9.0" \
 && /opt/venv/bin/pip install -q --no-build-isolation --require-hashes --no-deps -r /opt/lock.txt \
 && /opt/venv/bin/pip freeze > /opt/packages.txt
ENV PATH=/opt/venv/bin:$PATH
USER 10001:10001
