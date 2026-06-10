const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');
const ffmpeg = require('fluent-ffmpeg');
const ytdl = require('ytdl-core');
let tiktokScraper = null;

const ensureDirSync = (dirPath) => {
    try {
        fs.mkdirSync(dirPath, { recursive: true });
    } catch (_err) {
        // ignore
    }
};

let ffmpegBinary = null;
try {
    // Optional dependency, only set if available
    ffmpegBinary = require('ffmpeg-static');
    if (ffmpegBinary) {
        ffmpeg.setFfmpegPath(ffmpegBinary);
    }
} catch (error) {
    ffmpegBinary = null;
}

const MAX_QUEUE_HISTORY = 100;
const MAX_LOG_BUFFER = 500;

// Server configuration
const SERVER_PORT = 8000;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;

try {
    const userDataPath = app.getPath('userData');
    const cachePath = path.join(userDataPath, 'chromium-cache');
    ensureDirSync(cachePath);
    app.commandLine.appendSwitch('disk-cache-dir', cachePath);
    app.commandLine.appendSwitch('user-data-dir', userDataPath);
} catch (_err) {
    // ignore
}

let mainWindow;
let pythonProcess = null;
let pythonStatus = { status: 'unknown' };
let jobQueue = [];
let logBuffer = [];
let logFilePath = null;
let logsInitialized = false;
let ipcHandlersRegistered = false;

const pendingRendererEvents = [];

const enqueueRendererEvent = (channel, payload) => {
    pendingRendererEvents.push({ channel, payload });
};

const sendToRenderer = (channel, payload) => {
    if (mainWindow && !mainWindow.isDestroyed() && mainWindow.webContents) {
        mainWindow.webContents.send(channel, payload);
    } else {
        enqueueRendererEvent(channel, payload);
    }
};

const flushPendingRendererEvents = () => {
    if (!mainWindow || mainWindow.isDestroyed() || !mainWindow.webContents) {
        return;
    }
    while (pendingRendererEvents.length > 0) {
        const event = pendingRendererEvents.shift();
        mainWindow.webContents.send(event.channel, event.payload);
    }
    if (pythonStatus && pythonStatus.status && pythonStatus.status !== 'unknown') {
        sendToRenderer('python-status', pythonStatus);
        if (pythonStatus.status === 'ready') {
            sendToRenderer('backend-ready', pythonStatus);
        }
        if (pythonStatus.status === 'error') {
            sendToRenderer('backend-error', pythonStatus);
        }
    }
    sendToRenderer('queue-updated', [...jobQueue]);
};

const ensureLogsInitialized = () => {
    if (logsInitialized) {
        return;
    }
    const logsDir = path.join(app.getPath('userData'), 'logs');
    fs.mkdirSync(logsDir, { recursive: true });
    logFilePath = path.join(logsDir, 'renderer.log');
    logsInitialized = true;
};

const appendLog = (entry) => {
    ensureLogsInitialized();
    const logEntry = {
        ...entry,
        timestamp: entry.timestamp || Date.now()
    };
    logBuffer.push(logEntry);
    if (logBuffer.length > MAX_LOG_BUFFER) {
        logBuffer = logBuffer.slice(-MAX_LOG_BUFFER);
    }

    if (logsInitialized && logFilePath) {
        const formatted = `[${new Date(logEntry.timestamp).toISOString()}] [${logEntry.level?.toUpperCase() || 'INFO'}] ${logEntry.message || ''} ${logEntry.meta ? JSON.stringify(logEntry.meta) : ''}${os.EOL}`;
        fs.appendFile(logFilePath, formatted, (err) => {
            if (err) {
                console.error('Failed to write log file:', err);
            }
        });
    }
};

const publishPythonStatus = (status, details = {}) => {
    pythonStatus = {
        status,
        ...details,
        timestamp: Date.now()
    };
    sendToRenderer('python-status', pythonStatus);
    if (status === 'ready') {
        sendToRenderer('backend-ready', pythonStatus);
    } else if (status === 'error') {
        sendToRenderer('backend-error', pythonStatus);
    }
    appendLog({
        level: status === 'error' ? 'error' : 'info',
        message: `Python backend status changed: ${status}`,
        meta: details
    });
};

