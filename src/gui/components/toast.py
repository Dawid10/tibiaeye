"""Big short-lived message over the game (e.g. "CAVEBOT ON"), like the Real-tibia-heal bot."""
import tkinter as tk

from ...core.constants import TOAST_DURATION_MS


def show_toast(root, text, color):
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.attributes("-alpha", 0.85)
    toast.configure(bg="#1e1e1e")
    tk.Label(toast, text=text, font=("Menlo", 36, "bold"), fg=color, bg="#1e1e1e", padx=40, pady=20).pack()

    toast.update_idletasks()
    x = (toast.winfo_screenwidth() - toast.winfo_reqwidth()) // 2
    y = (toast.winfo_screenheight() - toast.winfo_reqheight()) // 3
    toast.geometry(f"+{x}+{y}")
    toast.after(TOAST_DURATION_MS, toast.destroy)
