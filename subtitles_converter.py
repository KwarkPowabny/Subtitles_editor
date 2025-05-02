from datetime import timedelta
import os
import re
import argparse
import srt
import webvtt

def parse_vtt_time(t):
    h, m, s = t.split(':')
    s, ms = s.split('.')
    return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))

def shift_timecodes(subs, fmt, shift_seconds):
    shift = timedelta(seconds=shift_seconds)

    if fmt == 'srt':
        for sub in subs:
            sub.start = max(timedelta(0), sub.start + shift)
            sub.end = max(timedelta(0), sub.end + shift)
        return subs

    elif fmt == 'vtt':
        for sub in subs:
            start = parse_vtt_time(sub['start']) + shift
            end = parse_vtt_time(sub['end']) + shift
            sub['start'] = format_timestamp(max(timedelta(0), start))
            sub['end'] = format_timestamp(max(timedelta(0), end))
        return subs

    return subs


def detect_format(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.srt', '.vtt', '.txt']:
        return ext[1:]
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        if re.match(r'\d+\s*$', first_line):
            return 'srt'
        elif first_line.startswith('WEBVTT'):
            return 'vtt'
        else:
            return 'txt'

def read_subtitles(file_path):
    fmt = detect_format(file_path)
    if fmt == 'srt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return list(srt.parse(f.read())), fmt
    elif fmt == 'vtt':
        subs = []
        for caption in webvtt.read(file_path):
            subs.append({'start': caption.start, 'end': caption.end, 'text': caption.text})
        return subs, fmt
    elif fmt == 'txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return [{'text': line.strip()} for line in lines if line.strip()], fmt

def format_timestamp(td):
    total_seconds = int(td.total_seconds())
    millis = int((td.total_seconds() - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"


def convert_srt_to_vtt(subs):
    return [{
        'start': format_timestamp(s.start),
        'end': format_timestamp(s.end),
        'text': s.content
    } for s in subs]

def convert_vtt_to_srt(subs):
    return [srt.Subtitle(index=i+1,
                         start=srt.srt_timestamp_to_timedelta(s['start']),
                         end=srt.srt_timestamp_to_timedelta(s['end']),
                         content=s['text']) for i, s in enumerate(subs)]

def save_subtitles(subs, target_fmt, output_path):
    if target_fmt == 'srt':
        if isinstance(subs[0], dict):
            if 'start' not in subs[0]:  # txt → srt
                import datetime
                new_subs = []
                start = datetime.timedelta(seconds=0)
                step = datetime.timedelta(seconds=3)
                for i, sub in enumerate(subs):
                    end = start + step
                    new_subs.append(srt.Subtitle(index=i+1, start=start, end=end, content=sub['text']))
                    start = end
                subs = new_subs
            else:
                subs = convert_vtt_to_srt(subs)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt.compose(subs))

    elif target_fmt == 'vtt':
        if isinstance(subs[0], srt.Subtitle):
            subs = convert_srt_to_vtt(subs)
        vtt = webvtt.WebVTT()
        for sub in subs:
            vtt.captions.append(webvtt.Caption(sub['start'], sub['end'], sub['text']))
        vtt.save(output_path)

    elif target_fmt == 'txt':
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in subs:
                text = sub.content if isinstance(sub, srt.Subtitle) else sub['text']
                f.write(text + '\n')

def main():
    parser = argparse.ArgumentParser(description='Konwerter plików napisów (SRT, VTT, TXT)')
    parser.add_argument('--input', '-i', required=True, help='Ścieżka do pliku wejściowego')
    parser.add_argument('--output', '-o', required=True, help='Ścieżka do pliku wyjściowego')
    parser.add_argument('--to', '-t', required=True, choices=['srt', 'vtt', 'txt'], help='Format docelowy')
    parser.add_argument('--shift', type=float, default=0.0,
                    help='Przesunięcie czasowe napisów w sekundach (może być ujemne)')

    args = parser.parse_args()
    subs, source_fmt = read_subtitles(args.input)
    if args.shift:
        subs = shift_timecodes(subs, detect_format(args.input), args.shift)

    print(f"Wykryty format źródłowy: {source_fmt}")
    save_subtitles(subs, args.to, args.output)
    print(f"Zapisano plik: {args.output} jako {args.to.upper()}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nBłąd: {e}")
        input("\nNaciśnij Enter, aby zamknąć...")
