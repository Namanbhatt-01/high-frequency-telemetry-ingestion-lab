FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY agent.py /app/agent.py

EXPOSE 8080

CMD ["python", "-u", "/app/agent.py"]
