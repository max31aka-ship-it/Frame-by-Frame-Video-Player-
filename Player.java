// Player.java
// Frame-by-Frame Video Player на Java

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.Channels;
import java.nio.channels.ReadableByteChannel;
import java.util.*;

public class Player {
    private static final String GRAYSCALE = " .,:;ox%#@";
    private static final int GRAYSCALE_LEN = GRAYSCALE.length();

    private static int rgbToGray(int r, int g, int b) {
        return (int)(0.299 * r + 0.587 * g + 0.114 * b);
    }

    private static String frameToAscii(byte[] data, int width, int height, int termW, int termH) {
        int outW = Math.min(width, termW);
        int outH = Math.min(height, termH - 1);
        double stepX = (double)width / outW;
        double stepY = (double)height / outH;
        StringBuilder sb = new StringBuilder();
        for (int y = 0; y < outH; y++) {
            for (int x = 0; x < outW; x++) {
                int srcX = (int)(x * stepX);
                int srcY = (int)(y * stepY);
                int idx = (srcY * width + srcX) * 3;
                int r = data[idx] & 0xFF;
                int g = data[idx+1] & 0xFF;
                int b = data[idx+2] & 0xFF;
                int gray = rgbToGray(r, g, b);
                int charIdx = (int)((gray / 255.0) * (GRAYSCALE_LEN - 1));
                sb.append(GRAYSCALE.charAt(charIdx));
            }
            sb.append('\n');
        }
        return sb.toString();
    }

    private static List<byte[]> extractFrames(String videoPath, int width, int height) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(
            "ffmpeg", "-i", videoPath,
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", width + "x" + height,
            "-vframes", "0",
            "-"
        );
        pb.redirectErrorStream(false);
        Process proc = pb.start();
        // Читаем stdout
        InputStream in = proc.getInputStream();
        ReadableByteChannel channel = Channels.newChannel(in);
        ByteBuffer buf = ByteBuffer.allocate(width * height * 3);
        List<byte[]> frames = new ArrayList<>();
        while (channel.read(buf) != -1) {
            buf.flip();
            if (buf.remaining() == width * height * 3) {
                byte[] frame = new byte[buf.remaining()];
                buf.get(frame);
                frames.add(frame);
            }
            buf.clear();
        }
        // Ждём завершения
        proc.waitFor();
        return frames;
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.out.println("Использование: java Player <video_file> [--width W] [--height H] [--fps N]");
            System.exit(1);
        }
        String video = args[0];
        int width = 80, height = 40, fps = 5;
        for (int i = 1; i < args.length; i++) {
            if (args[i].equals("--width")) { width = Integer.parseInt(args[++i]); }
            else if (args[i].equals("--height")) { height = Integer.parseInt(args[++i]); }
            else if (args[i].equals("--fps")) { fps = Integer.parseInt(args[++i]); }
        }
        // Размер терминала (заглушка)
        int termW = 80, termH = 24;
        width = Math.min(width, termW);
        height = Math.min(height, termH - 1);

        System.out.println("Извлечение кадров из " + video + "...");
        List<byte[]> frames = extractFrames(video, width, height);
        if (frames.isEmpty()) {
            System.out.println("Не удалось извлечь кадры.");
            System.exit(1);
        }
        int total = frames.size();
        System.out.println("Извлечено " + total + " кадров.");

        // Кэш
        Map<Integer, String> cache = new HashMap<>();
        int[] currentIdx = {0};
        boolean[] playing = {false};
        int[] currentFps = {fps};
        long[] lastFrameTime = {System.currentTimeMillis()};

        Runnable renderFrame = () -> {
            int idx = currentIdx[0];
            if (idx < 0 || idx >= total) return;
            if (!cache.containsKey(idx)) {
                cache.put(idx, frameToAscii(frames.get(idx), width, height, termW, termH));
            }
            System.out.print("\033[H\033[J");
            System.out.println(cache.get(idx));
            System.out.printf("Кадр %d/%d | Скорость: %d кадр/с | [Space] пауза, ←/→, +/- скорость, q выход\n",
                idx+1, total, currentFps[0]);
        };

        renderFrame.run();

        // Поток для ввода
        Thread inputThread = new Thread(() -> {
            try {
                BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
                while (true) {
                    int ch = System.in.read();
                    if (ch == -1) break;
                    char c = (char)ch;
                    if (c == 'q' || c == '\033') {
                        // Escape sequences не обрабатываем для простоты, только буквы
                        System.out.println("\nВыход.");
                        System.exit(0);
                    } else if (c == ' ') {
                        playing[0] = !playing[0];
                        if (playing[0]) lastFrameTime[0] = System.currentTimeMillis();
                    } else if (c == '+') {
                        currentFps[0] = Math.min(30, currentFps[0] + 1);
                    } else if (c == '-') {
                        currentFps[0] = Math.max(1, currentFps[0] - 1);
                    } else if (c == 'a') { // left
                        if (currentIdx[0] > 0) { currentIdx[0]--; renderFrame.run(); }
                    } else if (c == 'd') { // right
                        if (currentIdx[0] < total - 1) { currentIdx[0]++; renderFrame.run(); }
                    }
                }
            } catch (IOException e) {}
        });
        inputThread.setDaemon(true);
        inputThread.start();

        // Автовоспроизведение
        while (true) {
            if (playing[0]) {
                long now = System.currentTimeMillis();
                if (now - lastFrameTime[0] >= 1000 / currentFps[0]) {
                    if (currentIdx[0] < total - 1) {
                        currentIdx[0]++;
                        renderFrame.run();
                    } else {
                        playing[0] = false;
                    }
                    lastFrameTime[0] = now;
                }
            }
            Thread.sleep(50);
        }
    }
}
