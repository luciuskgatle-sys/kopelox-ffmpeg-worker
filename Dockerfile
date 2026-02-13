FROM denoland/deno:latest

# Install FFmpeg AND sox
RUN apt-get update && apt-get install -y ffmpeg sox && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

CMD ["deno", "run", "--allow-all", "server.js"]
