FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY --chown=appuser:appuser server.py ./
COPY --chown=appuser:appuser fashiongen ./fashiongen
COPY --chown=appuser:appuser static ./static
USER appuser
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8888') + '/api/health', timeout=4)"
CMD ["python", "server.py"]
