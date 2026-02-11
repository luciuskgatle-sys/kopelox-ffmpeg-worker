import express from 'express';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegPath from '@ffmpeg-installer/ffmpeg';
import fetch from 'node-fetch';
import { createWriteStream, unlinkSync } from 'fs';
import { pipeline } from 'stream/promises';

ffmpeg.setFfmpegPath(ffmpegPath.path);

const app = express();
app.use(express.json({ limit: '50mb' }));

const PORT = process.env.PORT || 3000;

// Helper: Download file to disk
async function downloadFile(url, filepath) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to download ${url}`);
  await pipeline(response.body, createWriteStream(filepath));
}

// Helper: Upload to Cloudinary
async function uploadToCloudinary(filepath, filename) {
  const form = new FormData();
  form.append('file', require('fs').createReadStream(filepath));
  form.append('upload_preset', process.env.CLOUDINARY_UPLOAD_PRESET || 'choir_videos');
  form.append('folder', 'choir-sync');
  form.append('public_id', filename.replace(/\.[^/.]+$/, ''));

  const response = await fetch(
    `https://api.cloudinary.com/v1_1/${process.env.CLOUDINARY_CLOUD_NAME}/video/upload`,
    { method: 'POST', body: form }
  );

  if (!response.ok) throw new Error('Cloudinary upload failed');
  const data = await response.json();
  return data.secure_url;
}

app.post('/', async (req, res) => {
  try {
    const { choir_id, contributions, layout_type = 'grid', output_width = 1920, output_height = 1080 } = req.body;

    if (!contributions || contributions.length < 2) {
      return res.status(400).json({ error: 'Need at least 2 videos' });
    }

    console.log(`Processing ${contributions.length} videos for choir ${choir_id}`);

    // Step 1: Download all videos
    const videoFiles = [];
    const tempDir = `/tmp/choir-${choir_id}`;
    require('fs').mkdirSync(tempDir, { recursive: true });

    for (let i = 0; i < contributions.length; i++) {
      const filename = `${tempDir}/video_${i}.mp4`;
      console.log(`Downloading video ${i + 1}/${contributions.length}...`);
      await downloadFile(contributions[i].video_url, filename);
      videoFiles.push({
        path: filename,
        offset: contributions[i].offset_seconds || 0
      });
    }

    // Step 2: Create grid layout with FFmpeg
    console.log('Creating grid composition...');
    const cols = Math.ceil(Math.sqrt(videoFiles.length));
    const rows = Math.ceil(videoFiles.length / cols);
    const cellWidth = Math.floor(output_width / cols);
    const cellHeight = Math.floor(output_height / rows);

    // Build FFmpeg filter for grid
    let filterComplex = '';
    let filterInputs = '';
    for (let i = 0; i < videoFiles.length; i++) {
      filterInputs += `[${i}:v]scale=${cellWidth}:${cellHeight}[v${i}];`;
    }

    let gridString = '';
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const idx = row * cols + col;
        if (idx < videoFiles.length) {
          gridString += `[v${idx}]`;
        }
      }
      gridString += `hstack=inputs=${cols}[row${row}];`;
    }

    // Combine rows vertically
    let rowInputs = '';
    for (let row = 0; row < rows; row++) {
      rowInputs += `[row${row}]`;
    }
    filterComplex = filterInputs + gridString + rowInputs + `vstack=inputs=${rows}`;

    const outputPath = `${tempDir}/output.mp4`;

    // Build FFmpeg command
    let ffmpegCmd = ffmpeg();
    videoFiles.forEach((v, i) => {
      ffmpegCmd = ffmpegCmd.input(v.path);
    });

    // Step 3: Render with FFmpeg
    await new Promise((resolve, reject) => {
      ffmpegCmd
        .complexFilter(filterComplex)
        .output(outputPath)
        .on('start', (cmd) => console.log('FFmpeg started:', cmd))
        .on('progress', (progress) => console.log(`Progress: ${progress.percent}%`))
        .on('end', () => {
          console.log('FFmpeg completed');
          resolve();
        })
        .on('error', (err) => {
          console.error('FFmpeg error:', err);
          reject(err);
        })
        .run();
    });

    // Step 4: Upload to Cloudinary
    console.log('Uploading to Cloudinary...');
    const videoUrl = await uploadToCloudinary(outputPath, `choir-${choir_id}`);

    // Cleanup
    videoFiles.forEach(v => unlinkSync(v.path));
    unlinkSync(outputPath);
    require('fs').rmdirSync(tempDir);

    res.json({
      success: true,
      output_video_url: videoUrl,
      videos_combined: videoFiles.length,
      processing_time: `${Math.round((Date.now() - req.startTime) / 1000)}s`
    });

  } catch (error) {
    console.error('Processing error:', error);
    res.status(500).json({ error: error.message });
  }
});

app.listen(PORT, () => console.log(`FFmpeg worker on port ${PORT}`));
