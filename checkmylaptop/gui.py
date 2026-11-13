"""Desktop interface. Collection runs off the UI thread."""

import json
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox, ttk

from .collect import scan
from .demo import snapshot
from .report import build_report, render_text


class Application:
    def __init__(self, root: tk.Tk, demo: bool):
        self.root = root
        self.demo = demo
        self.report = None
        self.messages = Queue()
        root.title("CheckMyLaptop" + (" · Demo" if demo else ""))
        root.geometry("850x660")
        root.minsize(560, 430)
        root.configure(bg="#eef2f6")

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Shell.TFrame", background="#eef2f6")
        style.configure("Title.TLabel", background="#eef2f6", foreground="#132239",
                        font=("Segoe UI", 25, "bold"))
        style.configure("Body.TLabel", background="#eef2f6", foreground="#34475a",
                        font=("Segoe UI", 10))
        style.configure("Scan.TButton", padding=(14, 9), background="#176245",
                        foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Scan.TButton", background=[("active", "#124c37"), ("disabled", "#45596b")])
        style.map("Scan.TButton", foreground=[("disabled", "#ffffff")])

        shell = ttk.Frame(root, padding=22, style="Shell.TFrame")
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="CheckMyLaptop", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="One-click Windows laptop diagnostics",
                  style="Body.TLabel").pack(anchor="w", pady=(2, 14))

        actions = ttk.Frame(shell, style="Shell.TFrame")
        actions.pack(fill="x", pady=(0, 10))
        self.scan_button = ttk.Button(actions, text="Run demo scan" if demo else "Scan laptop",
                                      command=self.start, style="Scan.TButton")
        self.scan_button.pack(side="left")
        self.export_button = ttk.Button(actions, text="Save report", command=self.export,
                                        state="disabled", padding=(10, 8))
        self.export_button.pack(side="left", padx=8)

        self.status = tk.StringVar(value="Simulated data" if demo else "Ready to scan · runs locally")
        ttk.Label(shell, textvariable=self.status, style="Body.TLabel").pack(anchor="w", pady=(0, 8))
        self.progress = ttk.Progressbar(shell, mode="indeterminate")

        panel = ttk.Frame(shell)
        panel.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(panel)
        scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(panel, wrap="word", padx=14, pady=12, bd=0,
                            background="white", foreground="#132239",
                            font=("Segoe UI", 11), yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.text.yview)
        self.text.tag_configure("high", foreground="#a72321", font=("Segoe UI", 11, "bold"))
        self.text.tag_configure("attention", foreground="#864b00", font=("Segoe UI", 11, "bold"))
        self.text.tag_configure("info", foreground="#22507a", font=("Segoe UI", 11, "bold"))
        self.show("Run a scan to see prioritized findings, recommended steps and scan coverage.")
        self.scan_button.focus_set()

    def show(self, content):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for line in content.splitlines():
            tag = next((level for level in ("high", "attention", "info")
                        if line.startswith(f"[{level.upper()}]")), "")
            self.text.insert("end", line + "\n", tag)
        self.text.configure(state="disabled")

    def start(self):
        self.scan_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.status.set("Collecting diagnostic data…")
        self.progress.pack(fill="x", side="bottom", pady=(8, 0))
        self.progress.start(14)
        Thread(target=self.run_scan, daemon=True).start()
        self.root.after(75, self.poll)

    def run_scan(self):
        try:
            data = snapshot() if self.demo else scan(
                progress=lambda label: self.messages.put(("progress", label)),
            )
            self.messages.put(("report", build_report(data, demo=self.demo)))
        except Exception:
            self.messages.put(("error", "The scan could not complete. Try again or report the issue."))

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "progress":
                    self.status.set(f"Waiting for {value.lower()}…")
                    continue
                self.progress.stop()
                self.progress.pack_forget()
                self.scan_button.configure(state="normal")
                if kind == "report":
                    self.report = value
                    self.show(render_text(value))
                    self.status.set("Demo complete" if self.demo else "Scan complete · review scan coverage")
                    self.export_button.configure(state="normal")
                else:
                    self.status.set("Scan failed")
                    self.show(value)
                return
        except Empty:
            self.root.after(75, self.poll)

    def export(self):
        destination = filedialog.asksaveasfilename(
            title="Save diagnostic report", defaultextension=".txt",
            initialfile="checkmylaptop-report.txt",
            filetypes=[("Text report", "*.txt"), ("JSON report", "*.json")],
        )
        if not destination:
            return
        path = Path(destination)
        content = (json.dumps(self.report, ensure_ascii=False, indent=2) + "\n"
                   if path.suffix.lower() == ".json" else render_text(self.report))
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save the report", str(exc))
        else:
            self.status.set("Report saved")


def run(*, demo=False):
    root = tk.Tk()
    Application(root, demo)
    root.mainloop()
