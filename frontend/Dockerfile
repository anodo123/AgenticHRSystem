# Frontend Dockerfile

FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* yarn.lock* ./

# Install dependencies
RUN npm ci || npm install

# Copy source code
COPY . .

# Build application
ARG VITE_API_URL=http://localhost:8000/api/v1
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Install serve to run SPA
RUN npm install -g serve

# Copy built app from builder
COPY --from=builder /app/dist ./dist

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

# Serve application
CMD ["serve", "-s", "dist", "-l", "3000"]
