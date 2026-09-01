// Player.cs
// Frame-by-Frame Video Player на C#

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

class Player
{
    private const string GRAYSCALE = " .,:;ox%#@";
    private static int GRAYSCALE_LEN = GRAYSCALE.Length;

    static int RgbToGray(byte r, byte g, byte b)
    {
        return (int)(0.299 * r + 0.587 * g + 0.114 * b);
    }

    static string FrameToAscii(byte[] data, int width, int height, int termW, int termH)
    {
        int outW = Math.Min(width, termW);
        int outH = Math.Min(height, termH - 1);
        double stepX = (double)width / outW;
        double stepY = (double)height / outH;
        var sb = new StringBuilder();
        for (int y = 0; y < outH; y++)
        {
            for (int x = 0; x < outW; x++)
            {
                int srcX = (int)(x * stepX);
                int srcY = (int)(y * stepY);
                int idx = (srcY * width + srcX) * 3;
                byte r = data[idx];
                byte g = data[idx + 1];
                byte b = data[idx + 2];
                int gray = RgbToGray(r, g, b);
                int charIdx = (int)((gray / 255.0) * (GRAYSCALE_LEN - 1));
                sb.Append(GRAYSCALE[charIdx]);
            }
            sb.Append('\n');
        }
        return sb.ToString();
    }

    static List<byte[]> ExtractFrames(string videoPath, int width, int height)
    {
        var args = $"-i \"{videoPath}\" -f rawvideo -pix_fmt rgb24 -s {width}x{height} -vframes 0 -";
        var startInfo = new ProcessStartInfo("ffmpeg", args)
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        var proc = Process.Start(startInfo);
        var frames = new List<byte[]>();
        int frameSize = width * height * 3;
        byte[] buffer = new byte[frameSize];
        using (var stream = proc.StandardOutput.BaseStream)
        {
            while (true)
            {
                int read = 0;
                while (read < frameSize)
                {
                    int n = stream.Read(buffer, read, frameSize - read);
                    if (n == 0) break;
                    read += n;
                }
                if (read == frameSize)
                {
                    byte[] frame = new byte[frameSize];
                    Buffer.BlockCopy(buffer, 0, frame, 0, frameSize);
                    frames.Add(frame);
                }
                else break;
            }
        }
        proc.WaitForExit();
        return frames;
    }

    static void Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.WriteLine("Использование: Player <video_file> [--width W] [--height H] [--fps N]");
            return;
        }
        string video = args[0];
        int width = 80, height = 40, fps = 5;
        for (int i = 1; i < args.Length; i++)
        {
            if (args[i] == "--width") width = int.Parse(args[++i]);
            else if (args[i] == "--height") height = int.Parse(args[++i]);
            else if (args[i] == "--fps") fps = int.Parse(args[++i]);
        }
        int termW = Console.WindowWidth;
        int termH = Console.WindowHeight;
        width = Math.Min(width, termW);
        height = Math.Min(height, termH - 1);

        Console.WriteLine($"Извлечение кадров из {video}...");
        var frames = ExtractFrames(video, width, height);
        if (frames.Count == 0)
        {
            Console.WriteLine("Не удалось извлечь кадры.");
            return;
        }
        int total = frames.Count;
        Console.WriteLine($"Извлечено {total} кадров.");

        var cache = new Dictionary<int, string>();
        int currentIdx = 0;
        bool playing = false;
        int currentFps = fps;
        DateTime lastFrameTime = DateTime.Now;

        void RenderFrame(int idx)
        {
            if (idx < 0 || idx >= total) return;
            if (!cache.ContainsKey(idx))
            {
                cache[idx] = FrameToAscii(frames[idx], width, height, termW, termH);
            }
            Console.Clear();
            Console.WriteLine(cache[idx]);
            Console.WriteLine($"Кадр {idx+1}/{total} | Скорость: {currentFps} кадр/с | [Space] пауза, ←/→, +/- скорость, q выход");
        }

        RenderFrame(currentIdx);

        // Поток ввода
        Thread inputThread = new Thread(() =>
        {
            while (true)
            {
                if (Console.KeyAvailable)
                {
                    var key = Console.ReadKey(true);
                    if (key.Key == ConsoleKey.Q || key.Key == ConsoleKey.Escape)
                    {
                        Console.WriteLine("\nВыход.");
                        Environment.Exit(0);
                    }
                    else if (key.Key == ConsoleKey.Spacebar)
                    {
                        playing = !playing;
                        if (playing) lastFrameTime = DateTime.Now;
                    }
                    else if (key.Key == ConsoleKey.LeftArrow)
                    {
                        if (currentIdx > 0) { currentIdx--; RenderFrame(currentIdx); }
                    }
                    else if (key.Key == ConsoleKey.RightArrow)
                    {
                        if (currentIdx < total - 1) { currentIdx++; RenderFrame(currentIdx); }
                    }
                    else if (key.KeyChar == '+')
                    {
                        currentFps = Math.Min(30, currentFps + 1);
                    }
                    else if (key.KeyChar == '-')
                    {
                        currentFps = Math.Max(1, currentFps - 1);
                    }
                }
                Thread.Sleep(50);
            }
        });
        inputThread.IsBackground = true;
        inputThread.Start();

        // Автовоспроизведение
        while (true)
        {
            if (playing)
            {
                var now = DateTime.Now;
                if ((now - lastFrameTime).TotalSeconds >= 1.0 / currentFps)
                {
                    if (currentIdx < total - 1)
                    {
                        currentIdx++;
                        RenderFrame(currentIdx);
                    }
                    else
                    {
                        playing = false;
                    }
                    lastFrameTime = now;
                }
            }
            Thread.Sleep(50);
        }
    }
}
