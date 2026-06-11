FROM oven/bun:1.3.5 AS tour-build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY scripts ./scripts
COPY tour ./tour
RUN bun run build:tour

FROM python:3.11-slim

WORKDIR /app

# Install graphviz for ER diagram visualization
RUN apt-get update && apt-get install -y graphviz && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=tour-build /app/static/tour ./static/tour

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
