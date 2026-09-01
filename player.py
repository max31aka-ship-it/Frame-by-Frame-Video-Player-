# player.py
# Frame-by-Frame Video Player на Python

import sys
import subprocess
import os
import tempfile
import struct
import termios
import tty
import select
import time
import shutil
import math
from collections import deque

# Набор символов для градаций серого (от светлого к тёмному)
GRAYSCALE = " .,:;ox%#@"
GRAYSCALE_LEN = len(GRAYSCALE)

def get_terminal_size():
    """Возвращает размер терминала в символах."""
    try:
        import shutil
        cols, rows = shutil.get_terminal_size()
        return cols, rows
    except:
        return 80, 24

def rgb_to_gray(r, g, b):
    """Преобразует RGB в яркость (0-255)."""
    return int(0.299 * r + 0.587 * g + 0.114 * b)

def frame_to_ascii(frame_data, width, height, term_width, term_height):
    """Преобразует сырые данные кадра (RGB24) в ASCII-строку."""
    # Определяем реальные размеры вывода
    out_w = min(width, term_width)
    out_h = min(height, term_height - 1)  # оставляем строку для информации
    # Масштабируем кадр до out_w x out_h
    frame_w = width
    frame_h = height
    # Рассчитываем шаг выборки
    step_x = frame_w / out_w
    step_y = frame_h / out_h
    lines = []
    for y in range(out_h):
        line_chars = []
        for x in range(out_w):
            # Билинейная интерполяция (упрощённо: берём ближайший пиксель)
            src_x = int(x * step_x)
            src_y = int(y * step_y)
            idx = (src_y * frame_w + src_x) * 3
            r = frame_data[idx]
            g = frame_data[idx+1]
            b = frame_data[idx+2]
            gray = rgb_to_gray(r, g, b)
            # Нормализуем 0-255 к индексу символа
            idx_char = int((gray / 255) * (GRAYSCALE_LEN - 1))
            line_chars.append(GRAYSCALE[idx_char])
        lines.append(''.join(line_chars))
    return '\n'.join(lines)

def extract_frames(video_path, width, height):
    """Извлекает все кадры из видео с помощью ffmpeg и возвращает список байтовых строк."""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-f', 'rawvideo',
        '-pix_fmt', 'rgb24',
        '-s', f'{width}x{height}',
        '-vframes', '0',  # все кадры
        '-'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_size = width * height * 3
    frames = []
    while True:
        data = proc.stdout.read(frame_size)
        if not data:
            break
        if len(data) < frame_size:
            break
        frames.append(data)
    proc.wait()
    return frames

def main():
    if len(sys.argv) < 2:
        print("Использование: python player.py <video_file> [--width W] [--height H] [--fps N]")
        sys.exit(1)
    video = sys.argv[1]
    # Парсинг аргументов
    width = 80
    height = 40
    fps = 5
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--width':
            width = int(sys.argv[i+1])
            i += 2
        elif sys.argv[i] == '--height':
            height = int(sys.argv[i+1])
            i += 2
        elif sys.argv[i] == '--fps':
            fps = int(sys.argv[i+1])
            i += 2
        else:
            i += 1

    # Получаем размер терминала
    term_w, term_h = get_terminal_size()
    width = min(width, term_w)
    height = min(height, term_h - 1)

    print(f"Извлечение кадров из {video}...")
    try:
        frames = extract_frames(video, width, height)
    except Exception as e:
        print(f"Ошибка: {e}. Убедитесь, что ffmpeg установлен.")
        sys.exit(1)
    if not frames:
        print("Не удалось извлечь кадры.")
        sys.exit(1)
    total_frames = len(frames)
    print(f"Извлечено {total_frames} кадров.")
    if total_frames == 0:
        sys.exit(0)

    # Кэш ASCII-представлений кадров (для ускорения)
    ascii_cache = {}
    current_idx = 0
    playing = False
    current_fps = fps
    last_frame_time = 0

    # Настройка терминала для неблокирующего ввода
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
    except:
        pass

    def render_frame(idx):
        nonlocal ascii_cache
        if idx < 0 or idx >= total_frames:
            return
        if idx not in ascii_cache:
            frame_data = frames[idx]
            ascii_cache[idx] = frame_to_ascii(frame_data, width, height, term_w, term_h)
        # Очищаем экран и выводим
        sys.stdout.write('\033[H\033[J')  # move to top-left and clear
        sys.stdout.write(ascii_cache[idx])
        info = f"Кадр {idx+1}/{total_frames} | FPS видео: ? | Скорость: {current_fps} кадр/с | [Space] пауза, ←/→, +/- скорость, q выход"
        sys.stdout.write('\n' + info)
        sys.stdout.flush()

    def handle_key(key):
        nonlocal current_idx, playing, current_fps, last_frame_time
        if key == 'q' or key == '\x1b':  # q или Escape
            return False
        elif key == ' ':
            playing = not playing
            if playing:
                last_frame_time = time.time()
        elif key == '\x1b[D' or key == 'a':  # left arrow or 'a'
            if current_idx > 0:
                current_idx -= 1
                render_frame(current_idx)
        elif key == '\x1b[C' or key == 'd':  # right arrow or 'd'
            if current_idx < total_frames - 1:
                current_idx += 1
                render_frame(current_idx)
        elif key == '+':
            current_fps = min(30, current_fps + 1)
        elif key == '-':
            current_fps = max(1, current_fps - 1)
        return True

    render_frame(current_idx)

    # Главный цикл
    running = True
    while running:
        # Проверка ввода
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == '\x1b':
                # последовательность стрелок
                key += sys.stdin.read(2)
            if not handle_key(key):
                running = False
                break

        # Автовоспроизведение
        if playing:
            now = time.time()
            if now - last_frame_time >= 1.0 / current_fps:
                if current_idx < total_frames - 1:
                    current_idx += 1
                    render_frame(current_idx)
                else:
                    playing = False  # остановить в конце
                last_frame_time = now

        time.sleep(0.01)

    # Восстановление терминала
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except:
        pass

if __name__ == "__main__":
    main()
