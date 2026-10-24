FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py code_reader.py auth0_verifier.py ./
USER 65532:65532
EXPOSE 8787
CMD ["python", "server.py"]
