FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy application
COPY . .

# Build-time env vars (NEXT_PUBLIC_ vars are baked at build time)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build
RUN npm run build

# Expose port
EXPOSE 3000

# Run application (production mode)
CMD ["npm", "start"]
