from datetime import timedelta
import os
import re
import argparse
import srt
#import webvtt

#poprawka z 26/06
from datetime import timedelta

def parse_timestamp(ts: str) -> timedelta:
    # obsłuż formaty "HH:MM:SS.mmm" i "HH:MM:SS,mmm"
    ts = ts.replace(',', '.')
    h, m, s = ts.split(':')
    s, ms = s.split('.')
    return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))

from datetime import timedelta

def apply_cut_ranges(subs, source_fmt, cut_ranges):
    def total_cut_before(t: timedelta) -> timedelta:
        total = timedelta()
        for start, end in cut_ranges:
            if t <= start:
                break
            # jeżeli t > start, to do shift wliczamy fragment cięcia od start do min(end, t)
            total += min(end, t) - start
        return total

    new_subs = []
    for sub in subs:
        # wyciągnij oryginalne czasy
        if source_fmt == 'srt':
            orig_t0, orig_t1 = sub.start, sub.end
        else:
            orig_t0 = parse_timestamp(sub['start'])
            orig_t1 = parse_timestamp(sub['end'])

        t0, t1 = orig_t0, orig_t1
        remove = False

        # sprawdź po kolei każde cięcie
        for start, end in cut_ranges:
            # jeśli cały napis jest wewnątrz zakresu cięcia -> usuń
            if start <= t0 and t1 <= end:
                remove = True
                break

            # częściowe nachodzenie na początek cięcia: przycinamy koniec napisu
            if t0 < start < t1:
                t1 = start

            # częściowe nachodzenie na koniec cięcia: przycinamy początek napisu
            if t0 < end < t1:
                t0 = end

            # jeżeli po przycięciach długość <= 0, to traktujemy jako usunięty
            if t1 <= t0:
                remove = True
                break

        if remove:
            continue

        # teraz obliczamy przesunięcie dla przyciętego punktu startu
        shift = total_cut_before(t0)
        new_t0 = t0 - shift
        new_t1 = t1 - shift

        # zapisujemy wynik
        if source_fmt == 'srt':
            sub.start, sub.end = new_t0, new_t1
            new_subs.append(sub)
        else:
            sub['start'] = format_timestamp(new_t0)
            sub['end']   = format_timestamp(new_t1)
            new_subs.append(sub)

    return new_subs

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
    parser.add_argument('--cuts', '-c',
                    help='(opcjonalnie) ścieżka do pliku txt z zakresami cięć')


    args = parser.parse_args()
    subs, source_fmt = read_subtitles(args.input)
    if args.shift:
        subs = shift_timecodes(subs, detect_format(args.input), args.shift)
    if args.cuts:
        cut_ranges = read_cut_ranges(args.cuts)
        subs = apply_cut_ranges(subs, source_fmt, cut_ranges)

    print(f"Wykryty format źródłowy: {source_fmt}")
    save_subtitles(subs, args.to, args.output)
    print(f"Zapisano plik: {args.output} jako {args.to.upper()}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nBłąd: {e}")
        input("\nNaciśnij Enter, aby zamknąć...")
