FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ADD --checksum=sha256:d0e0bee93732408c91fbad05cb0c2812e9ad37e94d12799c5503a9fe7afa2b82 https://raw.githubusercontent.com/swagger-api/swagger-ui/v5.35.1/dist/swagger-ui-bundle.js /app/swagger-ui/swagger-ui-bundle.js
ADD --checksum=sha256:5ed08757e53da3e026d6cbecc61fe5d43585c9560b302d534ad56692519a273d https://raw.githubusercontent.com/swagger-api/swagger-ui/v5.35.1/dist/swagger-ui.css /app/swagger-ui/swagger-ui.css
ADD --checksum=sha256:3ed612f41e050ca5e7000cad6f1cbe7e7da39f65fca99c02e99e6591056e5837 https://raw.githubusercontent.com/swagger-api/swagger-ui/v5.35.1/dist/favicon-32x32.png /app/swagger-ui/favicon-32x32.png
ADD --checksum=sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 https://raw.githubusercontent.com/swagger-api/swagger-ui/v5.35.1/LICENSE /app/swagger-ui/LICENSE
COPY alembic.ini ./
COPY migrations ./migrations
COPY testledger ./testledger
CMD ["python", "-m", "uvicorn", "testledger.main:app", "--host", "0.0.0.0", "--port", "8000"]
