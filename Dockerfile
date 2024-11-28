FROM python:3.13-slim

EXPOSE 8000

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "src.stac_auth_proxy.main:app", "--host", "0.0.0.0", "--port", "8000"]
