FROM python:3.12.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-app.txt /tmp/requirements-app.txt
COPY copilot/evaluation/requirements.txt /tmp/requirements-evaluation.txt
RUN pip install --no-cache-dir -r /tmp/requirements-app.txt -r /tmp/requirements-evaluation.txt
COPY copilot /app/copilot
COPY mapping /app/mapping
COPY contracts /app/contracts
COPY schemas /app/schemas
COPY vocab /app/vocab
RUN useradd --uid 10001 --create-home reports
USER 10001:10001
CMD ["python", "-m", "streamlit", "run", "copilot/metrics_dashboard/streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8503", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
