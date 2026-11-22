FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY migrations ./migrations
COPY testledger ./testledger
CMD ["python", "-m", "uvicorn", "testledger.main:app", "--host", "0.0.0.0", "--port", "8000"]
