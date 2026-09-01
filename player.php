<?php
// player.php
// Frame-by-Frame Video Player на PHP (консоль)

if (php_sapi_name() !== 'cli') {
    die("Это консольное приложение.\n");
}

$GRAYSCALE = " .,:;ox%#@";
$GRAYSCALE_LEN = strlen($GRAYSCALE);

function rgbToGray($r, $g, $b) {
    return (int)(0.299 * $r + 0.587 * $g + 0.114 * $b);
}

function frameToAscii($data, $width, $height, $termW, $termH) {
    $outW = min($width, $termW);
    $outH = min($height, $termH - 1);
    $stepX = $width / $outW;
    $stepY = $height / $outH;
    $lines = [];
    for ($y = 0; $y < $outH; $y++) {
        $line = '';
        for ($x = 0; $x < $outW; $x++) {
            $srcX = (int)($x * $stepX);
            $srcY = (int)($y * $stepY);
            $idx = ($srcY * $width + $srcX) * 3;
            $r = ord($data[$idx]);
            $g = ord($data[$idx+1]);
            $b = ord($data[$idx+2]);
            $gray = rgbToGray($r, $g, $b);
            $charIdx = (int)(($gray / 255) * ($GRAYSCALE_LEN - 1));
            $line .= $GRAYSCALE[$charIdx];
        }
        $lines[] = $line;
    }
    return implode("\n", $lines);
}

function extractFrames($videoPath, $width, $height) {
    $cmd = sprintf('ffmpeg -i "%s" -f rawvideo -pix_fmt rgb24 -s %dx%d -vframes 0 - 2>nul',
        $videoPath, $width, $height);
    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w']
    ];
    $proc = proc_open($cmd, $descriptors, $pipes);
    if (!is_resource($proc)) return [];
    $frameSize = $width * $height * 3;
    $frames = [];
    while (true) {
        $data = fread($pipes[1], $frameSize);
        if (strlen($data) < $frameSize) break;
        $frames[] = $data;
    }
    fclose($pipes[1]);
    fclose($pipes[2]);
    proc_close($proc);
    return $frames;
}

function getTermSize() {
    $cols = 80;
    $rows = 24;
    if (function_exists('shell_exec')) {
        $size = shell_exec('stty size 2>/dev/null');
        if ($size) {
            list($rows, $cols) = explode(' ', trim($size));
        }
    }
    return [$cols, $rows];
}

$args = array_slice($argv, 1);
if (empty($args)) {
    echo "Использование: php player.php <video_file> [--width W] [--height H] [--fps N]\n";
    exit(1);
}
$video = $args[0];
$width = 80;
$height = 40;
$fps = 5;
for ($i = 1; $i < count($args); $i++) {
    if ($args[$i] == '--width') { $width = (int)$args[++$i]; }
    elseif ($args[$i] == '--height') { $height = (int)$args[++$i]; }
    elseif ($args[$i] == '--fps') { $fps = (int)$args[++$i]; }
}
list($termW, $termH) = getTermSize();
$width = min($width, $termW);
$height = min($height, $termH - 1);

echo "Извлечение кадров из $video...\n";
$frames = extractFrames($video, $width, $height);
if (empty($frames)) {
    echo "Не удалось извлечь кадры. Убедитесь, что ffmpeg установлен.\n";
    exit(1);
}
$total = count($frames);
echo "Извлечено $total кадров.\n";

$cache = [];
$currentIdx = 0;
$playing = false;
$currentFps = $fps;
$lastFrameTime = microtime(true);

function renderFrame($idx) {
    global $frames, $width, $height, $termW, $termH, $total, $cache, $currentFps, $currentIdx;
    if ($idx < 0 || $idx >= $total) return;
    if (!isset($cache[$idx])) {
        $cache[$idx] = frameToAscii($frames[$idx], $width, $height, $termW, $termH);
    }
    echo "\033[H\033[J"; // clear
    echo $cache[$idx] . "\n";
    echo "Кадр " . ($idx+1) . "/$total | Скорость: $currentFps кадр/с | [Space] пауза, ←/→, +/- скорость, q выход\n";
}

renderFrame($currentIdx);

// Неблокирующий ввод
system('stty -echo cbreak'); // для Unix
while (true) {
    // Проверка ввода
    if (function_exists('stream_select')) {
        $r = [STDIN];
        $w = [];
        $e = [];
        if (stream_select($r, $w, $e, 0, 50000) > 0) {
            $char = fread(STDIN, 1);
            if ($char === "\x1b") {
                // стрелка
                $seq = fread(STDIN, 2);
                if ($seq === '[D') { // left
                    if ($currentIdx > 0) { $currentIdx--; renderFrame($currentIdx); }
                } elseif ($seq === '[C') { // right
                    if ($currentIdx < $total - 1) { $currentIdx++; renderFrame($currentIdx); }
                }
            } else {
                if ($char == 'q' || $char == "\x1b") {
                    echo "\nВыход.\n";
                    system('stty echo -cbreak');
                    exit(0);
                } elseif ($char == ' ') {
                    $playing = !$playing;
                    if ($playing) $lastFrameTime = microtime(true);
                } elseif ($char == '+') {
                    $currentFps = min(30, $currentFps + 1);
                } elseif ($char == '-') {
                    $currentFps = max(1, $currentFps - 1);
                }
            }
        }
    }

    // Автовоспроизведение
    if ($playing) {
        $now = microtime(true);
        if ($now - $lastFrameTime >= 1 / $currentFps) {
            if ($currentIdx < $total - 1) {
                $currentIdx++;
                renderFrame($currentIdx);
            } else {
                $playing = false;
            }
            $lastFrameTime = $now;
        }
    }
    usleep(50000);
}
