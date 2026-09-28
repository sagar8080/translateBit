FROM node:22-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --locked --no-dev
COPY backend ./backend
COPY --from=frontend /app/dist ./static
ENV STATIC_DIR=/app/static
ENV ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["backend/.venv/bin/uvicorn", "backend.translatebit.main:app", "--host", "0.0.0.0", "--port", "8000"]
