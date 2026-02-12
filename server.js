// Deploy this code on Railway as server.js with Deno runtime

async function downloadFile(url, path) {
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  await Deno.writeFile(path, new Uint8Array(arrayBuffer));
}

async function runCommand(cmd) {
  const process = new Deno.Command(cmd[0], {
    args: cmd.slice(1),
    stdout: "piped",
    stderr: "piped",
  });
  
  const { success, stdout, stderr } = await process.output();
  
  if (!success) {
    const errorMsg = new TextDecoder().decode(stderr);
    throw new Error(`Command failed: ${errorMsg}`);
  }
  
  return new TextDecoder().decode(stdout);
}

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST only" }), { status: 400 });
    }

    const payload = await req.json();
    const { choir_id, contributions, layout_type = "grid", output_width = 1920, output_height = 1080 } = payload;

    console.log(`FFmpeg Worker: Processing ${contributions.length} videos for choir ${choir_id}`);

    if (!contributions || contributions.length < 2) {
      return new Response(JSON.stringify({ error: "Need at least 2 videos" }), { status: 400 });
    }

    // Calculate grid dimensions
    const gridSize = Math.ceil(Math.sqrt(contributions.length));
    const cellWidth = Math.floor(output_width / gridSize);
    const cellHeight = Math.floor(output_height / gridSize);
    const rows = Math.ceil(contributions.length / gridSize);

    // Create temp directory
    await Deno.mkdir("/tmp/choir_processing", { recursive: true });
    const tmpDir = `/tmp/choir_processing/${choir_id}`;
    await Deno.mkdir(tmpDir, { recursive: true });

    // Download all videos
    console.log("Downloading videos...");
    const downloadedPaths = [];
    for (let i = 0; i < contributions.length; i++) {
      const vid = contributions[i];
      const path = `${tmpDir}/video_${i}.mp4`;
      console.log(`Downloading video ${i} from ${vid.video_url}`);
      await downloadFile(vid.video_url, path);
      downloadedPaths.push(path);
    }

    // Build FFmpeg filter complex for grid layout
    let inputStr = "";
    
    for (let i = 0; i < contributions.length; i++) {
      inputStr += `-i ${downloadedPaths[i]} `;
    }

    // Create grid layout with ffmpeg
    let filterParts = [];
    for (let i = 0; i < contributions.length; i++) {
      filterParts.push(`[${i}]scale=${cellWidth}:${cellHeight}[v${i}]`);
    }

    // Build hstack/vstack pattern
    let hstacks = [];
    for (let r = 0; r < rows; r++) {
      let rowVideos = [];
      for (let c = 0; c < gridSize; c++) {
        const idx = r * gridSize + c;
        if (idx < contributions.length) {
          rowVideos.push(`[v${idx}]`);
        }
      }
      if (rowVideos.length > 0) {
        const hstackName = `hstack${r}`;
        filterParts.push(`${rowVideos.join("")}hstack=inputs=${rowVideos.length}[${hstackName}]`);
        hstacks.push(`[${hstackName}]`);
      }
    }

    if (hstacks.length > 1) {
      filterParts.push(`${hstacks.join("")}vstack=inputs=${hstacks.length}[v]`);
    } else {
      filterParts.push(`${hstacks[0]}copy[v]`);
    }

    const filterComplex = filterParts.join(";");
    const outputPath = `${tmpDir}/output.mp4`;
    
    console.log("Running FFmpeg with filter:", filterComplex);

    // Run FFmpeg
    const cmd = [
      "ffmpeg",
      "-y",
      ...inputStr.split(" ").filter(s => s),
      "-filter_complex",
      filterComplex,
      "-map",
      "[v]",
      "-c:v",
      "libx264",
      "-preset",
      "fast",
      "-b:v",
      "5000k",
      outputPath
    ];

    await runCommand(cmd);

    console.log("FFmpeg processing complete");

    // Read file and return as binary response
    const fileData = await Deno.readFile(outputPath);
    
    return new Response(fileData, {
      headers: {
        "Content-Type": "video/mp4",
        "Content-Disposition": `attachment; filename="choir-${choir_id}.mp4"`
      }
    });

  } catch (error) {
    console.error("FFmpeg worker error:", error);
    return new Response(JSON.stringify({ error: error.message }), { status: 500 });
  }
});
