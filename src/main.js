const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');

function createWindow() {
    const win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    win.loadFile('index.html');
}

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// IPC handlers for video conversion and downloads
ipcMain.handle('convertVideo', async (event, { inputPath, outputPath }) => {
    return new Promise((resolve, reject) => {
        ffmpeg(inputPath)
            .output(outputPath)
            .on('end', () => resolve({ success: true }))
            .on('error', (err) => reject(err))
            .run();
    });
});

ipcMain.handle('downloadYouTube', async (event, { url, format }) => {
    try {
        const ytdl = require('ytdl-core');
        const fs = require('fs');
        const outputPath = path.join(app.getPath('downloads'), `youtube_${Date.now()}.${format}`);
        
        const video = ytdl(url, {
            quality: format === 'mp3' ? 'highestaudio' : 'highestvideo',
            format: format === 'mp3' ? 'mp3' : 'mp4'
        });

        await new Promise((resolve, reject) => {
            video.pipe(fs.createWriteStream(outputPath))
                .on('finish', resolve)
                .on('error', reject);
        });

        return { success: true, path: outputPath };
    } catch (error) {
        throw error;
    }
});

ipcMain.handle('downloadTikTok', async (event, { url }) => {
    try {
        const scraper = require('tiktok-scraper');
        const fs = require('fs');
        
        const videoInfo = await scraper.info(url);
        const videoUrl = videoInfo.videoUrl;
        const outputPath = path.join(app.getPath('downloads'), `tiktok_${Date.now()}.mp4`);

        const response = await fetch(videoUrl);
        const buffer = await response.buffer();
        
        await fs.promises.writeFile(outputPath, buffer);
        return { success: true, path: outputPath };
    } catch (error) {
        throw error;
    }
});
