FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update     && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config     && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/dev.txt
COPY . .
RUN useradd --create-home tis && chown -R tis /app
USER tis
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
