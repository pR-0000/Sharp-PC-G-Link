"""Source launcher setup using only the Python standard library."""
import importlib
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading


def hidden_process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def runtime_ready():
    try:
        serial = importlib.import_module("serial")
        importlib.import_module("tkinter")
        return sys.version_info >= (3, 10) and getattr(serial, "__version__", "") == "3.5"
    except ImportError:
        return False


def local_python(folder):
    return folder / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def launch_source(python, launcher, arguments):
    windowed = python.with_name("pythonw.exe") if os.name == "nt" else python
    subprocess.Popen([str(windowed if windowed.exists() else python), str(launcher), *arguments],
                     cwd=launcher.parent, **hidden_process_options())


def ensure_runtime(launcher, language="fr"):
    """Return True in the ready interpreter; otherwise show setup or relaunch."""
    if getattr(sys, "frozen", False) or runtime_ready():
        return True
    import tkinter as tk
    from tkinter import ttk
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10+ avec Tkinter requis / Python 3.10+ with Tkinter required.")
    python = local_python(launcher.parent)
    if python.exists():
        try:
            result = subprocess.run([str(python), "-c",
                "import sys, tkinter, serial; assert sys.version_info >= (3,10); assert serial.__version__ == '3.5'"],
                capture_output=True, timeout=15, **hidden_process_options())
            if result.returncode == 0:
                launch_source(python, launcher, sys.argv[1:])
                return False
        except (OSError, subprocess.TimeoutExpired):
            pass
    root = tk.Tk()
    root.title("Sharp PC-G Link — installation / setup")
    root.geometry("710x410"); root.minsize(640, 360)
    frame = ttk.Frame(root, padding=20); frame.pack(fill="both", expand=True)
    language_var = tk.StringVar(value="English" if language == "en" else "Français")
    row = ttk.Frame(frame); row.pack(fill="x")
    heading = ttk.Label(row, font=("Segoe UI", 15, "bold")); heading.pack(side="left")
    languages = ttk.Combobox(row, textvariable=language_var, values=("Français", "English"), state="readonly", width=11)
    languages.pack(side="right")
    description = ttk.Label(frame, wraplength=650, justify="left"); description.pack(fill="x", pady=16)
    progress = ttk.Progressbar(frame, mode="indeterminate"); progress.pack(fill="x")
    log = tk.Text(frame, font=("Consolas", 9), height=7, state="disabled", wrap="word")
    log.pack(fill="both", expand=True, pady=12)
    row = ttk.Frame(frame); row.pack(fill="x")
    events = queue.Queue(); running = False
    texts = {
        "fr": ("Préparer l’application", "Cette version source nécessite pyserial 3.5. La préparation crée un environnement Python local dans .venv et télécharge cette dépendance. Une connexion Internet est nécessaire une seule fois. Vos réglages sont conservés.", "Préparer et démarrer", "Fermer"),
        "en": ("Set up the application", "This source version requires pyserial 3.5. Setup creates a local Python environment in .venv and downloads this dependency. An Internet connection is needed once. Your preferences are preserved.", "Set up and start", "Close"),
    }
    def translate(_event=None):
        lang = "en" if language_var.get() == "English" else "fr"
        title, detail, start, close = texts[lang]
        heading.configure(text=title); description.configure(text=detail)
        prepare.configure(text=start); dismiss.configure(text=close)
    def append(value):
        log.configure(state="normal"); log.insert("end", value + "\n"); log.see("end"); log.configure(state="disabled")
    def start():
        nonlocal running
        if running:return
        running = True; prepare.configure(state="disabled"); dismiss.configure(state="disabled")
        languages.configure(state="disabled"); progress.start()
        chosen_language = "en" if language_var.get() == "English" else "fr"
        def worker():
            try:
                if not python.exists():
                    events.put(("log", "Création de .venv / Creating .venv…"))
                    result = subprocess.run([sys.executable, "-m", "venv", str(launcher.parent / ".venv")],
                        capture_output=True, text=True, errors="replace", timeout=180, **hidden_process_options())
                    if result.returncode:raise RuntimeError(result.stdout + result.stderr)
                events.put(("log", "Installation de pyserial 3.5 / Installing pyserial 3.5…"))
                result = subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(launcher.parent / "requirements.txt")],
                    capture_output=True, text=True, errors="replace", timeout=300, **hidden_process_options())
                events.put(("log", result.stdout + result.stderr))
                if result.returncode:raise RuntimeError("Installation impossible / Setup failed. Vérifier Internet / Check your Internet connection.")
                result = subprocess.run([str(python), "-c", "import sys, tkinter, serial; assert sys.version_info >= (3,10); assert serial.__version__ == '3.5'"],
                    capture_output=True, text=True, timeout=15, **hidden_process_options())
                if result.returncode:raise RuntimeError(result.stderr)
                from .config import config_path, load_settings, save_settings
                prefs = load_settings(config_path()); prefs["language"] = chosen_language; save_settings(config_path(), prefs)
                events.put(("done", None))
            except Exception as error:events.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()
    def poll():
        nonlocal running
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "log":append(value)
            elif kind == "done":
                launch_source(python, launcher, sys.argv[1:]); root.destroy(); return
            else:
                append(value); progress.stop(); running = False
                prepare.configure(state="normal"); dismiss.configure(state="normal"); languages.configure(state="readonly")
        root.after(100, poll)
    prepare = ttk.Button(row, command=start); prepare.pack(side="right")
    dismiss = ttk.Button(row, command=root.destroy); dismiss.pack(side="right", padx=8)
    languages.bind("<<ComboboxSelected>>", translate)
    root.protocol("WM_DELETE_WINDOW", lambda: None if running else root.destroy())
    translate(); root.after(100, poll); root.mainloop()
    return False


def show_startup_error(detail):
    text = "Sharp PC-G Link n’a pas pu démarrer / could not start.\nPython 3.10+ avec/with Tkinter requis/required.\n\n" + detail
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Sharp PC-G Link", text, parent=root); root.destroy()
    except Exception:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "Sharp PC-G Link", 0x10)
        else:print(text, file=sys.stderr)