const createJob = (type, metadata = {}) => {
    const job = {
        id: typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${type}-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
        type,
        status: 'pending',
        metadata,
        progress: 0,
        createdAt: Date.now(),
        updatedAt: Date.now()
    };
    jobQueue.push(job);
    if (jobQueue.length > MAX_QUEUE_HISTORY) {
        jobQueue = jobQueue.slice(-MAX_QUEUE_HISTORY);
    }
    sendToRenderer('queue-updated', [...jobQueue]);
    return job;
};

const updateJob = (jobId, updates = {}) => {
    const job = jobQueue.find((item) => item.id === jobId);
    if (!job) {
        return null;
    }
    Object.assign(job, updates, { updatedAt: Date.now() });
    sendToRenderer('queue-updated', [...jobQueue]);
    return job;
};

const completeJob = (jobId, success, result = {}) => {
    const status = success ? 'completed' : 'failed';
    const job = updateJob(jobId, {
        status,
        progress: success ? 100 : result.progress ?? 0,
        result,
        completedAt: Date.now()
    });
    if (job) {
        appendLog({
            level: success ? 'info' : 'error',
            message: `Job ${job.type} ${success ? 'completed' : 'failed'}`,
            meta: { jobId, result }
        });
    }
};

const clearCompletedJobs = () => {
    const before = jobQueue.length;
    jobQueue = jobQueue.filter((job) => job.status !== 'completed');
    const removed = before - jobQueue.length;
    sendToRenderer('queue-updated', [...jobQueue]);
    return removed;
};

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const pingServer = async () => {
    try {
        const response = await fetch(`${SERVER_URL}/`, {
            method: 'GET',
            cache: 'no-store'
        });
        return response.ok;
    } catch (error) {
        return false;
    }
};

const waitForServer = async (timeoutMs = 20000, intervalMs = 500) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        // eslint-disable-next-line no-await-in-loop
        if (await pingServer()) {
            return true;
        }
        // eslint-disable-next-line no-await-in-loop
        await delay(intervalMs);
    }
    return false;
};

const ensureTikTokScraper = () => {
    if (tiktokScraper) {
        return true;
    }
    try {
        // eslint-disable-next-line global-require
        tiktokScraper = require('tiktok-scraper');
        return true;
    } catch (error) {
        appendLog({
            level: 'warn',
            message: 'tiktok-scraper module not available',
            meta: { error: error.message }
        });
        return false;
    }
};

const emitQueueUpdate = () => {
    sendToRenderer('queue-updated', [...jobQueue]);
};

const progressPayload = (jobId, percent, extra = {}) => ({
    jobId,
    percent: Math.max(0, Math.min(percent, 100)),
    ...extra
});

