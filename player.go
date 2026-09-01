// player.go
// Frame-by-Frame Video Player на Go

package main

import (
	"bufio"
	"encoding/binary"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
	"time"
)

const grayscale = " .,:;ox%#@"
const grayscaleLen = len(grayscale)

func rgbToGray(r, g, b byte) byte {
	return byte(0.299*float64(r) + 0.587*float64(g) + 0.114*float64(b))
}

func frameToAscii(data []byte, width, height, termW, termH int) string {
	outW := min(width, termW)
	outH := min(height, termH-1)
	stepX := float64(width) / float64(outW)
	stepY := float64(height) / float64(outH)
	lines := make([]string, outH)
	for y := 0; y < outH; y++ {
		line := make([]byte, outW)
		for x := 0; x < outW; x++ {
			srcX := int(float64(x) * stepX)
			srcY := int(float64(y) * stepY)
			idx := (srcY*width + srcX) * 3
			r := data[idx]
			g := data[idx+1]
			b := data[idx+2]
			gray := rgbToGray(r, g, b)
			charIdx := int(float64(gray) / 255.0 * float64(grayscaleLen-1))
			line[x] = grayscale[charIdx]
		}
		lines[y] = string(line)
	}
	return join(lines, "\n")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func join(arr []string, sep string) string {
	res := ""
	for i, s := range arr {
		if i > 0 {
			res += sep
		}
		res += s
	}
	return res
}

func extractFrames(videoPath string, width, height int) ([][]byte, error) {
	cmd := exec.Command("ffmpeg",
		"-i", videoPath,
		"-f", "rawvideo",
		"-pix_fmt", "rgb24",
		"-s", fmt.Sprintf("%dx%d", width, height),
		"-vframes", "0",
		"-")
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	stderr, _ := cmd.StderrPipe()
	go io.Copy(io.Discard, stderr)
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	frameSize := width * height * 3
	var frames [][]byte
	buf := make([]byte, frameSize)
	for {
		n, err := stdout.Read(buf)
		if err != nil {
			break
		}
		if n < frameSize {
			break
		}
		// copy frame
		frame := make([]byte, frameSize)
		copy(frame, buf)
		frames = append(frames, frame)
	}
	cmd.Wait()
	return frames, nil
}

func main() {
	video := flag.String("video", "", "Видеофайл")
	width := flag.Int("width", 80, "Ширина ASCII-вывода")
	height := flag.Int("height", 40, "Высота ASCII-вывода")
	fps := flag.Int("fps", 5, "Скорость автовоспроизведения (кадр/с)")
	flag.Parse()
	if *video == "" {
		fmt.Println("Использование: go run player.go -video <file> [--width W] [--height H] [--fps N]")
		os.Exit(1)
	}
	// Размер терминала
	termW := 80
	termH := 24
	// Попытка получить размер терминала (Unix)
	if w, h, err := getTermSize(); err == nil {
		termW = w
		termH = h
	}
	*width = min(*width, termW)
	*height = min(*height, termH-1)

	fmt.Printf("Извлечение кадров из %s...\n", *video)
	frames, err := extractFrames(*video, *width, *height)
	if err != nil {
		fmt.Printf("Ошибка: %v. Убедитесь, что ffmpeg установлен.\n", err)
		os.Exit(1)
	}
	if len(frames) == 0 {
		fmt.Println("Не удалось извлечь кадры.")
		os.Exit(1)
	}
	total := len(frames)
	fmt.Printf("Извлечено %d кадров.\n", total)

	asciiCache := make(map[int]string)
	currentIdx := 0
	playing := false
	currentFps := *fps
	lastFrameTime := time.Now()

	renderFrame := func(idx int) {
		if idx < 0 || idx >= total {
			return
		}
		if _, ok := asciiCache[idx]; !ok {
			asciiCache[idx] = frameToAscii(frames[idx], *width, *height, termW, termH)
		}
		fmt.Print("\033[H\033[J") // clear screen
		fmt.Println(asciiCache[idx])
		fmt.Printf("Кадр %d/%d | Скорость: %d кадр/с | [Space] пауза, ←/→, +/- скорость, q выход\n",
			idx+1, total, currentFps)
	}

	renderFrame(currentIdx)

	// Неблокирующий ввод
	go func() {
		reader := bufio.NewReader(os.Stdin)
		for {
			b, err := reader.ReadByte()
			if err != nil {
				break
			}
			key := string(b)
			if key == "q" || key == "\x1b" {
				// escape sequence
				if key == "\x1b" {
					// read next two bytes
					b2, _ := reader.ReadByte()
					b3, _ := reader.ReadByte()
					if b2 == '[' {
						if b3 == 'D' { // left
							if currentIdx > 0 {
								currentIdx--
								renderFrame(currentIdx)
							}
						} else if b3 == 'C' { // right
							if currentIdx < total-1 {
								currentIdx++
								renderFrame(currentIdx)
							}
						}
					}
				} else {
					// q
					fmt.Println("\nВыход.")
					os.Exit(0)
				}
			} else if key == " " {
				playing = !playing
				if playing {
					lastFrameTime = time.Now()
				}
			} else if key == "+" {
				currentFps = min(30, currentFps+1)
			} else if key == "-" {
				currentFps = max(1, currentFps-1)
			}
		}
	}()

	// Автовоспроизведение
	for {
		if playing {
			now := time.Now()
			if now.Sub(lastFrameTime) >= time.Second/time.Duration(currentFps) {
				if currentIdx < total-1 {
					currentIdx++
					renderFrame(currentIdx)
				} else {
					playing = false
				}
				lastFrameTime = now
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// Заглушка для получения размера терминала (Unix)
func getTermSize() (int, int, error) {
	// Для Windows можно использовать другие методы, для простоты возвращаем стандарт
	return 80, 24, nil
}
