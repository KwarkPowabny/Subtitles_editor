import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from subtitles_converter import read_subtitles, detect_format, shift_timecodes, save_subtitles, format_timestamp

class SubtitleConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Subtitle Converter")
        self.root.geometry("450x300")
        self.file_path = ""
        self.output_path = ""
        self.output_format = tk.StringVar(value="srt")
        self.shift_seconds = tk.DoubleVar(value=0.0)
        self.use_external_timing = tk.BooleanVar(value=False)
        self.external_timing_path = ""


        self.create_widgets()

    def create_widgets(self):
        tk.Button(self.root, text="Wybierz plik wejściowy", command=self.choose_input).pack(pady=10)

        self.input_label = tk.Label(self.root, text="Brak pliku wejściowego")
        self.input_label.pack()

        tk.Label(self.root, text="Format wyjściowy:").pack(pady=5)
        ttk.Combobox(self.root, textvariable=self.output_format, values=["srt", "vtt", "txt"]).pack()

        tk.Label(self.root, text="Przesunięcie czasowe (s):").pack(pady=5)
        tk.Entry(self.root, textvariable=self.shift_seconds).pack()

        tk.Button(self.root, text="Zapisz jako...", command=self.choose_output).pack(pady=10)

        self.output_label = tk.Label(self.root, text="Brak pliku wyjściowego")
        self.output_label.pack()

        tk.Button(self.root, text="Konwertuj", command=self.convert).pack(pady=10)
        tk.Checkbutton(self.root, text="Użyj timecodów z innego pliku", variable=self.use_external_timing,
               command=self.toggle_timing_input).pack(pady=5)
        self.timing_button = tk.Button(self.root, text="Wybierz plik z timecodami", command=self.choose_timing_file, state=tk.DISABLED)
        self.timing_button.pack()

    def toggle_timing_input(self):
        state = tk.NORMAL if self.use_external_timing.get() else tk.DISABLED
        self.timing_button.config(state=state)

    def choose_timing_file(self):
        path = filedialog.askopenfilename(filetypes=[("Napisy", "*.srt *.vtt")])
        if path:
            self.external_timing_path = path
            self.timing_button.config(text=f"Z timecodów: {os.path.basename(path)}")

    def choose_input(self):
        path = filedialog.askopenfilename(filetypes=[("Napisy", "*.srt *.vtt *.txt")])
        if path:
            self.file_path = path
            self.input_label.config(text=f"Wejście: {path}")

    def choose_output(self):
        path = filedialog.asksaveasfilename(defaultextension=f".{self.output_format.get()}",
                                             filetypes=[("Napisy", "*.srt *.vtt *.txt")])
        if path:
            self.output_path = path
            self.output_label.config(text=f"Wyjście: {path}")

    def convert(self):
        if not self.file_path or not self.output_path:
            messagebox.showerror("Błąd", "Wybierz plik wejściowy i wyjściowy.")
            return
        try:
            if self.use_external_timing.get():
                timing_subs, timing_fmt = read_subtitles(self.external_timing_path)
                text_subs, text_fmt = read_subtitles(self.file_path)

                # Łączenie: tekst z `text_subs`, timecody z `timing_subs`
                if len(timing_subs) != len(text_subs):
                    messagebox.showerror("Błąd", "Liczba napisów nie zgadza się między plikami.")
                    return

                merged = []
                for i in range(len(timing_subs)):
                    if isinstance(timing_subs[i], dict):
                        start = timing_subs[i]['start']
                        end = timing_subs[i]['end']
                    else:
                        start = format_timestamp(timing_subs[i].start)
                        end = format_timestamp(timing_subs[i].end)

                    text = text_subs[i].content if hasattr(text_subs[i], 'content') else text_subs[i]['text']
                    merged.append({'start': start, 'end': end, 'text': text})

                save_subtitles(merged, self.output_format.get(), self.output_path)
            else:
                subs, fmt = read_subtitles(self.file_path)
                if self.shift_seconds.get():
                    subs = shift_timecodes(subs, fmt, self.shift_seconds.get())
                save_subtitles(subs, self.output_format.get(), self.output_path)

            messagebox.showinfo("Sukces", f"Zapisano: {self.output_path}")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = SubtitleConverterApp(root)
    root.mainloop()