const handleDownloadYoutube = async (_event, { url, format }) => {
    const normalizedFormat = (format || 'mp4').toLowerCase();
    const job = createJob('youtube-download', { url, format: normalizedFormat });
    appendLog({
        level: 'info',
        message: 'Starting YouTube download',
        meta: { jobId: job.id, url, format: normalizedFormat }
    });

    const resolveOutputPath = (title) => {
        const safeTitle = (title || 'youtube_video').replace(/[^\w\s-]/g, '').trim();
        return path.join(app.getPath('downloads'), `${safeTitle || 'youtube_video'}_${Date.now()}.${normalizedFormat}`);
    };

    return new Promise(async (resolve, reject) => {
        try {
            updateJob(job.id, { status: 'running' });

            // Extract video ID
            let videoId;
            try {
                const urlObj = new URL(url);
                if (urlObj.hostname.includes('youtu.be')) {
                    videoId = urlObj.pathname.split('/').filter(Boolean).pop();
                } else {
                    videoId = urlObj.searchParams.get('v');
                }
            } catch (parseError) {
                const match = url.match(/(?:v=|youtu\.be\/)([^&\n?#]+)/);
                videoId = match ? match[1] : null;
            }

            if (!videoId) {
                throw new Error('Invalid YouTube URL');
            }

            const info = await ytdl.getInfo(videoId);
            const outputPath = resolveOutputPath(info.videoDetails.title);

            const downloadOptions = {
                quality: normalizedFormat === 'mp3' ? 'highestaudio' : 'highest',
                filter: normalizedFormat === 'mp3' ? 'audioonly' : 'videoandaudio',
                dlChunkSize: 0,
                highWaterMark: 1024 * 1024 * 10,
                requestOptions: {
                    maxRetries: 3,
                    maxReconnects: 3
                }
            };

            const videoStream = ytdl.downloadFromInfo(info, downloadOptions);
            let lastPercent = 0;

            const downloadTimeout = setTimeout(() => {
                if (lastPercent === 0) {
                    videoStream.destroy(new Error('Download timed out. Check your internet connection.'));
                }
            }, 30000);

            videoStream.on('progress', (_chunkLength, downloaded, total) => {
                const percent = total ? (downloaded / total) * 100 : 0;
                lastPercent = percent;
                const elapsed = (Date.now() - job.createdAt) / 1000;
                const speed = elapsed > 0 ? downloaded / elapsed : 0;
                const remainingBytes = total ? total - downloaded : 0;
                const remaining = speed > 0 ? remainingBytes / speed : 0;

                const payload = progressPayload(job.id, percent, {
                    transferred: downloaded,
                    total,
                    remaining: Math.max(0, Math.round(remaining)),
                    speed
                });

                updateJob(job.id, { status: 'running', progress: payload.percent });
                sendToRenderer('download-progress', payload);
                sendToRenderer('youtube-download-progress', payload);
            });

            const completeSuccess = (resultMeta) => {
                clearTimeout(downloadTimeout);
                completeJob(job.id, true, resultMeta);
                appendLog({
                    level: 'info',
                    message: 'YouTube download completed',
                    meta: { jobId: job.id, ...resultMeta }
                });
                resolve({ success: true, ...resultMeta, jobId: job.id });
            };

            const handleError = (error) => {
                clearTimeout(downloadTimeout);
                const errorMessage = error?.message || 'Failed to download video';
                sendToRenderer('download-error', { jobId: job.id, message: errorMessage });
                appendLog({
                    level: 'error',
                    message: 'YouTube download failed',
                    meta: { jobId: job.id, error: errorMessage }
                });
                completeJob(job.id, false, { error: errorMessage });
                reject(new Error(errorMessage));
            };

            if (normalizedFormat === 'mp3') {
                const audioOnly = ytdl(url, {
                    quality: 'highestaudio',
                    filter: 'audioonly',
                    dlChunkSize: 0,
                    highWaterMark: 1024 * 1024 * 10
                });

                ffmpeg(audioOnly)
                    .audioBitrate(192)
                    .toFormat('mp3')
                    .on('error', handleError)
                    .on('end', () => completeSuccess({ outputPath }))
                    .pipe(fs.createWriteStream(outputPath));
            } else {
                const videoOnly = ytdl(url, {
                    quality: 'highest',
                    filter: 'videoonly',
                    dlChunkSize: 0,
                    highWaterMark: 1024 * 1024 * 10
                });

                const output = fs.createWriteStream(outputPath);

                videoOnly.on('error', handleError);
                videoOnly.pipe(output);

                output.on('finish', () => completeSuccess({ outputPath }));
                output.on('error', handleError);
            }

            videoStream.on('error', handleError);
        } catch (error) {
            sendToRenderer('download-error', { jobId: job.id, message: error.message });
            appendLog({
                level: 'error',
                message: 'YouTube download encountered an error',
                meta: { jobId: job.id, error: error.message }
            });
            completeJob(job.id, false, { error: error.message });
            reject(error);
        } finally {
            emitQueueUpdate();
        }
    });
};

const handleDownloadTikTok = async (_event, { url }) => {
    if (!ensureTikTokScraper()) {
        throw new Error('TikTok downloads are unavailable. Missing optional dependency.');
    }

    const job = createJob('tiktok-download', { url });
    appendLog({
        level: 'info',
        message: 'Starting TikTok download',
        meta: { jobId: job.id, url }
    });

    return new Promise(async (resolve, reject) => {
        try {
            updateJob(job.id, { status: 'running' });
            const videoInfo = await tiktokScraper.getVideoMeta(url);
            const videoUrl = videoInfo?.collector?.[0]?.videoUrl || videoInfo?.collector?.[0]?.videoUrlNoWaterMark;
            if (!videoUrl) {
                throw new Error('Could not resolve TikTok video URL');
            }

            const outputPath = path.join(app.getPath('downloads'), `tiktok_${Date.now()}.mp4`);
            const response = await fetch(videoUrl);
            const buffer = await response.arrayBuffer();
            await fs.promises.writeFile(outputPath, Buffer.from(buffer));

            completeJob(job.id, true, { outputPath });
            appendLog({
                level: 'info',
                message: 'TikTok download completed',
                meta: { jobId: job.id, outputPath }
            });
            resolve({ success: true, outputPath, jobId: job.id });
        } catch (error) {
            appendLog({
                level: 'error',
                message: 'TikTok download failed',
                meta: { jobId: job.id, error: error.message }
            });
            completeJob(job.id, false, { error: error.message });
            reject(error);
        } finally {
            emitQueueUpdate();
        }
    });
};

const handleConvertVideo = async (_event, { inputPath, outputPath, options = {} }) => {
    if (!inputPath || !outputPath) {
        throw new Error('Both inputPath and outputPath are required for conversion.');
    }
    if (!fs.existsSync(inputPath)) {
        throw new Error(`Input file does not exist: ${inputPath}`);
    }

    const job = createJob('convert-video', { inputPath, outputPath });
    appendLog({
        level: 'info',
        message: 'Starting video conversion',
        meta: { jobId: job.id, inputPath, outputPath }
    });

    const outputDir = path.dirname(outputPath);
    fs.mkdirSync(outputDir, { recursive: true });

    return new Promise((resolve, reject) => {
        try {
            const command = ffmpeg(inputPath)
                .output(outputPath)
                .on('progress', (progress) => {
                    const percent = typeof progress.percent === 'number' ? progress.percent : 0;
                    const payload = progressPayload(job.id, percent, {
                        frames: progress.frames,
                        bitrate: progress.currentKbps,
                        timemark: progress.timemark
                    });

                    updateJob(job.id, { status: 'running', progress: payload.percent });
                    sendToRenderer('convert-progress', payload);
                })
                .on('end', () => {
                    completeJob(job.id, true, { outputPath });
                    appendLog({
                        level: 'info',
                        message: 'Conversion completed',
                        meta: { jobId: job.id, outputPath }
                    });
                    resolve({ success: true, outputPath, jobId: job.id });
                })
                .on('error', (error) => {
                    appendLog({
                        level: 'error',
                        message: 'Conversion failed',
                        meta: { jobId: job.id, error: error.message }
                    });
                    sendToRenderer('download-error', { jobId: job.id, message: error.message });
                    completeJob(job.id, false, { error: error.message });
                    reject(error);
                });

            if (options.audioOnly) {
                command.noVideo().audioCodec('libmp3lame').audioBitrate('192k');
            }

            command.run();
        } catch (error) {
            appendLog({
                level: 'error',
                message: 'Conversion initialization failed',
                meta: { jobId: job.id, error: error.message }
            });
            completeJob(job.id, false, { error: error.message });
            reject(error);
        } finally {
            emitQueueUpdate();
        }
    });
};

const registerIpcHandlers = () => {
    if (ipcHandlersRegistered) {
        return;
    }
    ipcHandlersRegistered = true;

    ipcMain.handle('download-youtube', handleDownloadYoutube);
    ipcMain.handle('download-tiktok', handleDownloadTikTok);
    ipcMain.handle('convert-video', handleConvertVideo);
    ipcMain.handle('check-copyright', async (_event, { url }) => {
        appendLog({
            level: 'info',
            message: 'Copyright check requested',
            meta: { url }
        });
        // Placeholder logic – always returns safe
        await delay(300);
        return { isCopyrightSafe: true };
    });
    ipcMain.handle('queue:get', () => [...jobQueue]);
    ipcMain.handle('queue:clear-completed', () => {
        const removed = clearCompletedJobs();
        return { removed };
    });
    ipcMain.handle('get-environment', () => ({
        nodeVersion: process.version,
        electronVersion: process.versions.electron,
        chromeVersion: process.versions.chrome,
        platform: process.platform,
        arch: process.arch,
        ffmpeg: {
            available: Boolean(ffmpegBinary),
            path: ffmpegBinary
        },
        pythonStatus,
        downloadsDir: app.getPath('downloads'),
        appPath: app.getAppPath()
    }));
    ipcMain.handle('logger:get', (_event, options = {}) => {
        const limit = Number(options.limit) || MAX_LOG_BUFFER;
        return logBuffer.slice(-limit);
    });
    ipcMain.on('logger:log', (_event, entry) => {
        appendLog(entry || {});
    });
};

function createWindow() {
    // Create the browser window with secure defaults
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,  // Disable Node.js integration in the renderer
            contextIsolation: true,  // Enable context isolation
            enableRemoteModule: false, // Disable remote module
            preload: path.join(__dirname, 'preload.js'), // Use preload script
            webSecurity: true,       // Enable web security
            allowRunningInsecureContent: false // Don't allow insecure content
        },
        show: false // Don't show until ready-to-show
    });

    // Load the index.html file
    mainWindow.loadFile(path.join(__dirname, '..', 'index.html'));

    mainWindow.webContents.once('did-finish-load', () => {
        flushPendingRendererEvents();
    });

    // Open the DevTools in development mode
    if (process.env.NODE_ENV === 'development') {
        mainWindow.webContents.openDevTools();
    }

    // Show window when page is ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Handle external links
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });
}

