FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 8501
CMD ["npm", "run", "dev", "--", "--port", "8501"]
