# AEGIS control plane image
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY aegis /app/aegis
COPY aegis/pyproject.toml /app/aegis/pyproject.toml
COPY aegis/requirements.txt /app/aegis/requirements.txt
RUN pip install --no-cache-dir -r /app/aegis/requirements.txt
RUN pip install --no-cache-dir --no-deps /app/aegis
# local sibling engines (evalforge/run-replay/agent-sentinel stubs live at repo root)
COPY evalforge /app/evalforge
COPY run-replay /app/run-replay
COPY agent-sentinel /app/agent-sentinel
RUN pip install --no-cache-dir --no-deps /app/evalforge /app/run-replay /app/agent-sentinel
EXPOSE 8000
CMD ["uvicorn", "aegis.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
