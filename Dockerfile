FROM denoland/deno:latest

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

CMD ["deno", "run", "--allow-all", "server.js"]
