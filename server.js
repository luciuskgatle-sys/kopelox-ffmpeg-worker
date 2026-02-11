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

app.post('/', async (req, res) => {
  try {
    const { choir_id, master_video_url, contributions, layout_type } = req.body;
    
    // Download and process videos with FFmpeg
    // Grid layout composition logic here
    
    res.json({ 
      success: true, 
      output_video_url: 'processed_video_url',
      processing_time: '30s'
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(PORT, () => console.log(`FFmpeg worker on port ${PORT}`));
