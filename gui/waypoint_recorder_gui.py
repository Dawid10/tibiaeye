#!/usr/bin/env python3
"""
Waypoint Recorder GUI - Visual waypoint recording for Tibia routes.

A professional GUI application for recording and managing waypoints.
Can be displayed on a second monitor while playing.

Features:
- Add waypoints: walk, rope, shovel, useHole, moveUp, moveDown, refillChecker, labels
- Direction selection for moveUp/moveDown (N/S/E/W)
- Visual waypoint list with type, coordinate, label
- Insert at any position, remove any waypoint, undo
- Save/Load JSON routes
- Live coordinate display
"""
import sys
import os
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from src.core import get_screen_capture
from src.repositories.radar.core import (
    get_coordinate,
    get_radar_tools_position,
    get_radar_image,
    get_floor_level,
)
from src.repositories.radar.locators import clear_cache as clear_radar_cache


# Waypoint type styles with icons and colors
WAYPOINT_STYLES = {
    'walk':          {'icon': '🚶', 'color': '#e8e8e8'},
    'label':         {'icon': '🏷️', 'color': '#fff3cd'},
    'useRope':       {'icon': '🪢', 'color': '#d4edda'},
    'useShovel':     {'icon': '⛏️', 'color': '#f8d7da'},
    'useHole':       {'icon': '🕳️', 'color': '#d1ecf1'},
    'moveUp':        {'icon': '⬆️', 'color': '#d4edda'},
    'moveDown':      {'icon': '⬇️', 'color': '#f8d7da'},
    'refillChecker': {'icon': '🔍', 'color': '#e2d5f1'},
    'refillPotions': {'icon': '🧪', 'color': '#d4f1d4'},
    'depositGold':   {'icon': '💰', 'color': '#fff3cd'},
    'depositItems':  {'icon': '📦', 'color': '#d1ecf1'},
}


