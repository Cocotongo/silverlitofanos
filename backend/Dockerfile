FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# version.json lo escribe tools/actualizar_servidor.sh; el patrón evita fallar si no existe.
COPY version.jso[n] ./
ENV SILVER_DATOS=/datos
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
