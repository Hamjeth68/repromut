# Build stage only (networked). Installs the locked environment (uv.lock, --frozen) and the
# project package non-editably. Runtime containers are offline and mount the work copy at /work.
FROM python@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
ARG SKLEARN_OVERRIDE=""
COPY src_snapshot /build
WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN pip install -q "uv==0.13.7" && uv --version > /opt/uv_version.txt \
 && uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python3.14 \
 && if [ -n "$SKLEARN_OVERRIDE" ]; then uv pip install --python /opt/venv/bin/python --no-deps "scikit-learn==$SKLEARN_OVERRIDE"; fi \
 && uv pip freeze --python /opt/venv/bin/python > /opt/packages.txt \
 && cd / && rm -rf /build /root/.cache
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /
USER 10001:10001
