FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && playwright install chromium
COPY backend/ ./backend/
COPY frontend/ ./frontend/
RUN mkdir -p workspace/memory
EXPOSE 8000
CMD ["python","-m","uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
