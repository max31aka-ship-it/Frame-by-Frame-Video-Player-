// player.ts
// Frame-by-Frame Video Player на TypeScript

import { spawn } from 'child_process';
import * as readline from 'readline';

const GRAYSCALE = " .,:;ox%#@";
const GRAYSCALE_LEN = GRAYSCALE.length;

function rgbToGray(r: number, g: number, b: number): number {
    return Math.round(0.299 * r + 0.587 * g + 0.114 * b);
}

function frameToAscii(frameData: Buffer, width: number, height: number,
                      termWidth: number, termHeight: number): string {
    const outW = Math.min(width, termWidth);
    const outH = Math.min(height, termHeight - 1);
    const stepX = width / outW;
    const stepY = height / outH;
    const lines: string[] = [];
    for (let y = 0; y < outH; y++) {
        let line = '';
        for (let x = 0; x < outW; x++) {
            const srcX = Math.floor(x * stepX);
            const srcY = Math.floor(y * stepY);
            const idx = (srcY * width + srcX) * 3;
            const r = frameData[idx];
            const g = frameData[idx+1];
            const b = frameData[idx+2];
            const gray = rgbToGray(r, g, b);
            const charIdx = Math.floor((gray / 255) * (GRAYSCALE_LEN - 1));
            line += GRAYSCALE[charIdx];
        }
        lines.push(line);
    }
    return lines.join('\n');
}

function extractFrames(videoPath: string, width: number, height: number): Promise<Buffer[]> {
    return new Promise((resolve, reject) => {
        const args = ['-i', videoPath, '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                      '-s', `${width}x${height}`, '-vframes', '0', '-'];
        const proc = spawn('ffmpeg', args);
        const chunks: Buffer[] = [];
        proc.stdout.on('data', chunk => chunks.push(chunk));
        proc.stderr.on('data', () => {});
        proc.on('close', code => {
            if (code !== 0) reject(new Error(`ffmpeg exited with code ${code}`));
            else {
                const all = Buffer.concat(chunks);
                const frameSize = width * height * 3;
                const frames: Buffer[] = [];
                for (let i = 0; i < all.length; i += frameSize) {
                    if (i + frameSize <= all.length) {
                        frames.push(all.slice(i, i + frameSize));
                    }
                }
                resolve(frames);
            }
        });
    });
}

async function main(): Promise<void> {
    const args = process.argv.slice(2);
    if (args.length < 1) {
        console.log('Использование: ts-node player.ts <video_file> [--width W] [--height H] [--fps N]');
        process.exit(1);
    }
    const video = args[0];
    let width = 80, height = 40, fps = 5;
    for (let i = 1; i < args.length; i++) {
        if (args[i] === '--width') { width = parseInt(args[++i]); }
        else if (args[i] === '--height') { height = parseInt(args[++i]); }
        else if (args[i] === '--fps') { fps = parseInt(args[++i]); }
    }
    const termWidth = process.stdout.columns || 80;
    const termHeight = process.stdout.rows || 24;
    width = Math.min(width, termWidth);
    height = Math.min(height, termHeight - 1);

    console.log(`Извлечение кадров из ${video}...`);
    let frames: Buffer[];
    try {
        frames = await extractFrames(video, width, height);
    } catch (e: any) {
        console.error(`Ошибка: ${e.message}. Убедитесь, что ffmpeg установлен.`);
        process.exit(1);
    }
    if (frames.length === 0) {
        console.log('Не удалось извлечь кадры.');
        process.exit(1);
    }
    const totalFrames = frames.length;
    console.log(`Извлечено ${totalFrames} кадров.`);

    const asciiCache: Map<number, string> = new Map();
    let currentIdx = 0;
    let playing = false;
    let currentFps = fps;
    let lastFrameTime = 0;

    function renderFrame(idx: number): void {
        if (idx < 0 || idx >= totalFrames) return;
        if (!asciiCache.has(idx)) {
            asciiCache.set(idx, frameToAscii(frames[idx], width, height, termWidth, termHeight));
        }
        console.clear();
        console.log(asciiCache.get(idx));
        console.log(`Кадр ${idx+1}/${totalFrames} | Скорость: ${currentFps} кадр/с | [Space] пауза, ←/→, +/- скорость, q выход`);
    }

    readline.emitKeypressEvents(process.stdin);
    process.stdin.setRawMode(true);
    process.stdin.on('keypress', (str, key) => {
        if (key.name === 'q' || key.name === 'escape') {
            process.stdin.setRawMode(false);
            process.exit(0);
        } else if (key.name === 'space') {
            playing = !playing;
            if (playing) lastFrameTime = Date.now();
        } else if (key.name === 'left') {
            if (currentIdx > 0) { currentIdx--; renderFrame(currentIdx); }
        } else if (key.name === 'right') {
            if (currentIdx < totalFrames - 1) { currentIdx++; renderFrame(currentIdx); }
        } else if (str === '+') {
            currentFps = Math.min(30, currentFps + 1);
        } else if (str === '-') {
            currentFps = Math.max(1, currentFps - 1);
        }
    });

    renderFrame(currentIdx);
    setInterval(() => {
        if (playing) {
            const now = Date.now();
            if (now - lastFrameTime >= 1000 / currentFps) {
                if (currentIdx < totalFrames - 1) {
                    currentIdx++;
                    renderFrame(currentIdx);
                } else {
                    playing = false;
                }
                lastFrameTime = now;
            }
        }
    }, 50);
}

main().catch(console.error);
