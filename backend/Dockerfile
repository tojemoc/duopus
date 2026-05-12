FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
  && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system app && adduser --system --ingroup app app
COPY . .
RUN chmod +x /app/entrypoint.sh && chown -R app:app /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
USER app
CMD ["/app/entrypoint.sh"]