// Check if server is running, start if needed
async function checkOrStartServer() {
    try {
        // First, try to connect to existing server
        const response = await fetch(`${SERVER_URL}/`);
        if (response.ok) {
            console.log('Server is already running');
            publishPythonStatus('ready', { mode: 'external', url: SERVER_URL });
            return true;
        }
    } catch (error) {
        console.log('Server not running, starting new instance...');
    }
    
    // Start the Python server if not running
    const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';

    const isDev = process.argv.includes('--dev') || process.env.NODE_ENV === 'development';
    const uvicornArgs = ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'];
    if (isDev) {
        uvicornArgs.push('--reload');
    }

    publishPythonStatus('starting', { mode: 'spawn', url: SERVER_URL });

    pythonProcess = spawn(
        pythonExecutable,
        uvicornArgs,
        {
            stdio: ['ignore', 'pipe', 'pipe'],
            shell: false,
            windowsHide: true,
            env: { ...process.env, PYTHONUNBUFFERED: '1' }
        }
    );

    if (pythonProcess.stdout) {
        pythonProcess.stdout.on('data', (chunk) => {
            const message = chunk.toString();
            console.log(`[python] ${message}`);
            appendLog({ level: 'info', message: '[python stdout]', meta: { message } });
        });
    }

    if (pythonProcess.stderr) {
        pythonProcess.stderr.on('data', (chunk) => {
            const message = chunk.toString();
            console.error(`[python] ${message}`);
            appendLog({ level: 'error', message: '[python stderr]', meta: { message } });
        });
    }

    pythonProcess.on('error', (err) => {
        console.error('Failed to start Python server:', err);
        publishPythonStatus('error', { mode: 'spawn', error: err.message });
        // Don't quit immediately, user might have server running elsewhere
    });

    pythonProcess.on('exit', (code, signal) => {
        console.log(`Python server exited with code ${code} and signal ${signal}`);
        publishPythonStatus('error', { mode: 'spawn', code, signal });
        // Don't quit on server exit, allow manual restart
    });

    const ready = await waitForServer(20000, 500);
    if (ready) {
        publishPythonStatus('ready', { mode: 'spawn', url: SERVER_URL });
        return true;
    }

    publishPythonStatus('error', { mode: 'spawn', error: 'Backend did not become ready within timeout', url: SERVER_URL });
    return false;
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
app.whenReady().then(async () => {
    // Check or start the Python server
    await checkOrStartServer();
    
    // Create the main window
    createWindow();

    app.on('activate', function () {
        // On macOS it's common to re-create a window in the app when the
        // dock icon is clicked and there are no other windows open.
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

// Quit when all windows are closed, except on macOS.
app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') {
        // Stop the Python server
        if (pythonProcess) {
            pythonProcess.kill();
            pythonProcess = null;
        }
        app.quit();
    }
});

// Clean up on exit
app.on('will-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});

// IPC handlers for communication with renderer process
ipcMain.handle('get-server-url', () => {
    return SERVER_URL;
});

// Example IPC handler for downloading files
ipcMain.handle('download-file', async (event, { url, filename }) => {
    const downloadPath = path.join(app.getPath('downloads'), filename);
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    fs.writeFileSync(downloadPath, buffer);
    return { success: true, path: downloadPath };
});

// Show a Save As dialog and return the chosen path
ipcMain.handle('choose-save-location', async (event, { defaultPath }) => {
    const win = BrowserWindow.getFocusedWindow() || mainWindow;
    const result = await dialog.showSaveDialog(win, {
        defaultPath,
        properties: ['showOverwriteConfirmation']
    });
    return { canceled: result.canceled, filePath: result.filePath };
});

// Copy a file from sourcePath to destPath
ipcMain.handle('save-file-to', async (event, { sourcePath, destPath }) => {
    try {
        await fs.promises.mkdir(path.dirname(destPath), { recursive: true });
        await fs.promises.copyFile(sourcePath, destPath);
        return { success: true, destPath };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

// Error handling
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// YouTube download handler
ipcMain.handle('downloadYouTube', async (event, { url, format }) => {
    try {
        const ytdl = require('ytdl-core');
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
