# Build stage only (networked). Runtime containers are offline (THREAT-MODEL.md).
FROM python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ARG LOCK=lock.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libgomp1 && rm -rf /var/lib/apt/lists/*
COPY ${LOCK} /opt/lock.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -q --upgrade "pip==25.3" "setuptools==80.9.0" "wheel==0.45.1" "Cython<3.2" \
 && /opt/venv/bin/pip install -q --no-build-isolation --require-hashes --no-deps -r /opt/lock.txt \
 && /opt/venv/bin/pip freeze > /opt/packages.txt
ENV PATH=/opt/venv/bin:$PATH NLTK_DATA=/usr/share/nltk_data
USER 10001:10001
