FROM python:3.12-slim AS backend

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY adapters/ adapters/
COPY agents/ agents/
COPY cli/ cli/
COPY models/ models/
COPY orchestrator/ orchestrator/
COPY server/ server/
COPY config.py .

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

# -------------------------------------------------------------------

FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY app/ app/
COPY components/ components/
COPY lib/ lib/
COPY store/ store/
COPY types/ types/
COPY next.config.js tsconfig.json tailwind.config.js postcss.config.js ./

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# -------------------------------------------------------------------

FROM node:20-alpine AS frontend

WORKDIR /app

COPY --from=frontend-build /app/.next/standalone ./
COPY --from=frontend-build /app/.next/static ./.next/static

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
