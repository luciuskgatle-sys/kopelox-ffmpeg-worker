// Replace detectAudioOffset function with this - uses ACTUAL audio energy, not silence
async function detectAudioOffset(videoUrl, masterAudioUrl, tmpDir) {
  console.log('Starting audio energy offset detection...');
  
  const videoPath = `${tmpDir}/contribution.mp4`;
  const masterPath = `${tmpDir}/master.wav`;
  const videoAudioPath = `${tmpDir}/contribution.wav`;
  
  await downloadFile(videoUrl, videoPath);
  await downloadFile(masterAudioUrl, masterPath);
  
  await runCommand([
    'ffmpeg', '-i', videoPath,
    '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1',
    '-y', videoAudioPath
  ]);
  
  console.log('Detecting first LOUD audio moment (singing start)...');
  
  // Use astats to find when RMS level crosses threshold (actual singing)
  const masterStart = await detectLoudAudioStart(masterPath);
  const contribStart = await detectLoudAudioStart(videoAudioPath);
  
  const offset = contribStart - masterStart;
  
  console.log(`Master loud audio at: ${masterStart.toFixed(2)}s`);
  console.log(`Contribution loud audio at: ${contribStart.toFixed(2)}s`);
  console.log(`Offset: ${offset.toFixed(2)}s`);
  
  return {
    offset_seconds: Math.abs(offset),
    method: 'ffmpeg_audio_energy'
  };
}

async function detectLoudAudioStart(audioPath) {
  try {
    // Use astats to measure RMS over time, find first moment above -20dB
    const output = await runCommand([
      'ffmpeg', '-i', audioPath,
      '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level',
      '-f', 'null', '-'
    ]).catch(e => e.message);
    
    // Parse timestamps where RMS crosses threshold
    const lines = output.split('\n');
    for (const line of lines) {
      if (line.includes('lavfi.astats.Overall.RMS_level') && line.includes('pts_time')) {
        const timeMatch = line.match(/pts_time:([\d.]+)/);
        const rmsMatch = line.match(/RMS_level=(-?[\d.]+)/);
        
        if (timeMatch && rmsMatch) {
          const time = parseFloat(timeMatch[1]);
          const rms = parseFloat(rmsMatch[1]);
          
          // If RMS > -20dB, this is loud audio (singing, not countdown)
          if (rms > -20) {
            console.log(`Found loud audio at ${time}s with RMS ${rms}dB`);
            return time;
          }
        }
      }
    }
    
    return 0;
  } catch (e) {
    console.error('Audio energy detection error:', e);
    return 0;
  }
}
