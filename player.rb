# player.rb
# Frame-by-Frame Video Player на Ruby

require 'open3'
require 'io/console'

GRAYSCALE = " .,:;ox%#@"
GRAYSCALE_LEN = GRAYSCALE.length

def rgb_to_gray(r, g, b)
  (0.299 * r + 0.587 * g + 0.114 * b).to_i
end

def frame_to_ascii(data, width, height, term_w, term_h)
  out_w = [width, term_w].min
  out_h = [height, term_h - 1].min
  step_x = width.to_f / out_w
  step_y = height.to_f / out_h
  lines = []
  out_h.times do |y|
    line = ''
    out_w.times do |x|
      src_x = (x * step_x).to_i
      src_y = (y * step_y).to_i
      idx = (src_y * width + src_x) * 3
      r, g, b = data[idx, 3].bytes
      gray = rgb_to_gray(r, g, b)
      char_idx = ((gray / 255.0) * (GRAYSCALE_LEN - 1)).to_i
      line << GRAYSCALE[char_idx]
    end
    lines << line
  end
  lines.join("\n")
end

def extract_frames(video_path, width, height)
  cmd = ['ffmpeg', '-i', video_path, '-f', 'rawvideo', '-pix_fmt', 'rgb24',
         '-s', "#{width}x#{height}", '-vframes', '0', '-']
  frames = []
  Open3.popen3(*cmd) do |stdin, stdout, stderr, wait_thr|
    stderr.close
    frame_size = width * height * 3
    while data = stdout.read(frame_size)
      break if data.size < frame_size
      frames << data
    end
  end
  frames
end

def get_term_size
  [80, 24]
end

if ARGV.empty?
  puts "Использование: ruby player.rb <video_file> [--width W] [--height H] [--fps N]"
  exit 1
end

video = ARGV[0]
width = 80
height = 40
fps = 5
i = 1
while i < ARGV.length
  case ARGV[i]
  when '--width'
    width = ARGV[i+1].to_i; i += 2
  when '--height'
    height = ARGV[i+1].to_i; i += 2
  when '--fps'
    fps = ARGV[i+1].to_i; i += 2
  else
    i += 1
  end
end

term_w, term_h = get_term_size
width = [width, term_w].min
height = [height, term_h - 1].min

puts "Извлечение кадров из #{video}..."
frames = extract_frames(video, width, height)
if frames.empty?
  puts "Не удалось извлечь кадры. Убедитесь, что ffmpeg установлен."
  exit 1
end
total = frames.size
puts "Извлечено #{total} кадров."

cache = {}
current_idx = 0
playing = false
current_fps = fps
last_frame_time = Time.now

def render_frame(idx, frames, width, height, term_w, term_h, total, cache, current_fps)
  return if idx < 0 || idx >= total
  unless cache[idx]
    cache[idx] = frame_to_ascii(frames[idx], width, height, term_w, term_h)
  end
  print "\033[H\033[J"  # clear
  puts cache[idx]
  puts "Кадр #{idx+1}/#{total} | Скорость: #{current_fps} кадр/с | [Space] пауза, ←/→, +/- скорость, q выход"
end

render_frame(current_idx, frames, width, height, term_w, term_h, total, cache, current_fps)

# Ввод в отдельном потоке
Thread.new do
  while true
    char = STDIN.getch
    if char == 'q'
      puts "\nВыход."
      exit
    elsif char == ' '
      playing = !playing
      if playing
        last_frame_time = Time.now
      end
    elsif char == '+'
      current_fps = [30, current_fps + 1].min
    elsif char == '-'
      current_fps = [1, current_fps - 1].max
    elsif char == "\x1b"
      # стрелки
      seq = STDIN.read(2)
      if seq == '[D'
        if current_idx > 0
          current_idx -= 1
          render_frame(current_idx, frames, width, height, term_w, term_h, total, cache, current_fps)
        end
      elsif seq == '[C'
        if current_idx < total - 1
          current_idx += 1
          render_frame(current_idx, frames, width, height, term_w, term_h, total, cache, current_fps)
        end
      end
    end
  end
end

# Автовоспроизведение
while true
  if playing
    now = Time.now
    if now - last_frame_time >= 1.0 / current_fps
      if current_idx < total - 1
        current_idx += 1
        render_frame(current_idx, frames, width, height, term_w, term_h, total, cache, current_fps)
      else
        playing = false
      end
      last_frame_time = now
    end
  end
  sleep 0.05
end
