FROM python:3.13-slim

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utility
COPY ../../shared /shared

COPY . .

ENV PYTHONPATH=/service:/

RUN PYTHONPATH=/service:/  python scripts/migrate.py

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