class RefillCheckerDialog(tk.Toplevel):
    """Dialog for configuring refill checker options."""

    def __init__(self, parent, existing_wp=None):
        super().__init__(parent)
        self.existing_wp = existing_wp  # For editing existing waypoint

        # Set title based on mode
        if self.existing_wp:
            self.title("EDIT REFILL CHECKER")
        else:
            self.title("ADD REFILL CHECKER")

        self.geometry("450x480")
        self.resizable(False, False)

        self.result = None

        # Center on parent
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_window()

        # Handle window close button (X)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 450) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 480) // 2
        self.geometry(f"450x480+{x}+{y}")

    def _on_cancel(self):
        """Handle cancel/close."""
        self.result = None
        self.destroy()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Get existing values if editing
        existing_opts = {}
        existing_label = "checkSupplies"
        if self.existing_wp:
            existing_opts = self.existing_wp.get('options', {})
            existing_label = self.existing_wp.get('label', '')

        # Minimum amounts section
        amounts_frame = ttk.LabelFrame(main_frame, text="Minimum Amounts", padding=10)
        amounts_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(amounts_frame, text="Health Potions:").grid(row=0, column=0, sticky='w', pady=2)
        self.hp_var = tk.StringVar(value=str(existing_opts.get('minimumAmountOfHealthPotions', 50)))
        ttk.Entry(amounts_frame, textvariable=self.hp_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(amounts_frame, text="Mana Potions:").grid(row=1, column=0, sticky='w', pady=2)
        self.mp_var = tk.StringVar(value=str(existing_opts.get('minimumAmountOfManaPotions', 100)))
        ttk.Entry(amounts_frame, textvariable=self.mp_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(amounts_frame, text="Capacity:").grid(row=2, column=0, sticky='w', pady=2)
        self.cap_var = tk.StringVar(value=str(existing_opts.get('minimumAmountOfCap', 500)))
        ttk.Entry(amounts_frame, textvariable=self.cap_var, width=10).grid(row=2, column=1, padx=5, pady=2)

        # Labels section
        labels_frame = ttk.LabelFrame(main_frame, text="Waypoint Labels", padding=10)
        labels_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(labels_frame, text="Redirect to (if supplies OK):").grid(row=0, column=0, sticky='w', pady=2)
        self.redirect_var = tk.StringVar(value=existing_opts.get('waypointLabelToRedirect', 'huntStart'))
        ttk.Entry(labels_frame, textvariable=self.redirect_var, width=20).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(labels_frame, text="Leave to (if need refill):").grid(row=1, column=0, sticky='w', pady=2)
        self.leave_var = tk.StringVar(value=existing_opts.get('waypointLabelToLeave', ''))
        ttk.Entry(labels_frame, textvariable=self.leave_var, width=20).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(labels_frame, text="This waypoint label:").grid(row=2, column=0, sticky='w', pady=2)
        self.label_var = tk.StringVar(value=existing_label)
        ttk.Entry(labels_frame, textvariable=self.label_var, width=20).grid(row=2, column=1, padx=5, pady=2)

        # Help text
        help_text = (
            "The refill checker will redirect to 'Redirect to' label\n"
            "if supplies are above minimum. Otherwise continues to next waypoint.\n"
            "'Leave to' is optional - used for explicit refill route jumps."
        )
        ttk.Label(main_frame, text=help_text, foreground='gray', wraplength=380).pack(pady=5)

        # ============================================================
        # BUTTONS - BIG AND VISIBLE
        # ============================================================
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=(15, 15))

        # Big save button frame with colored background
        btn_color = '#4CAF50' if self.existing_wp else '#2196F3'
        save_frame = tk.Frame(main_frame, bg=btn_color, padx=3, pady=3)
        save_frame.pack(fill='x', pady=(0, 10))

        if self.existing_wp:
            save_btn = tk.Button(
                save_frame,
                text="SALVAR ALTERAÇÕES",
                command=self._on_ok,
                font=('TkDefaultFont', 14, 'bold'),
                bg='#4CAF50',
                fg='white',
                activebackground='#45a049',
                activeforeground='white',
                relief='flat',
                cursor='hand2',
                height=2
            )
        else:
            save_btn = tk.Button(
                save_frame,
                text="ADICIONAR WAYPOINT",
                command=self._on_ok,
                font=('TkDefaultFont', 14, 'bold'),
                bg='#2196F3',
                fg='white',
                activebackground='#1976D2',
                activeforeground='white',
                relief='flat',
                cursor='hand2',
                height=2
            )
        save_btn.pack(fill='x')

        # Cancel button (smaller, below)
        cancel_btn = tk.Button(
            main_frame,
            text="Cancelar",
            command=self._on_cancel,
            font=('TkDefaultFont', 10),
            relief='flat',
            cursor='hand2'
        )
        cancel_btn.pack(pady=(5, 0))

    def _on_ok(self):
        try:
            hp = int(self.hp_var.get())
            mp = int(self.mp_var.get())
            cap = int(self.cap_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for amounts.")
            return

        options = {
            "minimumAmountOfHealthPotions": hp,
            "minimumAmountOfManaPotions": mp,
            "minimumAmountOfCap": cap,
            "waypointLabelToRedirect": self.redirect_var.get(),
        }

        leave_label = self.leave_var.get().strip()
        if leave_label:
            options["waypointLabelToLeave"] = leave_label

        self.result = {
            "options": options,
            "label": self.label_var.get().strip()
        }
        self.destroy()


# Alias for editing existing refill checker
EditRefillCheckerDialog = RefillCheckerDialog


# Available potions for dropdowns
HEALTH_POTIONS = [
    "Health Potion",
    "Strong Health Potion",
    "Great Health Potion",
    "Ultimate Health Potion",
    "Supreme Health Potion",
]

MANA_POTIONS = [
    "Mana Potion",
    "Strong Mana Potion",
    "Great Mana Potion",
    "Ultimate Mana Potion",
]

SPIRIT_POTIONS = [
    "Great Spirit Potion",
    "Ultimate Spirit Potion",
]


class RefillPotionsDialog(tk.Toplevel):
    """Dialog for configuring refill potions (buy from NPC)."""

    def __init__(self, parent, existing_wp=None):
        super().__init__(parent)
        self.existing_wp = existing_wp

        if self.existing_wp:
            self.title("EDIT REFILL POTIONS")
        else:
            self.title("ADD REFILL POTIONS (Buy from NPC)")

        self.geometry("500x550")
        self.resizable(False, False)

        self.result = None

        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_window()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 500) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 550) // 2
        self.geometry(f"500x550+{x}+{y}")

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Get existing values if editing
        existing_opts = {}
        if self.existing_wp:
            existing_opts = self.existing_wp.get('options', {})

        hp_opts = existing_opts.get('healthPotion', {})
        mp_opts = existing_opts.get('manaPotion', {})

        # Title/Description
        ttk.Label(
            main_frame,
            text="Configure potions to buy from NPC",
            font=('TkDefaultFont', 12, 'bold')
        ).pack(pady=(0, 15))

        # ========== HEALTH POTIONS ==========
        hp_frame = ttk.LabelFrame(main_frame, text="🔴 Health Potions", padding=15)
        hp_frame.pack(fill='x', pady=(0, 15))

        # HP Potion Type
        type_frame = ttk.Frame(hp_frame)
        type_frame.pack(fill='x', pady=5)
        ttk.Label(type_frame, text="Potion Type:", width=15).pack(side='left')
        self.hp_type_var = tk.StringVar(value=hp_opts.get('item', 'Strong Health Potion'))
        hp_combo = ttk.Combobox(type_frame, textvariable=self.hp_type_var, values=HEALTH_POTIONS, width=25)
        hp_combo.pack(side='left', padx=5)

        # HP Quantity
        qty_frame = ttk.Frame(hp_frame)
        qty_frame.pack(fill='x', pady=5)
        ttk.Label(qty_frame, text="Target Quantity:", width=15).pack(side='left')
        self.hp_qty_var = tk.StringVar(value=str(hp_opts.get('quantity', 200)))
        ttk.Entry(qty_frame, textvariable=self.hp_qty_var, width=10).pack(side='left', padx=5)
        ttk.Label(qty_frame, text="(will buy until this amount)", foreground='gray').pack(side='left')

        # ========== MANA POTIONS ==========
        mp_frame = ttk.LabelFrame(main_frame, text="🔵 Mana Potions", padding=15)
        mp_frame.pack(fill='x', pady=(0, 15))

        # MP Potion Type
        type_frame2 = ttk.Frame(mp_frame)
        type_frame2.pack(fill='x', pady=5)
        ttk.Label(type_frame2, text="Potion Type:", width=15).pack(side='left')
        self.mp_type_var = tk.StringVar(value=mp_opts.get('item', 'Strong Mana Potion'))
        mp_combo = ttk.Combobox(type_frame2, textvariable=self.mp_type_var, values=MANA_POTIONS, width=25)
        mp_combo.pack(side='left', padx=5)

        # MP Quantity
        qty_frame2 = ttk.Frame(mp_frame)
        qty_frame2.pack(fill='x', pady=5)
        ttk.Label(qty_frame2, text="Target Quantity:", width=15).pack(side='left')
        self.mp_qty_var = tk.StringVar(value=str(mp_opts.get('quantity', 400)))
        ttk.Entry(qty_frame2, textvariable=self.mp_qty_var, width=10).pack(side='left', padx=5)
        ttk.Label(qty_frame2, text="(will buy until this amount)", foreground='gray').pack(side='left')

        # ========== COST ESTIMATE ==========
        cost_frame = ttk.LabelFrame(main_frame, text="💰 Estimated Cost", padding=10)
        cost_frame.pack(fill='x', pady=(0, 15))

        self.cost_label = ttk.Label(cost_frame, text="Select potions to see estimate", foreground='gray')
        self.cost_label.pack()

        # Bind updates to recalculate cost
        self.hp_type_var.trace_add('write', self._update_cost_estimate)
        self.hp_qty_var.trace_add('write', self._update_cost_estimate)
        self.mp_type_var.trace_add('write', self._update_cost_estimate)
        self.mp_qty_var.trace_add('write', self._update_cost_estimate)
        self._update_cost_estimate()

        # Help text
        help_text = (
            "This waypoint buys potions from an NPC.\n"
            "Place it next to the potion NPC (e.g., Edala in Venore).\n"
            "The bot will say 'hi' + 'trade' and buy using the trade window."
        )
        ttk.Label(main_frame, text=help_text, foreground='gray', wraplength=450).pack(pady=10)

        # ========== BUTTONS ==========
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=(10, 15))

        btn_color = '#4CAF50' if self.existing_wp else '#2196F3'
        save_frame = tk.Frame(main_frame, bg=btn_color, padx=3, pady=3)
        save_frame.pack(fill='x', pady=(0, 10))

        btn_text = "SALVAR ALTERAÇÕES" if self.existing_wp else "ADICIONAR WAYPOINT"
        save_btn = tk.Button(
            save_frame,
            text=btn_text,
            command=self._on_ok,
            font=('TkDefaultFont', 14, 'bold'),
            bg=btn_color,
            fg='white',
            activebackground='#45a049' if self.existing_wp else '#1976D2',
            activeforeground='white',
            relief='flat',
            cursor='hand2',
            height=2
        )
        save_btn.pack(fill='x')

        cancel_btn = tk.Button(
            main_frame,
            text="Cancelar",
            command=self._on_cancel,
            font=('TkDefaultFont', 10),
            relief='flat',
            cursor='hand2'
        )
        cancel_btn.pack(pady=(5, 0))

    def _update_cost_estimate(self, *args):
        """Update the cost estimate label."""
        try:
            hp_qty = int(self.hp_qty_var.get() or 0)
            mp_qty = int(self.mp_qty_var.get() or 0)
        except ValueError:
            self.cost_label.config(text="Invalid quantity", foreground='red')
            return

        # Potion prices (approximate)
        prices = {
            'Health Potion': 45,
            'Strong Health Potion': 100,
            'Great Health Potion': 190,
            'Ultimate Health Potion': 310,
            'Supreme Health Potion': 500,
            'Mana Potion': 50,
            'Strong Mana Potion': 80,
            'Great Mana Potion': 120,
            'Ultimate Mana Potion': 175,
            'Great Spirit Potion': 190,
            'Ultimate Spirit Potion': 350,
        }

        hp_price = prices.get(self.hp_type_var.get(), 100)
        mp_price = prices.get(self.mp_type_var.get(), 80)

        hp_cost = hp_price * hp_qty
        mp_cost = mp_price * mp_qty
        total = hp_cost + mp_cost

        self.cost_label.config(
            text=f"HP: {hp_qty}x {hp_price}gp = {hp_cost:,}gp | MP: {mp_qty}x {mp_price}gp = {mp_cost:,}gp | Total: {total:,}gp",
            foreground='#006600'
        )

    def _on_ok(self):
        try:
            hp_qty = int(self.hp_qty_var.get())
            mp_qty = int(self.mp_qty_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for quantities.")
            return

        options = {}

        # Only add health potion if quantity > 0
        if hp_qty > 0:
            options["healthPotion"] = {
                "item": self.hp_type_var.get(),
                "quantity": hp_qty
            }

        # Only add mana potion if quantity > 0
        if mp_qty > 0:
            options["manaPotion"] = {
                "item": self.mp_type_var.get(),
                "quantity": mp_qty
            }

        if not options:
            messagebox.showwarning("No Potions", "Please set at least one potion quantity > 0")
            return

        self.result = {"options": options}
        self.destroy()


# Alias for editing existing refill potions
EditRefillPotionsDialog = RefillPotionsDialog


class WaypointRecorderGUI:
    """Main GUI application for waypoint recording."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Waypoint Recorder")
        self.root.geometry("750x950")
        self.root.minsize(650, 700)

        # State
        self.waypoints = []
        self.output_file = None
        self.selected_index = None
        self.insert_mode = False
        self.undo_stack = []

        # Drag and drop state
        self._drag_data = {"item": None, "index": None}

        # Screen capture for coordinate detection
        clear_radar_cache()
        self.screen = get_screen_capture()
        self._previous_coord = None

        # Build UI
        self._build_ui()
        self._start_coordinate_updater()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _build_ui(self):
        """Build the main user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill='both', expand=True)

        # ========== HEADER ==========
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(header_frame, text="WAYPOINT RECORDER", font=('TkDefaultFont', 16, 'bold')).pack(side='left')

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side='right')
        ttk.Button(btn_frame, text="Load", command=self.load_waypoints).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Save", command=self.save_waypoints).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Save As...", command=self.save_waypoints_as).pack(side='left', padx=2)

        # ========== COORDINATE DISPLAY ==========
        coord_frame = ttk.LabelFrame(main_frame, text="Current Position", padding=10)
        coord_frame.pack(fill='x', pady=(0, 10))

        coord_inner = ttk.Frame(coord_frame)
        coord_inner.pack(fill='x')

        # Display X, Y, Z separately with labels
        coord_display = ttk.Frame(coord_inner)
        coord_display.pack(side='left')

        # X coordinate
        x_frame = ttk.Frame(coord_display)
        x_frame.pack(side='left', padx=(0, 15))
        ttk.Label(x_frame, text="X:", font=('TkDefaultFont', 10)).pack(side='left')
        self.x_label = ttk.Label(x_frame, text="?", font=('TkDefaultFont', 14, 'bold'), foreground='#0066cc')
        self.x_label.pack(side='left', padx=3)

        # Y coordinate
        y_frame = ttk.Frame(coord_display)
        y_frame.pack(side='left', padx=(0, 15))
        ttk.Label(y_frame, text="Y:", font=('TkDefaultFont', 10)).pack(side='left')
        self.y_label = ttk.Label(y_frame, text="?", font=('TkDefaultFont', 14, 'bold'), foreground='#0066cc')
        self.y_label.pack(side='left', padx=3)

        # Z coordinate (floor level)
        z_frame = ttk.Frame(coord_display)
        z_frame.pack(side='left', padx=(0, 15))
        ttk.Label(z_frame, text="Z:", font=('TkDefaultFont', 10)).pack(side='left')
        self.z_label = ttk.Label(z_frame, text="?", font=('TkDefaultFont', 14, 'bold'), foreground='#cc6600')
        self.z_label.pack(side='left', padx=3)

        # Combined coordinate display (smaller, for reference)
        self.coord_label = ttk.Label(coord_inner, text="", font=('TkDefaultFont', 10), foreground='gray')
        self.coord_label.pack(side='left', padx=(20, 0))

        ttk.Button(coord_inner, text="🔄 Refresh", command=self._refresh_coordinate).pack(side='right')
        ttk.Button(coord_inner, text="📋 Copy Coordinate", command=self._copy_coordinate).pack(side='right', padx=(0, 5))

        # ========== ADD WAYPOINT SECTION ==========
        add_frame = ttk.LabelFrame(main_frame, text="Add Waypoint", padding=10)
        add_frame.pack(fill='x', pady=(0, 10))

        # Row 1: Basic waypoints
        row1 = ttk.Frame(add_frame)
        row1.pack(fill='x', pady=5)

        btn_width = 10
        ttk.Button(row1, text="WALK", width=btn_width, command=self.add_walk).pack(side='left', padx=2)
        ttk.Button(row1, text="ROPE", width=btn_width, command=self.add_rope).pack(side='left', padx=2)
        ttk.Button(row1, text="USE HOLE", width=btn_width, command=self.add_use_hole).pack(side='left', padx=2)

        # Row 2: Shovel with direction
        row2 = ttk.Frame(add_frame)
        row2.pack(fill='x', pady=10)

        # Shovel frame (dig in direction)
        shovel_frame = ttk.LabelFrame(row2, text="Shovel (dig direction)", padding=5)
        shovel_frame.pack(side='left', padx=10)
        self._create_direction_buttons(shovel_frame, "useShovel")

        # Move Up frame
        moveup_frame = ttk.LabelFrame(row2, text="Move Up (stairs/ramp)", padding=5)
        moveup_frame.pack(side='left', padx=10)
        self._create_direction_buttons(moveup_frame, "moveUp")

        # Move Down frame
        movedown_frame = ttk.LabelFrame(row2, text="Move Down (stairs/ramp)", padding=5)
        movedown_frame.pack(side='left', padx=10)
        self._create_direction_buttons(movedown_frame, "moveDown")

        # Row 3: Label
        row3 = ttk.Frame(add_frame)
        row3.pack(fill='x', pady=5)

        ttk.Label(row3, text="Label:").pack(side='left')
        self.label_entry = ttk.Entry(row3, width=20)
        self.label_entry.pack(side='left', padx=5)
        ttk.Button(row3, text="ADD LABEL", command=self.add_label).pack(side='left', padx=2)

        # Row 4: Refill Checker and Refill Potions
        row4 = ttk.Frame(add_frame)
        row4.pack(fill='x', pady=5)

        ttk.Button(row4, text="REFILL CHECKER...", command=self.show_refill_checker_dialog).pack(side='left', padx=(0, 5))
        ttk.Button(row4, text="🧪 REFILL POTIONS...", command=self.show_refill_potions_dialog).pack(side='left', padx=5)
        ttk.Label(row4, text="(Buy from NPC)", foreground='gray').pack(side='left', padx=5)

        # Row 5: Deposit actions
        row5 = ttk.Frame(add_frame)
        row5.pack(fill='x', pady=5)

        ttk.Button(row5, text="💰 DEPOSIT GOLD", command=self.add_deposit_gold).pack(side='left', padx=(0, 5))
        ttk.Button(row5, text="📦 DEPOSIT ITEMS...", command=self.show_deposit_items_dialog).pack(side='left', padx=5)
        ttk.Label(row5, text="(Banker / Depot)", foreground='gray').pack(side='left', padx=5)

        # ========== WAYPOINT LIST ==========
        list_frame = ttk.LabelFrame(main_frame, text="Waypoints", padding=10)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        # List header with count and buttons
        list_header = ttk.Frame(list_frame)
        list_header.pack(fill='x', pady=(0, 5))

        self.count_label = ttk.Label(list_header, text="(0 total)")
        self.count_label.pack(side='left')

        ttk.Label(list_header, text="(drag to reorder)", foreground='gray').pack(side='left', padx=10)

        ttk.Button(list_header, text="Undo", command=self.undo).pack(side='right', padx=2)
        self.insert_btn = ttk.Button(list_header, text="Insert Here", command=self.toggle_insert_mode)
        self.insert_btn.pack(side='right', padx=2)
        ttk.Button(list_header, text="Delete Selected", command=self.delete_selected).pack(side='right', padx=2)

        # Treeview for waypoint list
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill='both', expand=True)

        columns = ('id', 'type', 'coord', 'label', 'options')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse')

        self.tree.heading('id', text='#')
        self.tree.heading('type', text='Type')
        self.tree.heading('coord', text='Coordinate')
        self.tree.heading('label', text='Label')
        self.tree.heading('options', text='Options')

        self.tree.column('id', width=40, anchor='center')
        self.tree.column('type', width=100, anchor='w')
        self.tree.column('coord', width=150, anchor='center')
        self.tree.column('label', width=120, anchor='w')
        self.tree.column('options', width=200, anchor='w')

        # Style the treeview - remove gray background
        style = ttk.Style()
        style.configure("Treeview",
                        background="white",
                        foreground="black",
                        fieldbackground="white",
                        rowheight=25)
        style.map("Treeview",
                  background=[('selected', '#0078d7')],
                  foreground=[('selected', 'white')])

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Bind selection
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double_click)

        # Bind right-click context menu
        self.tree.bind('<Button-3>', self._on_right_click)  # Linux/Windows
        self.tree.bind('<Button-2>', self._on_right_click)  # macOS

        # Bind drag and drop
        self.tree.bind('<ButtonPress-1>', self._on_drag_start)
        self.tree.bind('<B1-Motion>', self._on_drag_motion)
        self.tree.bind('<ButtonRelease-1>', self._on_drag_release)

        # Selected waypoint info
        self.selected_label = ttk.Label(list_frame, text="Selected: None", foreground='gray')
        self.selected_label.pack(fill='x', pady=(5, 0))

        # ========== STATUS BAR ==========
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill='x')

        ttk.Button(status_frame, text="SAVE & EXIT", command=self.save_and_exit).pack(side='left')

        self.status_label = ttk.Label(status_frame, text="Ready", foreground='gray')
        self.status_label.pack(side='right')

    def _create_direction_buttons(self, parent, wp_type):
        """Create N/S/E/W direction buttons for move waypoints."""
        # Grid: N on top, W-center-E in middle, S on bottom
        ttk.Button(parent, text="N", width=3,
                   command=lambda: self.add_move_waypoint(wp_type, "north")).grid(row=0, column=1, pady=1)
        ttk.Button(parent, text="W", width=3,
                   command=lambda: self.add_move_waypoint(wp_type, "west")).grid(row=1, column=0, padx=1)
        ttk.Label(parent, text="+").grid(row=1, column=1)
        ttk.Button(parent, text="E", width=3,
                   command=lambda: self.add_move_waypoint(wp_type, "east")).grid(row=1, column=2, padx=1)
        ttk.Button(parent, text="S", width=3,
                   command=lambda: self.add_move_waypoint(wp_type, "south")).grid(row=2, column=1, pady=1)

    def _bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind('<Delete>', lambda e: self.delete_selected())
        self.root.bind('<BackSpace>', lambda e: self.delete_selected())
        self.root.bind('<Control-z>', lambda e: self.undo())
        self.root.bind('<Command-z>', lambda e: self.undo())  # macOS
        self.root.bind('<Control-s>', lambda e: self.save_waypoints())
        self.root.bind('<Command-s>', lambda e: self.save_waypoints())  # macOS
        self.root.bind('<Control-o>', lambda e: self.load_waypoints())
        self.root.bind('<Command-o>', lambda e: self.load_waypoints())  # macOS

        # F-key shortcuts (same as terminal version)
        self.root.bind('<F5>', lambda e: self.undo())
        self.root.bind('<F6>', lambda e: self.add_walk())
        self.root.bind('<F7>', lambda e: self.add_rope())
        self.root.bind('<F8>', lambda e: self.add_shovel())
        self.root.bind('<F11>', lambda e: self.save_waypoints())

        # Escape to exit insert mode
        self.root.bind('<Escape>', lambda e: self._exit_insert_mode())

    def _start_coordinate_updater(self):
        """Start periodic coordinate updates."""
        def update():
            coord = self._get_current_coordinate()
            self._update_coord_display(coord)
            self.root.after(500, update)
        update()

    def _update_coord_display(self, coord):
        """Update all coordinate display labels."""
        if coord:
            self.x_label.config(text=str(coord[0]))
            self.y_label.config(text=str(coord[1]))
            self.z_label.config(text=str(coord[2]))
            self.coord_label.config(text=f"({coord[0]}, {coord[1]}, {coord[2]})")
        else:
            self.x_label.config(text="?")
            self.y_label.config(text="?")
            self.z_label.config(text="?")
            self.coord_label.config(text="Not detected")

    def _refresh_coordinate(self):
        """Force refresh of coordinate display."""
        clear_radar_cache()
        self._previous_coord = None
        coord = self._get_current_coordinate()
        self._update_coord_display(coord)
        if coord:
            self.status_label.config(text="Coordinate refreshed")
        else:
            self.status_label.config(text="Could not detect coordinate")

    def _copy_coordinate(self):
        """Copy current coordinate to clipboard."""
        coord = self._get_current_coordinate()
        if coord:
            coord_str = f"{coord[0]}, {coord[1]}, {coord[2]}"
            self.root.clipboard_clear()
            self.root.clipboard_append(coord_str)
            self.root.update()  # Required for clipboard to work
            self.status_label.config(text=f"Copied: {coord_str}")
        else:
            self.status_label.config(text="Could not detect coordinate to copy")

    def _get_current_coordinate(self):
        """Get current coordinate from game screen."""
        try:
            img = self.screen.capture()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            coord = get_coordinate(gray, self._previous_coord)
            if coord:
                self._previous_coord = coord
            return coord
        except Exception as e:
            return None

    def _refresh_waypoint_list(self):
        """Refresh the waypoint treeview."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add waypoints
        for i, wp in enumerate(self.waypoints):
            wp_type = wp.get('type', 'unknown')
            coord = wp.get('coordinate', [0, 0, 0])
            label = wp.get('label', '')
            options = wp.get('options', {})

            # Format coordinate
            coord_str = f"({coord[0]}, {coord[1]}, {coord[2]})"

            # Format options (show direction for move waypoints, etc.)
            opts_str = ""
            if 'direction' in options and 'hotkey' in options:
                # useShovel has both direction and hotkey
                opts_str = f"dir: {options['direction']}, key: {options['hotkey']}"
            elif 'direction' in options:
                opts_str = f"dir: {options['direction']}"
            elif 'hotkey' in options:
                opts_str = f"key: {options['hotkey']}"
            elif 'minimumAmountOfHealthPotions' in options:
                # refillChecker
                hp = options.get('minimumAmountOfHealthPotions', 0)
                mp = options.get('minimumAmountOfManaPotions', 0)
                cap = options.get('minimumAmountOfCap', 0)
                opts_str = f"HP≥{hp}, MP≥{mp}, Cap≥{cap}"
            elif 'healthPotion' in options or 'manaPotion' in options:
                # refillPotions
                parts = []
                if 'healthPotion' in options:
                    hp_item = options['healthPotion'].get('item', 'HP')
                    hp_qty = options['healthPotion'].get('quantity', 0)
                    # Shorten name: "Strong Health Potion" -> "SHP"
                    hp_short = ''.join(w[0] for w in hp_item.split())
                    parts.append(f"{hp_short}→{hp_qty}")
                if 'manaPotion' in options:
                    mp_item = options['manaPotion'].get('item', 'MP')
                    mp_qty = options['manaPotion'].get('quantity', 0)
                    mp_short = ''.join(w[0] for w in mp_item.split())
                    parts.append(f"{mp_short}→{mp_qty}")
                opts_str = ", ".join(parts)

            # Get style (icon only, no background color)
            style = WAYPOINT_STYLES.get(wp_type, {'icon': '❓', 'color': '#ffffff'})
            type_display = f"{style['icon']} {wp_type}"

            # Insert item (no background color tags - clean white background)
            self.tree.insert('', 'end', values=(i, type_display, coord_str, label, opts_str))

        # Update count label
        self.count_label.config(text=f"({len(self.waypoints)} total)")

    def _on_select(self, event):
        """Handle waypoint selection."""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            self.selected_index = int(item['values'][0])
            wp = self.waypoints[self.selected_index]
            coord = wp.get('coordinate', [0, 0, 0])
            self.selected_label.config(
                text=f"Selected: #{self.selected_index} {wp.get('type')} at ({coord[0]}, {coord[1]}, {coord[2]})"
            )
            # Update insert mode status to show new insertion point
            if self.insert_mode:
                self.status_label.config(
                    text=f"INSERT MODE: All new waypoints will be added after #{self.selected_index}",
                    foreground='#cc6600'
                )
        else:
            self.selected_index = None
            self.selected_label.config(text="Selected: None")

    def _on_double_click(self, event):
        """Handle double-click to edit waypoint based on type."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        idx = int(item['values'][0])
        wp = self.waypoints[idx]
        wp_type = wp.get('type', '')

        # Different actions based on waypoint type
        if wp_type == 'refillChecker':
            self._edit_refill_checker(idx, wp)
        elif wp_type == 'refillPotions':
            self._edit_refill_potions(idx, wp)
        elif wp_type in ('useRope', 'useShovel'):
            self._edit_hotkey(idx, wp)
        else:
            # Default: edit label
            self._edit_label(idx, wp)

    def _edit_label(self, idx, wp):
        """Edit the label of a waypoint."""
        current_label = wp.get('label', '')
        new_label = simpledialog.askstring(
            "Edit Label",
            f"Enter label for waypoint #{idx}:",
            initialvalue=current_label,
            parent=self.root
        )

        if new_label is not None:
            self._save_undo_state()
            wp['label'] = new_label
            self._refresh_waypoint_list()
            self.status_label.config(text=f"Updated label for waypoint #{idx}")

    def _edit_hotkey(self, idx, wp):
        """Edit the hotkey of a rope/shovel waypoint."""
        options = wp.get('options', {})
        current_hotkey = options.get('hotkey', 'o' if wp['type'] == 'useRope' else 'p')

        new_hotkey = simpledialog.askstring(
            "Edit Hotkey",
            f"Enter hotkey for {wp['type']} waypoint #{idx}:",
            initialvalue=current_hotkey,
            parent=self.root
        )

        if new_hotkey is not None and new_hotkey.strip():
            self._save_undo_state()
            if 'options' not in wp:
                wp['options'] = {}
            wp['options']['hotkey'] = new_hotkey.strip()
            self._refresh_waypoint_list()
            self.status_label.config(text=f"Updated hotkey for waypoint #{idx} to '{new_hotkey.strip()}'")

    def _edit_refill_checker(self, idx, wp):
        """Edit refill checker options."""
        dialog = EditRefillCheckerDialog(self.root, wp)
        self.root.wait_window(dialog)

        if dialog.result:
            self._save_undo_state()
            wp['options'] = dialog.result['options']
            wp['label'] = dialog.result['label']
            self._refresh_waypoint_list()
            self.status_label.config(text=f"Updated refill checker waypoint #{idx}")

    def _edit_refill_potions(self, idx, wp):
        """Edit refill potions options."""
        dialog = EditRefillPotionsDialog(self.root, wp)
        self.root.wait_window(dialog)

        if dialog.result:
            self._save_undo_state()
            wp['options'] = dialog.result['options']
            self._refresh_waypoint_list()
            self.status_label.config(text=f"Updated refill potions waypoint #{idx}")

    def _on_right_click(self, event):
        """Handle right-click context menu."""
        # Select the item under cursor
        item = self.tree.identify_row(event.y)
        if not item:
            return

        self.tree.selection_set(item)
        values = self.tree.item(item, "values")
        if not values:
            return

        idx = int(values[0])
        wp = self.waypoints[idx]
        coord = wp.get('coordinate', [0, 0, 0])

        # Create context menu
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label=f"Copy Coordinate ({coord[0]}, {coord[1]}, {coord[2]})",
            command=lambda: self._copy_waypoint_coordinate(coord)
        )
        menu.add_separator()
        menu.add_command(label="Edit Label", command=lambda: self._edit_label(idx, wp))
        menu.add_command(label="Delete", command=self.delete_selected)

        # Show menu at cursor position
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_waypoint_coordinate(self, coord):
        """Copy waypoint coordinate to clipboard."""
        coord_str = f"{coord[0]}, {coord[1]}, {coord[2]}"
        self.root.clipboard_clear()
        self.root.clipboard_append(coord_str)
        self.root.update()
        self.status_label.config(text=f"Copied: {coord_str}")

    def _on_drag_start(self, event):
        """Start dragging a waypoint."""
        item = self.tree.identify_row(event.y)
        if item:
            self._drag_data["item"] = item
            values = self.tree.item(item, "values")
            if values:
                self._drag_data["index"] = int(values[0])

    def _on_drag_motion(self, event):
        """Handle drag motion - show visual feedback."""
        if self._drag_data["item"] is None:
            return

        # Get the item under the cursor
        target = self.tree.identify_row(event.y)
        if target and target != self._drag_data["item"]:
            # Change cursor to indicate drop is possible
            self.tree.config(cursor="hand2")
        else:
            self.tree.config(cursor="")

    def _on_drag_release(self, event):
        """Handle drop - reorder waypoints."""
        self.tree.config(cursor="")

        if self._drag_data["item"] is None or self._drag_data["index"] is None:
            self._drag_data = {"item": None, "index": None}
            return

        # Get the target position
        target = self.tree.identify_row(event.y)
        if not target or target == self._drag_data["item"]:
            self._drag_data = {"item": None, "index": None}
            return

        target_values = self.tree.item(target, "values")
        if not target_values:
            self._drag_data = {"item": None, "index": None}
            return

        source_idx = self._drag_data["index"]
        target_idx = int(target_values[0])

        # Don't move if same position
        if source_idx == target_idx:
            self._drag_data = {"item": None, "index": None}
            return

        # Save for undo
        self._save_undo_state()

        # Move the waypoint
        waypoint = self.waypoints.pop(source_idx)
        self.waypoints.insert(target_idx, waypoint)

        # Refresh and show feedback
        self._refresh_waypoint_list()
        self.status_label.config(text=f"Moved waypoint from #{source_idx} to #{target_idx}")

        # Select the moved item
        children = self.tree.get_children()
        if children and target_idx < len(children):
            self.tree.selection_set(children[target_idx])
            self.tree.see(children[target_idx])

        # Reset drag data
        self._drag_data = {"item": None, "index": None}

    def _save_undo_state(self):
        """Save current state for undo."""
        import copy
        self.undo_stack.append(copy.deepcopy(self.waypoints))
        # Keep only last 50 states
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    # ==================== WAYPOINT ACTIONS ====================

    def add_waypoint(self, wp_type: str, options: dict = None, label: str = ""):
        """Add a waypoint at current position."""
        coord = self._get_current_coordinate()
        if coord is None:
            messagebox.showerror("Error", "Could not detect current coordinate!\n\nMake sure Tibia is visible and the minimap is at default zoom.")
            return False

        # Save for undo
        self._save_undo_state()

        waypoint = {
            "type": wp_type,
            "coordinate": list(coord),
            "label": label,
            "options": options or {}
        }

        if self.insert_mode and self.selected_index is not None:
            # Insert after selected position
            insert_pos = self.selected_index + 1
            self.waypoints.insert(insert_pos, waypoint)
            # Keep insert mode active and advance insertion point
            self.selected_index = insert_pos
            self.status_label.config(
                text=f"INSERT MODE: Inserted {wp_type} at #{insert_pos} | Next insert after #{self.selected_index}",
                foreground='#cc6600'
            )
        else:
            # Append to end
            self.waypoints.append(waypoint)
            self.status_label.config(text=f"Added {wp_type} at {coord}")

        self._refresh_waypoint_list()

        # Scroll to new waypoint and select it
        children = self.tree.get_children()
        if children:
            if self.insert_mode and self.selected_index is not None:
                # Scroll to and select the inserted waypoint
                target_idx = min(self.selected_index, len(children) - 1)
                self.tree.see(children[target_idx])
                self.tree.selection_set(children[target_idx])
            else:
                self.tree.see(children[-1])

        return True

    def add_walk(self):
        """Add walk waypoint."""
        self.add_waypoint("walk")

    def add_rope(self):
        """Add rope waypoint."""
        self.add_waypoint("useRope", {"hotkey": "o"})

    def add_use_hole(self):
        """Add useHole waypoint (right-click on ladder/hole)."""
        self.add_waypoint("useHole")

    def add_move_waypoint(self, wp_type: str, direction: str):
        """Add moveUp, moveDown, or useShovel waypoint with direction."""
        if wp_type == "useShovel":
            # Shovel needs both hotkey and direction
            self.add_waypoint(wp_type, {"hotkey": "p", "direction": direction})
        else:
            self.add_waypoint(wp_type, {"direction": direction})

    def add_label(self):
        """Add label waypoint."""
        label_name = self.label_entry.get().strip()
        if not label_name:
            messagebox.showwarning("No Label", "Please enter a label name first.")
            self.label_entry.focus()
            return

        self.add_waypoint("label", label=label_name)
        self.label_entry.delete(0, 'end')

    def show_refill_checker_dialog(self):
        """Show dialog for refill checker configuration."""
        dialog = RefillCheckerDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result:
            self.add_waypoint("refillChecker", dialog.result['options'], dialog.result['label'])

    def show_refill_potions_dialog(self):
        """Show dialog for refill potions (buy from NPC) configuration."""
        dialog = RefillPotionsDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result:
            self.add_waypoint("refillPotions", dialog.result['options'])

    def add_deposit_gold(self):
        """Add deposit gold waypoint (talk to banker)."""
        self.add_waypoint("depositGold")

    def show_deposit_items_dialog(self):
        """Show dialog for deposit items configuration."""
        # Simple dialog for now - just add the waypoint
        # Could be expanded later with options for loot backpack, etc.
        self.add_waypoint("depositItems", {
            "depositMethod": "backpack",
            "lootBackpack": "loot"
        })

    def toggle_insert_mode(self):
        """Toggle insert mode."""
        if self.selected_index is None:
            messagebox.showinfo("Select Waypoint", "Please select a waypoint first.\nThe new waypoint will be inserted after it.")
            return

        self.insert_mode = not self.insert_mode

        if self.insert_mode:
            self.insert_btn.config(text="Exit Insert Mode")
            self.status_label.config(
                text=f"INSERT MODE: All new waypoints will be added after #{self.selected_index}",
                foreground='#cc6600'
            )
        else:
            self.insert_btn.config(text="Insert Here")
            self.status_label.config(text="Ready (back to normal mode)", foreground='gray')

    def _exit_insert_mode(self):
        """Exit insert mode (called by Escape key)."""
        if self.insert_mode:
            self.insert_mode = False
            self.insert_btn.config(text="Insert Here")
            self.status_label.config(text="Ready (exited insert mode)", foreground='gray')

    def delete_selected(self):
        """Delete the selected waypoint."""
        if self.selected_index is None:
            messagebox.showinfo("Select Waypoint", "Please select a waypoint to delete.")
            return

        # Save for undo
        self._save_undo_state()

        removed = self.waypoints.pop(self.selected_index)
        self.status_label.config(text=f"Deleted waypoint #{self.selected_index} ({removed['type']})")
        self.selected_index = None
        self.selected_label.config(text="Selected: None")
        self._refresh_waypoint_list()

    def undo(self):
        """Undo last action."""
        if not self.undo_stack:
            self.status_label.config(text="Nothing to undo")
            return

        self.waypoints = self.undo_stack.pop()
        self._refresh_waypoint_list()
        self.status_label.config(text="Undone")

    # ==================== FILE OPERATIONS ====================

    def save_waypoints(self):
        """Save waypoints to current file."""
        if not self.output_file:
            self.save_waypoints_as()
            return

        self._do_save()

    def save_waypoints_as(self):
        """Save waypoints to a new file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir="routes/",
            title="Save Waypoints"
        )

        if filename:
            self.output_file = filename
            self._do_save()

    def _do_save(self):
        """Actually save the waypoints file."""
        if not self.output_file:
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.output_file) or '.', exist_ok=True)

        # Renumber IDs
        for i, wp in enumerate(self.waypoints):
            wp['id'] = i

        data = {
            "name": os.path.splitext(os.path.basename(self.output_file))[0],
            "waypoints": self.waypoints,
            "metadata": {
                "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        with open(self.output_file, 'w') as f:
            json.dump(data, f, indent=2)

        self.status_label.config(text=f"Saved {len(self.waypoints)} waypoints to {os.path.basename(self.output_file)}")
        self.root.title(f"Waypoint Recorder - {os.path.basename(self.output_file)}")

    def load_waypoints(self):
        """Load waypoints from file."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir="routes/",
            title="Load Waypoints"
        )

        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                data = json.load(f)

            self.waypoints = data.get('waypoints', [])
            self.output_file = filename
            self.undo_stack = []

            self._refresh_waypoint_list()
            self.status_label.config(text=f"Loaded {len(self.waypoints)} waypoints from {os.path.basename(filename)}")
            self.root.title(f"Waypoint Recorder - {os.path.basename(filename)}")

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load file:\n{e}")

    def save_and_exit(self):
        """Save waypoints and exit."""
        if self.waypoints:
            if not self.output_file:
                result = messagebox.askyesnocancel(
                    "Save Before Exit",
                    "Do you want to save the waypoints before exiting?"
                )
                if result is None:  # Cancel
                    return
                if result:  # Yes
                    self.save_waypoints_as()
                    if not self.output_file:  # User cancelled save dialog
                        return
            else:
                self._do_save()

        self.root.destroy()

    def run(self):
        """Run the application."""
        self.root.protocol("WM_DELETE_WINDOW", self.save_and_exit)
        self.root.mainloop()


def main():
    """Entry point."""
    print("=" * 60)
    print("  WAYPOINT RECORDER GUI")
    print("=" * 60)
    print()
    print("Starting GUI...")
    print()
    print("Keyboard shortcuts:")
    print("  F6 - Add WALK")
    print("  F7 - Add ROPE")
    print("  F8 - Add SHOVEL")
    print("  F5 - Undo")
    print("  F11 - Save")
    print("  Ctrl+S / Cmd+S - Save")
    print("  Ctrl+Z / Cmd+Z - Undo")
    print("  Delete / Backspace - Delete selected")
    print("  Escape - Exit insert mode")
    print()
    print("Tips:")
    print("  - Drag waypoints to reorder them")
    print("  - Double-click to edit labels")
    print("  - Use INSERT MODE to add multiple waypoints at a specific position")
    print("    (select a waypoint, click 'Insert Here', add waypoints, press Escape)")
    print()

    app = WaypointRecorderGUI()
    app.run()


if __name__ == "__main__":
    main()
