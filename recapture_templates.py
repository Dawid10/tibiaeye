"""
Template Recapture Tool - Capture card edition
===============================================
Interactive GUI to recapture template icons from a capture card screenshot.

Controls:
  - Scroll wheel: Zoom in/out (centered on mouse)
  - Space + left-click drag (or right-click drag): Pan the image
  - Left-click drag: Select a region to crop
  - After selecting, the crop preview appears on the right panel
  - Choose a template target from the dropdown and click "Save"
  - Or use "Add to Pending" + "Save All Pending" for batch saves
  - Use "Browse Custom..." to pick any .png file as the save target

Usage:
  poetry run python recapture_templates.py [screenshot_path]

  If no path given, defaults to device_with_swamptrolls.png
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import cv2
import numpy as np

# All template targets organized by category
_TEMPLATE_TARGETS = {
    "skills": {
        "icons/skills": "src/repositories/skills/images/icons/skills.png",
        "digits/0": "src/repositories/skills/images/digits/0.png",
        "digits/1": "src/repositories/skills/images/digits/1.png",
        "digits/2": "src/repositories/skills/images/digits/2.png",
        "digits/3": "src/repositories/skills/images/digits/3.png",
        "digits/4": "src/repositories/skills/images/digits/4.png",
        "digits/5": "src/repositories/skills/images/digits/5.png",
        "digits/6": "src/repositories/skills/images/digits/6.png",
        "digits/7": "src/repositories/skills/images/digits/7.png",
        "digits/8": "src/repositories/skills/images/digits/8.png",
        "digits/9": "src/repositories/skills/images/digits/9.png",
    },
    "statusBar": {
        "heart": "src/repositories/statusbar/images/heart.png",
        "mana": "src/repositories/statusbar/images/mana.png",
    },
    "battleList": {
        "icons/battleList": "src/repositories/battlelist/images/icons/battleList.png",
        "containers/bottomBar": "src/repositories/battlelist/images/containers/bottomBar.png",
    },
    "gameWindow": {
        "arrows/leftGameWindow00": "src/repositories/gamewindow/images/arrows/leftGameWindow00.png",
        "arrows/leftGameWindow01": "src/repositories/gamewindow/images/arrows/leftGameWindow01.png",
        "arrows/leftGameWindow10": "src/repositories/gamewindow/images/arrows/leftGameWindow10.png",
        "arrows/leftGameWindow11": "src/repositories/gamewindow/images/arrows/leftGameWindow11.png",
        "arrows/rightGameWindow00": "src/repositories/gamewindow/images/arrows/rightGameWindow00.png",
        "arrows/rightGameWindow01": "src/repositories/gamewindow/images/arrows/rightGameWindow01.png",
        "arrows/rightGameWindow10": "src/repositories/gamewindow/images/arrows/rightGameWindow10.png",
        "arrows/rightGameWindow11": "src/repositories/gamewindow/images/arrows/rightGameWindow11.png",
    },
    "actionBar": {
        "arrows/left": "src/repositories/actionBar/images/arrows/left.png",
        "arrows/right": "src/repositories/actionBar/images/arrows/right.png",
        "digits/0": "src/repositories/actionBar/images/digits/0.png",
        "digits/1": "src/repositories/actionBar/images/digits/1.png",
        "digits/2": "src/repositories/actionBar/images/digits/2.png",
        "digits/3": "src/repositories/actionBar/images/digits/3.png",
        "digits/4": "src/repositories/actionBar/images/digits/4.png",
        "digits/5": "src/repositories/actionBar/images/digits/5.png",
        "digits/6": "src/repositories/actionBar/images/digits/6.png",
        "digits/7": "src/repositories/actionBar/images/digits/7.png",
        "digits/8": "src/repositories/actionBar/images/digits/8.png",
        "digits/9": "src/repositories/actionBar/images/digits/9.png",
        "cooldowns/attack": "src/repositories/actionBar/images/cooldowns/attack.png",
        "cooldowns/healing": "src/repositories/actionBar/images/cooldowns/healing.png",
        "cooldowns/support": "src/repositories/actionBar/images/cooldowns/support.png",
        "cooldowns/exanaKor": "src/repositories/actionBar/images/cooldowns/exanaKor.png",
        "cooldowns/exanaPox": "src/repositories/actionBar/images/cooldowns/exanaPox.png",
        "cooldowns/exaniHur": "src/repositories/actionBar/images/cooldowns/exaniHur.png",
        "cooldowns/exaniTera": "src/repositories/actionBar/images/cooldowns/exaniTera.png",
        "cooldowns/exetaAmpRes": "src/repositories/actionBar/images/cooldowns/exetaAmpRes.png",
        "cooldowns/exetaRes": "src/repositories/actionBar/images/cooldowns/exetaRes.png",
        "cooldowns/exivaMoeRes": "src/repositories/actionBar/images/cooldowns/exivaMoeRes.png",
        "cooldowns/exori": "src/repositories/actionBar/images/cooldowns/exori.png",
        "cooldowns/exoriGran": "src/repositories/actionBar/images/cooldowns/exoriGran.png",
        "cooldowns/exoriGranIco": "src/repositories/actionBar/images/cooldowns/exoriGranIco.png",
        "cooldowns/exoriHur": "src/repositories/actionBar/images/cooldowns/exoriHur.png",
        "cooldowns/exoriIco": "src/repositories/actionBar/images/cooldowns/exoriIco.png",
        "cooldowns/exoriMas": "src/repositories/actionBar/images/cooldowns/exoriMas.png",
        "cooldowns/exoriMin": "src/repositories/actionBar/images/cooldowns/exoriMin.png",
        "cooldowns/exuraGranIco": "src/repositories/actionBar/images/cooldowns/exuraGranIco.png",
        "cooldowns/exuraIco": "src/repositories/actionBar/images/cooldowns/exuraIco.png",
        "cooldowns/exuraMedIco": "src/repositories/actionBar/images/cooldowns/exuraMedIco.png",
        "cooldowns/utamoTempo": "src/repositories/actionBar/images/cooldowns/utamoTempo.png",
        "cooldowns/utaniHur": "src/repositories/actionBar/images/cooldowns/utaniHur.png",
        "cooldowns/utaniTempoHur": "src/repositories/actionBar/images/cooldowns/utaniTempoHur.png",
        "cooldowns/utevoGranLux": "src/repositories/actionBar/images/cooldowns/utevoGranLux.png",
        "cooldowns/utevoGranResEq": "src/repositories/actionBar/images/cooldowns/utevoGranResEq.png",
        "cooldowns/utevoLux": "src/repositories/actionBar/images/cooldowns/utevoLux.png",
        "cooldowns/utitoTempo": "src/repositories/actionBar/images/cooldowns/utitoTempo.png",
        "cooldowns/utoriKor": "src/repositories/actionBar/images/cooldowns/utoriKor.png",
        "cooldowns/utura": "src/repositories/actionBar/images/cooldowns/utura.png",
        "cooldowns/uturaGran": "src/repositories/actionBar/images/cooldowns/uturaGran.png",
    },
    "radar": {
        "buttons/radarTools": "src/repositories/radar/images/buttons/radarTools.png",
        "floorLevels/0": "src/repositories/radar/images/floorLevels/0.png",
        "floorLevels/1": "src/repositories/radar/images/floorLevels/1.png",
        "floorLevels/2": "src/repositories/radar/images/floorLevels/2.png",
        "floorLevels/3": "src/repositories/radar/images/floorLevels/3.png",
        "floorLevels/4": "src/repositories/radar/images/floorLevels/4.png",
        "floorLevels/5": "src/repositories/radar/images/floorLevels/5.png",
        "floorLevels/6": "src/repositories/radar/images/floorLevels/6.png",
        "floorLevels/7": "src/repositories/radar/images/floorLevels/7.png",
        "floorLevels/8": "src/repositories/radar/images/floorLevels/8.png",
        "floorLevels/9": "src/repositories/radar/images/floorLevels/9.png",
        "floorLevels/10": "src/repositories/radar/images/floorLevels/10.png",
        "floorLevels/11": "src/repositories/radar/images/floorLevels/11.png",
        "floorLevels/12": "src/repositories/radar/images/floorLevels/12.png",
        "floorLevels/13": "src/repositories/radar/images/floorLevels/13.png",
        "floorLevels/14": "src/repositories/radar/images/floorLevels/14.png",
        "floorLevels/15": "src/repositories/radar/images/floorLevels/15.png",
    },
}


def _redirect_for_win32(targets):
    """On Windows, redirect all paths to save into images/win32/ subdirectory."""
    if sys.platform != 'win32':
        return targets
    redirected = {}
    for category, templates in targets.items():
        redirected[category] = {}
        for name, path in templates.items():
            redirected[category][name] = path.replace('/images/', '/images/win32/')
    return redirected


TEMPLATE_TARGETS = _redirect_for_win32(_TEMPLATE_TARGETS)


class TemplateCaptureApp:
    def __init__(self, root, image_path):
        self.root = root
        self.root.title(f"Template Recapture Tool - {os.path.basename(image_path)}")
        self.root.geometry("1500x950")
        self.root.configure(bg="#2b2b2b")

        # Style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#e0e0e0")
        style.configure("TLabelframe", background="#2b2b2b", foreground="#e0e0e0")
        style.configure("TLabelframe.Label", background="#2b2b2b", foreground="#e0e0e0")
        style.configure("TButton", background="#404040", foreground="#e0e0e0")
        style.configure("Save.TButton", background="#2d5a2d", foreground="#e0e0e0")
        style.configure("Status.TLabel", background="#1a1a1a", foreground="#00ff00",
                         font=("Consolas", 10))

        # Load source image
        self.cv_image = cv2.imread(image_path)
        if self.cv_image is None:
            messagebox.showerror("Error", f"Could not load: {image_path}")
            sys.exit(1)
        self.cv_image_rgb = cv2.cvtColor(self.cv_image, cv2.COLOR_BGR2RGB)
        self.pil_image = Image.fromarray(self.cv_image_rgb)
        self.img_w, self.img_h = self.pil_image.size

        # View state
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Selection state
        self.selecting = False
        self.sel_start_x = 0
        self.sel_start_y = 0
        self.current_crop = None
        self.current_crop_coords = None

        # Pan state
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.space_held = False

        # Custom target path (for "Browse Custom..." replace)
        self.custom_target_path = None

        # Pending saves: [(path, crop_rgb, label), ...]
        self.pending_saves = []

        self._build_ui()
        self.root.after(100, self._fit_to_canvas)

    def _build_ui(self):
        # Top bar with source info
        top_bar = ttk.Frame(self.root)
        top_bar.pack(fill=tk.X, padx=5, pady=(5, 0))

        ttk.Button(top_bar, text="Load Image...", command=self._load_new_image).pack(side=tk.LEFT, padx=5)
        self.source_label = ttk.Label(top_bar, text=f"Source: {self.img_w}x{self.img_h}")
        self.source_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(top_bar, text="Fit View", command=self._fit_to_canvas).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="1:1", command=self._zoom_1to1).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_bar, text="4x", command=lambda: self._set_zoom(4)).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_bar, text="8x", command=lambda: self._set_zoom(8)).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_bar, text="16x", command=lambda: self._set_zoom(16)).pack(side=tk.LEFT, padx=2)

        # Main layout
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: canvas
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#1a1a1a", cursor="crosshair",
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.coord_label = ttk.Label(canvas_frame, text="Move mouse over image...",
                                     style="Status.TLabel")
        self.coord_label.pack(fill=tk.X)

        # Right: controls (fixed width)
        ctrl_outer = ttk.Frame(main_frame, width=400)
        ctrl_outer.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ctrl_outer.pack_propagate(False)

        ctrl_canvas = tk.Canvas(ctrl_outer, bg="#2b2b2b", highlightthickness=0)
        ctrl_scrollbar = ttk.Scrollbar(ctrl_outer, orient=tk.VERTICAL, command=ctrl_canvas.yview)
        ctrl_frame = ttk.Frame(ctrl_canvas)

        ctrl_frame.bind("<Configure>", lambda e: ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all")))
        ctrl_canvas.create_window((0, 0), window=ctrl_frame, anchor="nw", width=380)
        ctrl_canvas.configure(yscrollcommand=ctrl_scrollbar.set)
        ctrl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ctrl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Category / Target ---
        target_frame = ttk.LabelFrame(ctrl_frame, text="Template Target")
        target_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(target_frame, text="Category:").pack(anchor=tk.W, padx=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(target_frame, textvariable=self.category_var,
                                           values=list(TEMPLATE_TARGETS.keys()), state="readonly",
                                           width=35)
        self.category_combo.pack(fill=tk.X, padx=5, pady=2)
        self.category_combo.bind("<<ComboboxSelected>>", self._on_category_change)

        ttk.Label(target_frame, text="Template:").pack(anchor=tk.W, padx=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(target_frame, textvariable=self.template_var,
                                           state="readonly", width=35)
        self.template_combo.pack(fill=tk.X, padx=5, pady=2)
        self.template_combo.bind("<<ComboboxSelected>>", self._on_template_change)

        ttk.Separator(target_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(target_frame, text="Or replace any existing image:").pack(anchor=tk.W, padx=5)
        custom_row = ttk.Frame(target_frame)
        custom_row.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(custom_row, text="Browse Custom...",
                   command=self._browse_custom_target).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(custom_row, text="Clear", command=self._clear_custom_target).pack(side=tk.LEFT)
        self.custom_target_label = ttk.Label(target_frame, text="No custom target",
                                              foreground="#888888", wraplength=350)
        self.custom_target_label.pack(anchor=tk.W, padx=5, pady=(0, 5))

        # --- Selection info ---
        sel_frame = ttk.LabelFrame(ctrl_frame, text="Current Selection")
        sel_frame.pack(fill=tk.X, padx=5, pady=5)

        self.sel_info_label = ttk.Label(sel_frame, text="Drag on the image to select a region",
                                        wraplength=350)
        self.sel_info_label.pack(anchor=tk.W, padx=5, pady=2)

        ttk.Label(sel_frame, text="Your crop (zoomed preview):").pack(anchor=tk.W, padx=5)
        self.preview_canvas = tk.Canvas(sel_frame, width=370, height=160, bg="#111111",
                                        highlightthickness=1, highlightbackground="#555")
        self.preview_canvas.pack(padx=5, pady=3)

        ttk.Label(sel_frame, text="Existing template (for comparison):").pack(anchor=tk.W, padx=5)
        self.existing_canvas = tk.Canvas(sel_frame, width=370, height=100, bg="#111111",
                                         highlightthickness=1, highlightbackground="#555")
        self.existing_canvas.pack(padx=5, pady=3)
        self.existing_info_label = ttk.Label(sel_frame, text="")
        self.existing_info_label.pack(anchor=tk.W, padx=5)

        # --- Buttons ---
        btn_frame = ttk.LabelFrame(ctrl_frame, text="Actions")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Add to Pending List",
                   command=self._add_to_pending).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(btn_frame, text="Save Current Template Now",
                   command=self._save_current, style="Save.TButton").pack(fill=tk.X, padx=5, pady=2)

        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Save All Pending",
                   command=self._save_all_pending, style="Save.TButton").pack(fill=tk.X, padx=5, pady=2)

        # --- Pending list ---
        pending_frame = ttk.LabelFrame(ctrl_frame, text="Pending Saves")
        pending_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.pending_listbox = tk.Listbox(pending_frame, height=12, bg="#1a1a1a",
                                          fg="#00ff00", selectbackground="#444",
                                          font=("Consolas", 9))
        self.pending_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        pending_btn_frame = ttk.Frame(pending_frame)
        pending_btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(pending_btn_frame, text="Remove Selected",
                   command=self._remove_pending).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(pending_btn_frame, text="Clear All",
                   command=self._clear_pending).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        # Bind canvas events
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<Button-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Configure>", lambda e: self._render())

        # Canvas grabs focus on mouse enter so Space works for panning
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

        # Space key for pan mode
        self.canvas.bind("<KeyPress-space>", self._on_space_press)
        self.canvas.bind("<KeyRelease-space>", self._on_space_release)

        # Set default category
        if TEMPLATE_TARGETS:
            self.category_combo.current(0)
            self._on_category_change(None)

    # --- Image loading ---
    def _load_new_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
            initialdir=os.getcwd()
        )
        if path:
            img = cv2.imread(path)
            if img is not None:
                self.cv_image = img
                self.cv_image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.pil_image = Image.fromarray(self.cv_image_rgb)
                self.img_w, self.img_h = self.pil_image.size
                self.source_label.config(text=f"Source: {self.img_w}x{self.img_h} - {os.path.basename(path)}")
                self.root.title(f"Template Recapture Tool - {os.path.basename(path)}")
                self.current_crop = None
                self.current_crop_coords = None
                self._fit_to_canvas()

    # --- Category/template ---
    def _on_category_change(self, event):
        cat = self.category_var.get()
        if cat in TEMPLATE_TARGETS:
            templates = list(TEMPLATE_TARGETS[cat].keys())
            self.template_combo["values"] = templates
            if templates:
                self.template_combo.current(0)
            self._show_existing_template()

    def _on_template_change(self, event):
        self.custom_target_path = None
        self.custom_target_label.config(text="No custom target", foreground="#888888")
        self._show_existing_template()

    def _browse_custom_target(self):
        path = filedialog.askopenfilename(
            title="Choose an existing image to replace",
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
            initialdir=os.path.join(os.getcwd(), "src", "repositories")
        )
        if path:
            # Make relative to cwd if possible
            try:
                rel = os.path.relpath(path, os.getcwd())
                path = rel.replace("\\", "/")
            except ValueError:
                pass
            self.custom_target_path = path
            self.custom_target_label.config(text=path, foreground="#00ccff")
            self._show_existing_template()

    def _clear_custom_target(self):
        self.custom_target_path = None
        self.custom_target_label.config(text="No custom target", foreground="#888888")
        self._show_existing_template()

    def _get_target_path(self):
        if self.custom_target_path:
            return self.custom_target_path
        cat = self.category_var.get()
        tmpl = self.template_var.get()
        if cat and tmpl and cat in TEMPLATE_TARGETS and tmpl in TEMPLATE_TARGETS[cat]:
            return TEMPLATE_TARGETS[cat][tmpl]
        return None

    def _show_existing_template(self):
        self.existing_canvas.delete("all")
        path = self._get_target_path()
        if path and os.path.exists(path):
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                if len(img.shape) == 2:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                elif img.shape[2] == 4:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                else:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w = img_rgb.shape[:2]
                scale = min(8, 370 // max(w, 1), 100 // max(h, 1))
                scale = max(scale, 1)
                pil_img = Image.fromarray(img_rgb).resize(
                    (w * scale, h * scale), Image.NEAREST)
                self._existing_tk = ImageTk.PhotoImage(pil_img)
                self.existing_canvas.create_image(5, 5, anchor=tk.NW, image=self._existing_tk)
                self.existing_info_label.config(text=f"Existing: {w}x{h}px (shown {scale}x)")
        else:
            self.existing_info_label.config(text="No existing template found")

    # --- Coordinate conversion ---
    def _screen_to_image(self, sx, sy):
        ix = (sx - self.offset_x) / self.zoom
        iy = (sy - self.offset_y) / self.zoom
        return ix, iy

    def _image_to_screen(self, ix, iy):
        sx = ix * self.zoom + self.offset_x
        sy = iy * self.zoom + self.offset_y
        return sx, sy

    # --- Zoom helpers ---
    def _fit_to_canvas(self):
        self.root.update_idletasks()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        zx = cw / self.img_w
        zy = ch / self.img_h
        self.zoom = min(zx, zy)
        self.offset_x = (cw - self.img_w * self.zoom) / 2
        self.offset_y = (ch - self.img_h * self.zoom) / 2
        self._render()

    def _zoom_1to1(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.zoom = 1.0
        self.offset_x = (cw - self.img_w) / 2
        self.offset_y = (ch - self.img_h) / 2
        self._render()

    def _set_zoom(self, z):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        cx, cy = cw / 2, ch / 2
        # Center on current view center
        img_cx, img_cy = self._screen_to_image(cx, cy)
        self.zoom = z
        self.offset_x = cx - img_cx * self.zoom
        self.offset_y = cy - img_cy * self.zoom
        self._render()

    # --- Space key for pan mode ---
    def _on_space_press(self, event):
        # Ignore if focus is on a text entry/combobox
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, ttk.Combobox)):
            return
        if not self.space_held:
            self.space_held = True
            self.canvas.config(cursor="fleur")

    def _on_space_release(self, event):
        if self.space_held:
            self.space_held = False
            if not self.panning:
                self.canvas.config(cursor="crosshair")

    # --- Mouse events ---
    def _on_scroll(self, event):
        mx, my = event.x, event.y
        old_zoom = self.zoom
        factor = 1.2
        if event.delta > 0:
            self.zoom = min(self.zoom * factor, 64.0)
        else:
            self.zoom = max(self.zoom / factor, 0.05)
        self.offset_x = mx - (mx - self.offset_x) * (self.zoom / old_zoom)
        self.offset_y = my - (my - self.offset_y) * (self.zoom / old_zoom)
        self._render()

    def _on_left_press(self, event):
        if self.space_held:
            # Space held = pan mode with left click
            self.panning = True
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            return
        self.selecting = True
        self.sel_start_x = event.x
        self.sel_start_y = event.y

    def _on_left_drag(self, event):
        if self.panning:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self._render()
            return
        if not self.selecting:
            return
        self._render()
        x1 = min(self.sel_start_x, event.x)
        y1 = min(self.sel_start_y, event.y)
        x2 = max(self.sel_start_x, event.x)
        y2 = max(self.sel_start_y, event.y)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00ff00", width=2)

        ix1, iy1 = self._screen_to_image(x1, y1)
        ix2, iy2 = self._screen_to_image(x2, y2)
        pw = int(ix2) - int(ix1)
        ph = int(iy2) - int(iy1)
        self.coord_label.config(
            text=f"Selecting: ({int(ix1)},{int(iy1)}) -> ({int(ix2)},{int(iy2)}) = {pw}x{ph}px | Zoom: {self.zoom:.1f}x"
        )

    def _on_left_release(self, event):
        if self.panning:
            self.panning = False
            if not self.space_held:
                self.canvas.config(cursor="crosshair")
            return
        if not self.selecting:
            return
        self.selecting = False
        x1s = min(self.sel_start_x, event.x)
        y1s = min(self.sel_start_y, event.y)
        x2s = max(self.sel_start_x, event.x)
        y2s = max(self.sel_start_y, event.y)

        ix1, iy1 = self._screen_to_image(x1s, y1s)
        ix2, iy2 = self._screen_to_image(x2s, y2s)

        ix1 = max(0, int(ix1))
        iy1 = max(0, int(iy1))
        ix2 = min(self.img_w, int(ix2))
        iy2 = min(self.img_h, int(iy2))

        if ix2 > ix1 and iy2 > iy1:
            self.current_crop = self.cv_image_rgb[iy1:iy2, ix1:ix2].copy()
            self.current_crop_coords = (ix1, iy1, ix2, iy2)
            w = ix2 - ix1
            h = iy2 - iy1
            self.sel_info_label.config(
                text=f"Selected: ({ix1},{iy1}) -> ({ix2},{iy2}) = {w}x{h}px"
            )
            self._update_preview()
            self._show_existing_template()
        self._render()

    def _on_right_press(self, event):
        self.panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def _on_right_drag(self, event):
        if not self.panning:
            return
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.offset_x += dx
        self.offset_y += dy
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self._render()

    def _on_right_release(self, event):
        self.panning = False

    def _on_mouse_move(self, event):
        ix, iy = self._screen_to_image(event.x, event.y)
        ix_i, iy_i = int(ix), int(iy)
        if 0 <= ix_i < self.img_w and 0 <= iy_i < self.img_h:
            r, g, b = self.cv_image_rgb[iy_i, ix_i]
            self.coord_label.config(
                text=f"Pos: ({ix_i}, {iy_i}) RGB=({r},{g},{b}) | Zoom: {self.zoom:.1f}x"
            )

    # --- Rendering ---
    def _render(self):
        self.canvas.delete("all")
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        # Visible region in image space
        ix1, iy1 = self._screen_to_image(0, 0)
        ix2, iy2 = self._screen_to_image(cw, ch)

        ix1c = max(0, int(ix1))
        iy1c = max(0, int(iy1))
        ix2c = min(self.img_w, int(ix2) + 1)
        iy2c = min(self.img_h, int(iy2) + 1)

        if ix2c <= ix1c or iy2c <= iy1c:
            return

        crop = self.cv_image_rgb[iy1c:iy2c, ix1c:ix2c]
        crop_pil = Image.fromarray(crop)

        sw = max(1, int((ix2c - ix1c) * self.zoom))
        sh = max(1, int((iy2c - iy1c) * self.zoom))

        resample = Image.NEAREST if self.zoom >= 2 else Image.BILINEAR
        crop_resized = crop_pil.resize((sw, sh), resample)

        self._canvas_tk = ImageTk.PhotoImage(crop_resized)
        sx, sy = self._image_to_screen(ix1c, iy1c)
        self.canvas.create_image(sx, sy, anchor=tk.NW, image=self._canvas_tk)

        # Selection rectangle
        if self.current_crop_coords:
            cx1, cy1, cx2, cy2 = self.current_crop_coords
            sx1, sy1 = self._image_to_screen(cx1, cy1)
            sx2, sy2 = self._image_to_screen(cx2, cy2)
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                         outline="#00ff00", width=2, dash=(6, 3))

        # Pixel grid when zoomed enough
        if self.zoom >= 10:
            grid_xs = max(0, int(ix1))
            grid_xe = min(self.img_w, int(ix2) + 1)
            grid_ys = max(0, int(iy1))
            grid_ye = min(self.img_h, int(iy2) + 1)
            for gx in range(grid_xs, grid_xe + 1):
                lx, _ = self._image_to_screen(gx, 0)
                self.canvas.create_line(lx, 0, lx, ch, fill="#333333", width=1)
            for gy in range(grid_ys, grid_ye + 1):
                _, ly = self._image_to_screen(0, gy)
                self.canvas.create_line(0, ly, cw, ly, fill="#333333", width=1)

    def _update_preview(self):
        self.preview_canvas.delete("all")
        if self.current_crop is None:
            return
        h, w = self.current_crop.shape[:2]
        scale = min(370 // max(w, 1), 160 // max(h, 1), 16)
        scale = max(scale, 1)
        pil_crop = Image.fromarray(self.current_crop).resize(
            (w * scale, h * scale), Image.NEAREST)
        self._preview_tk = ImageTk.PhotoImage(pil_crop)
        self.preview_canvas.create_image(5, 5, anchor=tk.NW, image=self._preview_tk)

    # --- Save actions ---
    def _add_to_pending(self):
        if self.current_crop is None:
            messagebox.showwarning("No selection", "Draw a selection on the image first.")
            return
        path = self._get_target_path()
        if not path:
            messagebox.showwarning("No target", "Select a template target or browse a custom file.")
            return
        if self.custom_target_path:
            label = f"[custom] {os.path.basename(path)}"
        else:
            cat = self.category_var.get()
            tmpl = self.template_var.get()
            label = f"[{cat}] {tmpl}"

        for i, (p, _, _) in enumerate(self.pending_saves):
            if p == path:
                # Replace existing
                self.pending_saves[i] = (path, self.current_crop.copy(), label)
                self.pending_listbox.delete(i)
                h, w = self.current_crop.shape[:2]
                self.pending_listbox.insert(i, f"{label} ({w}x{h})")
                return

        self.pending_saves.append((path, self.current_crop.copy(), label))
        h, w = self.current_crop.shape[:2]
        self.pending_listbox.insert(tk.END, f"{label} ({w}x{h})")

        # Auto-advance to next template in same category
        idx = self.template_combo.current()
        values = self.template_combo["values"]
        if idx + 1 < len(values):
            self.template_combo.current(idx + 1)
            self._show_existing_template()

    def _remove_pending(self):
        sel = self.pending_listbox.curselection()
        if sel:
            idx = sel[0]
            self.pending_saves.pop(idx)
            self.pending_listbox.delete(idx)

    def _clear_pending(self):
        if self.pending_saves and messagebox.askyesno("Clear All", "Remove all pending saves?"):
            self.pending_saves.clear()
            self.pending_listbox.delete(0, tk.END)

    def _save_image(self, path, crop_rgb):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bgr = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(path, bgr)

    def _save_current(self):
        if self.current_crop is None:
            messagebox.showwarning("No selection", "Draw a selection first.")
            return
        path = self._get_target_path()
        if not path:
            messagebox.showwarning("No target", "Select a template target.")
            return
        h, w = self.current_crop.shape[:2]
        if messagebox.askyesno("Confirm", f"Save {w}x{h} crop to:\n{path}?"):
            self._save_image(path, self.current_crop)
            messagebox.showinfo("Saved", f"Saved: {path}")
            self._show_existing_template()

    def _save_all_pending(self):
        if not self.pending_saves:
            messagebox.showinfo("Empty", "No pending saves.")
            return
        msg = f"Save {len(self.pending_saves)} templates?\n\n"
        for path, crop, label in self.pending_saves:
            h, w = crop.shape[:2]
            msg += f"  {label}: {w}x{h}\n"
        if messagebox.askyesno("Confirm Batch Save", msg):
            saved = 0
            for path, crop, label in self.pending_saves:
                self._save_image(path, crop)
                saved += 1
            messagebox.showinfo("Done", f"Saved {saved} templates.")
            self.pending_saves.clear()
            self.pending_listbox.delete(0, tk.END)
            self._show_existing_template()


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else "device_with_swamptrolls.png"
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        print("Usage: poetry run python recapture_templates.py [screenshot.png]")
        sys.exit(1)

    root = tk.Tk()
    TemplateCaptureApp(root, image_path)
    root.mainloop()


if __name__ == "__main__":
    main()
