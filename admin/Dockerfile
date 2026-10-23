FROM oven/bun:1.4.4 AS tour-build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY scripts ./scripts
COPY tour ./tour
RUN bun run build:tour

FROM python:3.11-slim

WORKDIR /app

# Install graphviz for ER diagram visualization
RUN apt-get update && apt-get install -y --no-install-recommends graphviz ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Bootstrap from the SHA-256 pinned wheel recommended by Python security.
RUN python -m pip install --no-cache-dir --no-deps "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70" \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=tour-build /app/static/tour ./static/tour

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
