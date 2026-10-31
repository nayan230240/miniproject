# Node image for the Configo UI (Vite dev server).
FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better Docker layer caching.
COPY package.json package-lock.json* ./
RUN npm install

# Copy the React source.
COPY . .

# Vite default port.
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
