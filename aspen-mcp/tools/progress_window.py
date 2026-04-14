"""Standalone progress window for GA optimization.

Launched as a subprocess. Reads progress from a JSON file periodically.
Usage: python progress_window.py <state_file>

State file format (JSON):
  {"gen": 0, "n_gen": 30, "eval_count": 5, "total": 155,
   "status": "...", "best_objs": [1.23, 4.56], "obj_names": ["A", "B"],
   "done": false}
"""

import json
import sys
import tkinter as tk
from tkinter import ttk


class ProgressApp:
    def __init__(self, state_file: str):
        self._state_file = state_file
        self._root = tk.Tk()
        self._root.title("Optimization Progress")
        self._root.resizable(False, False)
        self._root.attributes("-topmost", True)
        self._root.protocol("WM_DELETE_WINDOW", lambda: None)

        f = ttk.Frame(self._root, padding=16)
        f.pack(fill="both", expand=True)

        self._gen_var = tk.StringVar(value="Initializing...")
        ttk.Label(f, textvariable=self._gen_var, font=("Consolas", 12, "bold")).pack(anchor="w")

        self._bar = ttk.Progressbar(f, length=400, maximum=1)
        self._bar.pack(pady=(8, 4), fill="x")

        self._eval_var = tk.StringVar(value="Waiting...")
        ttk.Label(f, textvariable=self._eval_var, font=("Consolas", 10)).pack(anchor="w")

        ttk.Separator(f).pack(fill="x", pady=(10, 6))
        ttk.Label(f, text="Current Best:", font=("Consolas", 10, "bold")).pack(anchor="w")
        self._obj_frame = f
        self._obj_vars: list[tk.StringVar] = []
        self._obj_labels_created = False

        ttk.Separator(f).pack(fill="x", pady=(10, 6))
        self._status_var = tk.StringVar(value="Starting...")
        ttk.Label(f, textvariable=self._status_var, font=("Consolas", 9)).pack(anchor="w")

        self._poll()
        self._root.mainloop()

    def _poll(self):
        try:
            with open(self._state_file, "r", encoding="utf-8") as fp:
                state = json.load(fp)

            n_gen = state.get("n_gen", 1)
            total = state.get("total", 1)
            gen = state.get("gen", 0)
            count = state.get("eval_count", 0)
            status = state.get("status", "")
            best = state.get("best_objs")
            obj_names = state.get("obj_names", [])
            done = state.get("done", False)

            self._bar["maximum"] = total
            self._bar["value"] = count
            self._gen_var.set(f"Generation {gen} / {n_gen}")
            self._eval_var.set(f"{count} / {total} evaluations")
            self._status_var.set(status)

            # Create objective labels on first valid read
            if obj_names and not self._obj_labels_created:
                for name in obj_names:
                    sv = tk.StringVar(value=f"  {name}: —")
                    ttk.Label(self._obj_frame, textvariable=sv,
                              font=("Consolas", 10)).pack(anchor="w", before=self._obj_frame.winfo_children()[-2])
                    self._obj_vars.append(sv)
                self._obj_labels_created = True

            if best and self._obj_vars:
                for sv, name, val in zip(self._obj_vars, obj_names, best):
                    sv.set(f"  {name}: {val:.6g}")

            if done:
                self._status_var.set("Optimization complete!")
                self._root.after(2000, self._root.destroy)
                return

        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

        self._root.after(500, self._poll)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python progress_window.py <state_file>")
        sys.exit(1)
    ProgressApp(sys.argv[1])
