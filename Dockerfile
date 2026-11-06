# NNE container status webpage – development image (nginx/TLS is a separate step before deployment)
# Build the nnedbtools wheel first: scripts/build_wheel.sh
FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt ./
COPY vendor/ vendor/
RUN pip install --no-cache-dir -r requirements.txt vendor/*.whl

COPY app.py ./
COPY pages/ pages/
COPY assets/ assets/

RUN useradd --system app
USER app
EXPOSE 8050
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "app:server"]
