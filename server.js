// FFmpeg Worker - Aligned to Architecture
// Deploy to Railway - Handles offset_detection AND choir_render jobs
// Uses FFmpeg silencedetect for audio sync

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

// Detect audio offset using FFmpeg silencedetect (SOLID ARCHITECTURE-ALIGNED)
// FFmpeg worker does ALL media processing - no external dependencies
async function detectAudioOffset(videoUrl, masterAudioUrl, tmpDir) {
  console.log('Starting FFmpeg silencedetect audio offset detection...');
  
  const videoPath = `${tmpDir}/contribution.mp4`;
  const masterPath = `${tmpDir}/master.wav`;
  const videoAudioPath = `${tmpDir}/contribution.wav`;
  
  // Download files
  await downloadFile(videoUrl, videoPath);
  await downloadFile(masterAudioUrl, masterPath);
  
  // Extract audio from contribution video
  await runCommand([
    'ffmpeg', '-i', videoPath,
    '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1',
    '-y', videoAudioPath
  ]);
  
  console.log('Detecting first significant audio moment in both tracks...');
  
  // Find when audio actually starts in each file (skip silence/countdown)
  const masterStart = await detectFirstAudio(masterPath);
  const contribStart = await detectFirstAudio(videoAudioPath);
  
  // Offset is the difference between when each track starts
  const offset = contribStart - masterStart;
  
  console.log(`Master starts at: ${masterStart.toFixed(2)}s`);
  console.log(`Contribution starts at: ${contribStart.toFixed(2)}s`);
  console.log(`Calculated offset: ${offset.toFixed(2)}s`);
  
  return {
    offset_seconds: Math.abs(offset),
    method: 'ffmpeg_silencedetect'
  };
}

async function detectFirstAudio(audioPath) {
  // Find first moment of significant audio (above -40dB threshold)
  try {
    await runCommand([
      'ffmpeg',
      '-i', audioPath,
      '-af', 'silencedetect=noise=-40dB:d=0.3',
      '-f', 'null', '-'
    ]);
    return 0;
  } catch (e) {
    // FFmpeg writes to stderr even on success
    const errorOutput = e.message || '';
    
    // Parse silencedetect output for first silence_end (= audio start)
    const match = errorOutput.match(/silence_end: ([\d.]+)/);
    if (match) {
      return parseFloat(match[1]);
    }
    
    // If no silence detected, audio starts at 0
    return 0;
  }
}

async function getAudioDuration(audioPath) {
  const output = await runCommand([
    'ffprobe',
    '-v', 'error',
    '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1',
    audioPath
  ]);
  
  return parseFloat(output.trim());
}

// Render choir grid video
async function renderChoirGrid(jobContract, tmpDir) {
  const { participants, layout, output, master_audio_url } = jobContract;
  
  console.log(`Rendering choir with ${participants.length} participants`);
  
  // Calculate grid dimensions
  const gridSize = Math.ceil(Math.sqrt(participants.length));
  const [outputWidth, outputHeight] = output.resolution.split('x').map(Number);
  const cellWidth = Math.floor(outputWidth / gridSize);
  const cellHeight = Math.floor(outputHeight / gridSize);
  const rows = Math.ceil(participants.length / gridSize);
  
  // Download all videos
  console.log('Downloading participant videos...');
  const downloadedPaths = [];
  for (let i = 0; i < participants.length; i++) {
    const participant = participants[i];
    const path = `${tmpDir}/video_${i}.mp4`;
    await downloadFile(participant.video_url, path);
    downloadedPaths.push({ path, offset: participant.offset_seconds });
  }
  
  // Build FFmpeg inputs with offset trimming
  let inputArgs = [];
  let filterParts = [];
  
  for (let i = 0; i < participants.length; i++) {
    const { path, offset } = downloadedPaths[i];
    inputArgs.push('-i', path);
    
    // Apply offset via setpts (delay video start)
    const delayFilter = offset > 0 ? `setpts=PTS+${offset}/TB` : 'setpts=PTS';
    filterParts.push(`[${i}:v]${delayFilter},scale=${cellWidth}:${cellHeight}[v${i}]`);
  }
  
  // Build grid layout
  let hstacks = [];
  for (let r = 0; r < rows; r++) {
    let rowVideos = [];
    for (let c = 0; c < gridSize; c++) {
      const idx = r * gridSize + c;
      if (idx < participants.length) {
        rowVideos.push(`[v${idx}]`);
      }
    }
    if (rowVideos.length > 0) {
      const hstackName = `hstack${r}`;
      filterParts.push(`${rowVideos.join('')}hstack=inputs=${rowVideos.length}[${hstackName}]`);
      hstacks.push(`[${hstackName}]`);
    }
  }
  
  if (hstacks.length > 1) {
    filterParts.push(`${hstacks.join('')}vstack=inputs=${hstacks.length}[vout]`);
  } else {
    filterParts.push(`${hstacks[0]}copy[vout]`);
  }
  
  const filterComplex = filterParts.join(';');
  const outputPath = `${tmpDir}/${output.filename}`;
  
  console.log('Running FFmpeg render...');
  
  // Run FFmpeg
  const ffmpegCmd = [
    'ffmpeg', '-y',
    ...inputArgs,
    '-filter_complex', filterComplex,
    '-map', '[vout]',
    '-c:v', 'libx264',
    '-preset', 'medium',
    '-b:v', '5000k',
    '-pix_fmt', 'yuv420p',
    outputPath
  ];
  
  await runCommand(ffmpegCmd);
  
  console.log('Render complete:', outputPath);
  
  return outputPath;
}

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST only" }), { status: 400 });
    }
    
    const jobContract = await req.json();
    const { job_id, job_type } = jobContract;
    
    console.log(`FFmpeg Worker: Processing ${job_type} job: ${job_id}`);
    
    const tmpDir = `/tmp/choir_${job_id}`;
    await Deno.mkdir(tmpDir, { recursive: true });
    
    // Route to appropriate handler
    if (job_type === 'offset_detection') {
      const { video_url, master_audio_url } = jobContract;
      
      const result = await detectAudioOffset(video_url, master_audio_url, tmpDir);
      
      return new Response(JSON.stringify({
        success: true,
        job_id,
        job_type,
        ...result
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
      
    } else if (job_type === 'choir_render') {
      const outputPath = await renderChoirGrid(jobContract, tmpDir);
      
      // Read and return video file
      const fileData = await Deno.readFile(outputPath);
      
      return new Response(fileData, {
        headers: {
          'Content-Type': 'video/mp4',
          'Content-Disposition': `attachment; filename="${jobContract.output.filename}"`
        }
      });
      
    } else {
      return new Response(JSON.stringify({ 
        error: `Unknown job_type: ${job_type}` 
      }), { status: 400 });
    }
    
  } catch (error) {
    console.error('FFmpeg worker error:', error);
    return new Response(JSON.stringify({ 
      error: error.message,
      stack: error.stack
    }), { status: 500 });
  }
});
