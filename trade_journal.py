import customtkinter as ctk
import tkinter as tk
import json
import os
import sys
import calendar
import threading
import webbrowser
import urllib.request
import urllib.error
import base64
import subprocess
from datetime import datetime

# =====================
# APP META / VERSION
# =====================

APP_NAME = "TradeLog"
APP_VERSION = "0.9.0"          # bump this + tag a matching GitHub release (vX.Y.Z) when you ship updates
GITHUB_REPO = "Scorpy644/TradeLog"

# =====================
# DATA
# =====================

# When packaged with PyInstaller, a relative path resolves unpredictably
# depending on how the .exe was launched. Anchor trades.json to the folder
# the .exe (or this script) actually lives in, so your data always loads
# from -- and saves to -- the same place, no matter how you open the app.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, "trades.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def load_trades():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_trades():
    with open(DATA_FILE, "w") as f:
        json.dump(trades_data, f, indent=4)


trades_data = load_trades()


def get_day_trades(date_str):
    return trades_data.get(date_str, [])


def day_stats(date_str):
    trades = get_day_trades(date_str)
    if not trades:
        return None
    total_pnl = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    win_rate = round(wins / len(trades) * 100)
    return total_pnl, win_rate, len(trades)


# =====================
# LOCAL CONFIG (token lives here only -- never in this .py file, never pushed to git)
# =====================

DEFAULT_CONFIG = {
    "github_token": "",
    "auto_check_updates": True,
    "last_dismissed_version": ""
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)


app_config = load_config()


# =====================
# COLORS
# =====================

BACKGROUND = "#0B0E14"
CARD = "#12161F"
CELL_BORDER = "#1E2530"
TEXT = "#F1F5F9"
MUTED = "#6B7280"

GREEN = "#22C55E"
GREEN_BG = "#0F2A1C"
GREEN_BORDER = "#1F6E3E"

RED = "#F87171"
RED_BG = "#2A1414"
RED_BORDER = "#7F1D1D"

ACCENT = "#22C55E"
INPUT_BG = "#1A1F2A"
BORDER = "#232B38"

DAY_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]


def lighten(hex_color, amount=16):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, r + amount)
    g = min(255, g + amount)
    b = min(255, b + amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def advance_month(month, year, delta):
    m = month + delta
    y = year
    if m < 1:
        m = 12
        y -= 1
    elif m > 12:
        m = 1
        y += 1
    return m, y


def version_tuple(v):
    """'1.2.0' -> (1, 2, 0), ignoring a leading 'v' and any non-numeric suffix."""
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = ""
        for ch in p:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


# =====================
# APP SETUP
# =====================

ctk.set_appearance_mode("dark")

root = ctk.CTk()
root.title(f"{APP_NAME}")
root.geometry("1500x820")
root.configure(fg_color=BACKGROUND)
root.minsize(1000, 620)

current_month = datetime.now().month
current_year = datetime.now().year
current_panel_date = None
panel_visible = False

# =====================
# HEADER
# =====================

header = ctk.CTkFrame(root, fg_color="transparent", height=70)
header.pack(fill="x", padx=30, pady=(25, 10))
header.pack_propagate(False)

title_label = ctk.CTkLabel(
    header,
    text=APP_NAME,
    font=("Segoe UI", 26, "bold")
)
title_label.pack(side="left")

add_trade_header_btn = ctk.CTkButton(
    header, text="+ Add Trade", width=130, height=38, corner_radius=10,
    fg_color=ACCENT, text_color="#05210F", hover_color="#16A34A",
    font=("Segoe UI", 13, "bold"),
    command=lambda: select_day(datetime.now().strftime("%Y-%m-%d"))
)
add_trade_header_btn.pack(side="left", padx=20)

nav_frame = ctk.CTkFrame(header, fg_color="transparent")
nav_frame.pack(side="right")

settings_btn = ctk.CTkButton(
    nav_frame, text="\u2699", width=42, height=42, corner_radius=10,
    fg_color="transparent", border_width=1, border_color="#3A4252",
    hover_color="#232B38", font=("Segoe UI", 16),
    command=lambda: toggle_settings()
)
settings_btn.pack(side="left", padx=(0, 14))

month_label = ctk.CTkLabel(nav_frame, text="", font=("Segoe UI", 20, "bold"))

prev_btn = ctk.CTkButton(
    nav_frame, text="\u2190", width=42, height=42, corner_radius=10,
    fg_color="#161B25", hover_color="#232B38", font=("Segoe UI", 16),
    command=lambda: change_month(-1)
)
prev_btn.pack(side="left", padx=(0, 5))

month_label.pack(side="left", padx=15)

next_btn = ctk.CTkButton(
    nav_frame, text="\u2192", width=42, height=42, corner_radius=10,
    fg_color="transparent", border_width=1, border_color="#3A4252",
    hover_color="#232B38", font=("Segoe UI", 16),
    command=lambda: change_month(1)
)
next_btn.pack(side="left", padx=(5, 0))

# =====================
# BODY: calendar (left) + panel (right, hidden until opened)
# =====================

body = ctk.CTkFrame(root, fg_color="transparent")
body.pack(fill="both", expand=True, padx=30, pady=(0, 25))

calendar_container = ctk.CTkFrame(body, fg_color="transparent")
calendar_container.pack(side="left", fill="both", expand=True, padx=(0, 20))

canvas = tk.Canvas(
    calendar_container, bg=BACKGROUND, highlightthickness=0, bd=0
)
canvas.pack(fill="both", expand=True)

PANEL_WIDTH = 400

panel = ctk.CTkFrame(
    body, width=PANEL_WIDTH, fg_color=CARD, corner_radius=14,
    border_width=1, border_color=BORDER
)
panel.pack_propagate(False)
# not packed yet -- shown on demand via show_panel()

# =====================
# CALENDAR RENDERING (PIL supersampled -> anti-aliased)
# =====================

from PIL import Image, ImageDraw, ImageFont, ImageTk

SUPERSAMPLE = 2
HEADER_ROW_H = 34
CELL_PAD = 9
MAX_ROWS = 6  # fixed so every month gets the same cell height

_font_cache = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    candidates = (
        [r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf", "arialbd.ttf"]
        if bold else
        [r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf", "arial.ttf"]
    )

    font = None
    for name in candidates:
        try:
            font = ImageFont.truetype(name, size)
            break
        except Exception:
            continue

    if font is None:
        font = ImageFont.load_default()

    _font_cache[key] = font
    return font


def compute_cell_rects(year, month, width, height):
    """Returns (day_cells, blank_cells). day_cells maps date_str -> (x1,y1,x2,y2).
    Row height is based on a fixed MAX_ROWS so cell size never changes month to month."""

    col_w = width / 7
    grid_h = height - HEADER_ROW_H
    row_h = grid_h / MAX_ROWS

    first_weekday, days_in_month = calendar.monthrange(year, month)
    first_weekday_sun = (first_weekday + 1) % 7
    total_cells = first_weekday_sun + days_in_month
    rows_needed = -(-total_cells // 7)

    day_cells = {}
    blank_cells = []
    day_num = 1

    for r in range(rows_needed):
        for c in range(7):
            index = r * 7 + c

            x1 = c * col_w + CELL_PAD
            y1 = HEADER_ROW_H + r * row_h + CELL_PAD
            x2 = (c + 1) * col_w - CELL_PAD
            y2 = HEADER_ROW_H + (r + 1) * row_h - CELL_PAD

            if index < first_weekday_sun or day_num > days_in_month:
                blank_cells.append((x1, y1, x2, y2))
                continue

            date_str = f"{year:04d}-{month:02d}-{day_num:02d}"
            day_cells[date_str] = (x1, y1, x2, y2)
            day_num += 1

    return day_cells, blank_cells


photo_image_ref = None
calendar_image_id = None


def render_calendar_image():
    global photo_image_ref, calendar_image_id

    width = canvas.winfo_width()
    height = canvas.winfo_height()

    if width < 20 or height < 20:
        return

    scale = SUPERSAMPLE
    big_w, big_h = width * scale, height * scale

    img = Image.new("RGB", (big_w, big_h), BACKGROUND)
    draw = ImageDraw.Draw(img)

    header_font = get_font(12 * scale, bold=True)
    day_font = get_font(16 * scale, bold=True)
    pnl_font = get_font(21 * scale, bold=True)
    rate_font = get_font(14 * scale, bold=False)

    col_w = width / 7

    for i, name in enumerate(DAY_NAMES):
        cx = (i * col_w + col_w / 2) * scale
        cy = (HEADER_ROW_H / 2) * scale
        draw.text((cx, cy), name, font=header_font, fill=MUTED, anchor="mm")

    day_cells, blank_cells = compute_cell_rects(current_year, current_month, width, height)

    for (x1, y1, x2, y2) in blank_cells:
        draw.rounded_rectangle(
            [x1 * scale, y1 * scale, x2 * scale, y2 * scale],
            radius=10 * scale, fill=CARD
        )

    for date_str, (x1, y1, x2, y2) in day_cells.items():
        stats = day_stats(date_str)

        if stats:
            pnl, win_rate, count = stats
            if pnl >= 0:
                bg, border, txt_color = GREEN_BG, GREEN_BORDER, GREEN
            else:
                bg, border, txt_color = RED_BG, RED_BORDER, RED
        else:
            bg, border, txt_color = CARD, CELL_BORDER, TEXT

        sx1, sy1, sx2, sy2 = x1 * scale, y1 * scale, x2 * scale, y2 * scale

        draw.rounded_rectangle(
            [sx1, sy1, sx2, sy2], radius=10 * scale,
            fill=bg, outline=border, width=max(1, scale)
        )

        day_num = int(date_str.split("-")[2])
        draw.text(
            (sx1 + 16 * scale, sy1 + 24 * scale), str(day_num),
            font=day_font, fill=TEXT, anchor="lm"
        )

        if stats:
            pnl, win_rate, count = stats
            sign = "" if pnl >= 0 else "-"
            pnl_text = f"{sign}${abs(pnl):,.2f}"
            cy = (sy1 + sy2) / 2

            draw.text(((sx1 + sx2) / 2, cy - 13 * scale), pnl_text, font=pnl_font, fill=txt_color, anchor="mm")
            draw.text(((sx1 + sx2) / 2, cy + 22 * scale), f"{win_rate}%", font=rate_font, fill=txt_color, anchor="mm")

    resized = img.resize((width, height), Image.LANCZOS)
    photo_image_ref = ImageTk.PhotoImage(resized)

    if calendar_image_id is None:
        calendar_image_id = canvas.create_image(0, 0, anchor="nw", image=photo_image_ref, tags=("calimg",))
    else:
        canvas.itemconfig(calendar_image_id, image=photo_image_ref)

    canvas.tag_lower("calimg")


# =====================
# HIT-TESTING + LIGHTWEIGHT HOVER (no full re-render on mouse move)
# =====================

last_hover_date = None
hover_outline_id = None


def date_at_pixel(x, y):
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    if width < 20 or height < 20:
        return None

    day_cells, _ = compute_cell_rects(current_year, current_month, width, height)

    for date_str, (x1, y1, x2, y2) in day_cells.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return date_str

    return None


def round_rect(cnv, x1, y1, x2, y2, radius=10, **kwargs):
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return cnv.create_polygon(points, smooth=True, **kwargs)


def clear_hover():
    global last_hover_date, hover_outline_id
    if hover_outline_id is not None:
        canvas.delete(hover_outline_id)
        hover_outline_id = None
    last_hover_date = None
    canvas.configure(cursor="")


def canvas_motion(event):
    global last_hover_date, hover_outline_id

    date_str = date_at_pixel(event.x, event.y)

    if date_str == last_hover_date:
        return

    last_hover_date = date_str

    if hover_outline_id is not None:
        canvas.delete(hover_outline_id)
        hover_outline_id = None

    if date_str is None:
        canvas.configure(cursor="")
        return

    canvas.configure(cursor="hand2")

    day_cells, _ = compute_cell_rects(current_year, current_month, canvas.winfo_width(), canvas.winfo_height())
    x1, y1, x2, y2 = day_cells[date_str]
    hover_outline_id = round_rect(canvas, x1, y1, x2, y2, radius=10, outline=ACCENT, width=2, fill="")


def canvas_click(event):
    date_str = date_at_pixel(event.x, event.y)
    if date_str:
        select_day(date_str)


canvas.bind("<Motion>", canvas_motion)
canvas.bind("<Leave>", lambda e: clear_hover())
canvas.bind("<Button-1>", canvas_click)


def redraw_current(event=None):
    global hover_outline_id, last_hover_date
    if hover_outline_id is not None:
        canvas.delete(hover_outline_id)
        hover_outline_id = None
    last_hover_date = None
    render_calendar_image()
    month_label.configure(text=f"{calendar.month_name[current_month]} {current_year}")


canvas.bind("<Configure>", redraw_current)


def change_month(direction):
    global current_month, current_year
    current_month, current_year = advance_month(current_month, current_year, direction)
    redraw_current()


# =====================
# PANEL: day trades + add-trade form (opens on demand)
# =====================

panel_scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent")
panel_scroll.pack(fill="both", expand=True, padx=20, pady=20)

panel_header_row = ctk.CTkFrame(panel_scroll, fg_color="transparent")
panel_header_row.pack(fill="x", pady=(0, 2))

panel_date_label = ctk.CTkLabel(
    panel_header_row, text="", font=("Segoe UI", 21, "bold")
)
panel_date_label.pack(side="left")


def hide_panel():
    global panel_visible
    panel.pack_forget()
    panel_visible = False


def show_panel():
    global panel_visible
    if not panel_visible:
        panel.pack(side="right", fill="y")
        panel_visible = True


close_btn = ctk.CTkButton(
    panel_header_row, text="\u2715", width=30, height=30, corner_radius=15,
    fg_color=INPUT_BG, hover_color="#2A1414", text_color=MUTED,
    hover=True, font=("Segoe UI", 13), command=hide_panel
)
close_btn.pack(side="right")

panel_summary = ctk.CTkLabel(
    panel_scroll, text="", font=("Segoe UI", 13), text_color=MUTED, justify="left"
)
panel_summary.pack(anchor="w", pady=(2, 16))

trades_list_frame = ctk.CTkFrame(panel_scroll, fg_color="transparent")
trades_list_frame.pack(fill="x", pady=(0, 4))


def section_label(parent, text):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(22, 12))

    ctk.CTkFrame(row, width=3, height=16, fg_color=ACCENT, corner_radius=2).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(row, text=text, font=("Segoe UI", 15, "bold")).pack(side="left")


section_label(panel_scroll, "Add Trade")


def field_label(parent, text):
    ctk.CTkLabel(
        parent, text=text.upper(), font=("Segoe UI", 10, "bold"), text_color=MUTED
    ).pack(anchor="w", pady=(0, 4))


def labeled_entry(parent, label_text, placeholder=""):
    field_label(parent, label_text)
    entry = ctk.CTkEntry(
        parent, height=38, corner_radius=9, fg_color=INPUT_BG,
        border_width=1, border_color=BORDER, font=("Segoe UI", 13.5),
        placeholder_text=placeholder
    )
    entry.pack(fill="x")
    return entry


def field_pair(parent, spec_a, spec_b):
    """spec_a / spec_b: (label, placeholder). Returns the two entry widgets, side by side."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(10, 0))
    row.grid_columnconfigure(0, weight=1, uniform="pair")
    row.grid_columnconfigure(1, weight=1, uniform="pair")

    col_a = ctk.CTkFrame(row, fg_color="transparent")
    col_a.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
    col_b = ctk.CTkFrame(row, fg_color="transparent")
    col_b.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

    label_a, ph_a = spec_a
    label_b, ph_b = spec_b

    field_label(col_a, label_a)
    entry_a = ctk.CTkEntry(
        col_a, height=38, corner_radius=9, fg_color=INPUT_BG,
        border_width=1, border_color=BORDER, font=("Segoe UI", 13.5), placeholder_text=ph_a
    )
    entry_a.pack(fill="x")

    field_label(col_b, label_b)
    entry_b = ctk.CTkEntry(
        col_b, height=38, corner_radius=9, fg_color=INPUT_BG,
        border_width=1, border_color=BORDER, font=("Segoe UI", 13.5), placeholder_text=ph_b
    )
    entry_b.pack(fill="x")

    return entry_a, entry_b


# Symbol + Side (side is a segmented toggle, not a plain entry, so built separately)
symbol_side_row = ctk.CTkFrame(panel_scroll, fg_color="transparent")
symbol_side_row.pack(fill="x", pady=(10, 0))
symbol_side_row.grid_columnconfigure(0, weight=1, uniform="ss")
symbol_side_row.grid_columnconfigure(1, weight=1, uniform="ss")

symbol_col = ctk.CTkFrame(symbol_side_row, fg_color="transparent")
symbol_col.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
side_col = ctk.CTkFrame(symbol_side_row, fg_color="transparent")
side_col.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

field_label(symbol_col, "Symbol")
symbol_entry = ctk.CTkEntry(
    symbol_col, height=38, corner_radius=9, fg_color=INPUT_BG,
    border_width=1, border_color=BORDER, font=("Segoe UI", 13.5), placeholder_text="MES"
)
symbol_entry.pack(fill="x")

field_label(side_col, "Side")
side_var = ctk.StringVar(value="Long")
side_toggle = ctk.CTkSegmentedButton(
    side_col, values=["Long", "Short"], variable=side_var, height=38, corner_radius=9,
    fg_color=INPUT_BG, selected_color=ACCENT, selected_hover_color="#16A34A",
    unselected_hover_color="#232B38", font=("Segoe UI", 13, "bold")
)
side_toggle.pack(fill="x")

entry_price_entry, exit_price_entry = field_pair(
    panel_scroll, ("Entry Price", "5200.25"), ("Exit Price", "5210.50")
)
size_entry, pnl_entry = field_pair(
    panel_scroll, ("Size", "2"), ("P&L ($)", "auto-filled")
)

field_label_notes_wrap = ctk.CTkFrame(panel_scroll, fg_color="transparent")
field_label_notes_wrap.pack(fill="x", pady=(16, 0))
field_label(field_label_notes_wrap, "Notes")

notes_box = ctk.CTkTextbox(
    panel_scroll, height=72, corner_radius=9, fg_color=INPUT_BG,
    border_color=BORDER, border_width=1, font=("Segoe UI", 13.5)
)
notes_box.pack(fill="x")

tags_entry = labeled_entry(panel_scroll, "Tags (comma separated)", "breakout, morning")


def compute_pnl_from_fields():
    try:
        entry_p = float(entry_price_entry.get())
        exit_p = float(exit_price_entry.get())
        size = float(size_entry.get())
    except ValueError:
        return None

    direction = 1 if side_var.get() == "Long" else -1
    return (exit_p - entry_p) * size * direction


def autofill_pnl(*_):
    pnl = compute_pnl_from_fields()
    if pnl is None:
        return
    pnl_entry.delete(0, "end")
    pnl_entry.insert(0, f"{pnl:.2f}")


entry_price_entry.bind("<KeyRelease>", autofill_pnl)
entry_price_entry.bind("<FocusOut>", autofill_pnl)
exit_price_entry.bind("<KeyRelease>", autofill_pnl)
exit_price_entry.bind("<FocusOut>", autofill_pnl)
size_entry.bind("<KeyRelease>", autofill_pnl)
size_entry.bind("<FocusOut>", autofill_pnl)
side_toggle.configure(command=lambda _: autofill_pnl())


def clear_form():
    symbol_entry.delete(0, "end")
    entry_price_entry.delete(0, "end")
    exit_price_entry.delete(0, "end")
    size_entry.delete(0, "end")
    pnl_entry.delete(0, "end")
    notes_box.delete("1.0", "end")
    tags_entry.delete(0, "end")
    side_var.set("Long")


def flash_invalid(entry_widget):
    entry_widget.configure(border_color=RED)
    root.after(1000, lambda: entry_widget.configure(border_color=BORDER))


def save_toast(message, error=False):
    color = RED if error else GREEN
    bg = RED_BG if error else GREEN_BG
    toast = ctk.CTkLabel(
        panel, text=message, font=("Segoe UI", 12, "bold"),
        fg_color=bg, text_color=color, corner_radius=8, height=30
    )
    toast.place(relx=0.5, y=8, anchor="n")
    root.after(1800, toast.destroy)


def add_trade():
    global current_panel_date

    if not current_panel_date:
        return

    symbol = symbol_entry.get().strip() or "\u2014"

    entry_p = exit_p = size = None
    try:
        entry_p = float(entry_price_entry.get())
        exit_p = float(exit_price_entry.get())
        size = float(size_entry.get())
    except ValueError:
        pass

    # Try the typed P&L first; fall back to computing it from
    # entry/exit/size right here, instead of relying only on the
    # earlier reactive auto-fill (which could be skipped/missed).
    pnl = None
    pnl_raw = pnl_entry.get().strip()
    if pnl_raw:
        try:
            pnl = float(pnl_raw)
        except ValueError:
            pnl = None

    if pnl is None:
        pnl = compute_pnl_from_fields()

    if pnl is None:
        flash_invalid(pnl_entry)
        save_toast("Enter a P&L, or fill Entry/Exit/Size", error=True)
        return

    tags_raw = tags_entry.get().strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    trade = {
        "symbol": symbol,
        "side": side_var.get(),
        "entry_price": entry_p,
        "exit_price": exit_p,
        "size": size,
        "pnl": pnl,
        "notes": notes_box.get("1.0", "end").strip(),
        "tags": tags
    }

    trades_data.setdefault(current_panel_date, []).append(trade)
    save_trades()

    clear_form()
    refresh_panel_trades(current_panel_date)
    redraw_current()
    save_toast("Trade saved")


save_trade_btn = ctk.CTkButton(
    panel_scroll, text="Save Trade", height=46, corner_radius=11,
    fg_color=ACCENT, text_color="#05210F", hover_color="#16A34A",
    font=("Segoe UI", 15, "bold"), command=add_trade
)
save_trade_btn.pack(fill="x", pady=(22, 4))


def delete_trade(date_str, index):
    trades = trades_data.get(date_str, [])
    if 0 <= index < len(trades):
        trades.pop(index)
        if not trades:
            trades_data.pop(date_str, None)
        save_trades()
    refresh_panel_trades(date_str)
    redraw_current()


def refresh_panel_trades(date_str):
    for w in trades_list_frame.winfo_children():
        w.destroy()

    trades = get_day_trades(date_str)

    stats = day_stats(date_str)
    if stats:
        pnl, win_rate, count = stats
        sign = "" if pnl >= 0 else "-"
        panel_summary.configure(
            text=f"{count} trade{'s' if count != 1 else ''}  \u2022  {sign}${abs(pnl):,.2f}  \u2022  {win_rate}% win rate"
        )
    else:
        panel_summary.configure(text="No trades logged yet")

    if not trades:
        ctk.CTkLabel(
            trades_list_frame, text="Nothing here yet.",
            text_color=MUTED, font=("Segoe UI", 13)
        ).pack(pady=6, anchor="w")
        return

    for i, t in enumerate(trades):
        sign = "" if t["pnl"] >= 0 else "-"
        pnl_color = GREEN if t["pnl"] >= 0 else RED

        card = ctk.CTkFrame(
            trades_list_frame, fg_color=INPUT_BG, corner_radius=10,
            border_width=1, border_color=BORDER
        )
        card.pack(fill="x", pady=5)

        # colored accent strip so wins/losses are scannable at a glance
        ctk.CTkFrame(card, width=4, fg_color=pnl_color, corner_radius=0).pack(side="left", fill="y")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True)

        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(11, 2))

        del_btn = ctk.CTkButton(
            top_row, text="\u2715", width=24, height=24, corner_radius=12,
            fg_color="transparent", hover_color="#2A1111", text_color=MUTED,
            font=("Segoe UI", 11), command=lambda i=i, ds=date_str: delete_trade(ds, i)
        )
        del_btn.pack(side="right")

        ctk.CTkLabel(
            top_row, text=f"{sign}${abs(t['pnl']):,.2f}",
            font=("Segoe UI", 14, "bold"), text_color=pnl_color
        ).pack(side="right", padx=(0, 8))

        ctk.CTkLabel(
            top_row, text=f"{t['symbol']}  \u00b7  {t.get('side', '\u2014')}",
            font=("Segoe UI", 13.5, "bold")
        ).pack(side="left")

        if t.get("entry_price") is not None and t.get("exit_price") is not None:
            ctk.CTkLabel(
                content,
                text=f"Entry {t['entry_price']}  \u2192  Exit {t['exit_price']}  \u2022  Size {t.get('size', '\u2014')}",
                font=("Segoe UI", 11), text_color=MUTED
            ).pack(anchor="w", padx=14)

        if t.get("notes"):
            ctk.CTkLabel(
                content, text=t["notes"], font=("Segoe UI", 11),
                text_color=TEXT, wraplength=290, justify="left"
            ).pack(anchor="w", padx=14, pady=(5, 0))

        if t.get("tags"):
            ctk.CTkLabel(
                content, text="  ".join(f"#{tag}" for tag in t["tags"]),
                font=("Segoe UI", 11), text_color=ACCENT
            ).pack(anchor="w", padx=14, pady=(5, 0))

        ctk.CTkFrame(content, height=1, fg_color="transparent").pack(pady=(0, 11))


def select_day(date_str):
    global current_panel_date
    current_panel_date = date_str

    display_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    panel_date_label.configure(text=display_date)

    clear_form()
    refresh_panel_trades(date_str)
    show_panel()


# =====================
# UPDATE CHECKER (GitHub Releases API)
# =====================

def fetch_latest_release():
    """Runs on a background thread. Returns a dict, never raises to the caller.

    Uses the /releases list endpoint (not /releases/latest) because "latest"
    specifically excludes pre-releases and drafts -- if your newest tag is
    marked Pre-release on GitHub, /latest 404s even though the release exists.
    The list endpoint returns newest-first, so we just take the first entry."""
    token = app_config.get("github_token", "").strip()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=5"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{APP_NAME}-updater")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            releases = json.loads(resp.read().decode())

        if not releases:
            return {"ok": False, "error": "No releases published yet"}

        # skip drafts (unpublished), keep pre-releases -- first non-draft is newest
        data = next((r for r in releases if not r.get("draft")), None)
        if data is None:
            return {"ok": False, "error": "No published releases found"}

        latest_tag = data.get("tag_name", "")
        return {
            "ok": True,
            "latest": latest_tag,
            "url": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
            "notes": data.get("body", "") or ""
        }
    except urllib.error.HTTPError as e:
        if e.code == 401:
            msg = "Token invalid or expired"
        elif e.code == 404:
            msg = "Repo not found (check repo name / token access)"
        else:
            msg = f"GitHub error {e.code}"
        return {"ok": False, "error": msg}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_for_updates_async(on_done, silent=False):
    """Fetches in a background thread, then hands the result back on the main thread."""

    def worker():
        result = fetch_latest_release()
        root.after(0, lambda: on_done(result, silent))

    threading.Thread(target=worker, daemon=True).start()


def download_and_install_update(tag):
    """Pulls trade_journal.py from the given release tag via the GitHub Contents API
    and overwrites the running script. Runs on a background thread -- do file I/O only,
    no Tkinter calls in here."""

    if getattr(sys, "frozen", False):
        raise RuntimeError("Self-update only works when run as a .py script, not a packaged .exe")

    token = app_config.get("github_token", "").strip()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/trade_journal.py?ref={tag}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{APP_NAME}-updater")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())

    content_b64 = payload.get("content", "")
    if not content_b64:
        raise RuntimeError("GitHub returned an empty file")

    new_source = base64.b64decode(content_b64)
    if len(new_source) < 200:  # sanity check -- a real script is way bigger than this
        raise RuntimeError("Downloaded file looked incomplete, aborted before overwriting")

    script_path = os.path.abspath(__file__)
    backup_path = script_path + ".bak"

    with open(script_path, "rb") as f:
        current_source = f.read()
    with open(backup_path, "wb") as f:
        f.write(current_source)  # kept in case the new version has a problem

    with open(script_path, "wb") as f:
        f.write(new_source)


def relaunch_app():
    """Starts a fresh copy of the (now-updated) script, then closes this one."""
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__)])
    except Exception:
        pass
    root.destroy()
    os._exit(0)


def install_update_async(tag, on_error):
    def worker():
        try:
            download_and_install_update(tag)
            root.after(0, relaunch_app)
        except Exception as e:
            root.after(0, lambda: on_error(str(e)))

    threading.Thread(target=worker, daemon=True).start()


def maybe_auto_check_on_launch():
    if not app_config.get("auto_check_updates", True):
        return

    def handle_result(result, silent):
        if not result.get("ok"):
            return  # stay quiet on launch if the check fails
        latest = result["latest"]
        latest_clean = latest.lstrip("vV")
        if version_tuple(latest_clean) > version_tuple(APP_VERSION):
            if app_config.get("last_dismissed_version") == latest:
                return
            show_update_banner(latest, result["url"])

    check_for_updates_async(handle_result, silent=True)


update_banner = None


def show_update_banner(latest_version, release_url):
    global update_banner
    if update_banner is not None:
        return

    update_banner = ctk.CTkFrame(root, fg_color="#14210F", corner_radius=0, height=44)
    update_banner.pack(side="top", fill="x", before=header)
    update_banner.pack_propagate(False)

    banner_label = ctk.CTkLabel(
        update_banner, text=f"A new version ({latest_version}) is available.",
        font=("Segoe UI", 12, "bold"), text_color=GREEN
    )
    banner_label.pack(side="left", padx=(20, 10))

    update_btn = ctk.CTkButton(
        update_banner, text="Update Now", width=110, height=28, corner_radius=7,
        fg_color=ACCENT, text_color="#05210F", hover_color="#16A34A",
        font=("Segoe UI", 11, "bold")
    )
    update_btn.pack(side="left")

    def handle_install_error(msg):
        update_btn.configure(state="normal", text="Update Now")
        banner_label.configure(
            text=f"Update failed ({msg}) \u2014 try again or open it on GitHub instead.",
            text_color=RED
        )
        retry_link.pack(side="left", padx=(10, 0))

    def start_install():
        update_btn.configure(state="disabled", text="Installing...")
        banner_label.configure(text=f"Installing version {latest_version}...", text_color=GREEN)
        install_update_async(latest_version, handle_install_error)

    update_btn.configure(command=start_install)

    retry_link = ctk.CTkButton(
        update_banner, text="Open on GitHub", width=120, height=28, corner_radius=7,
        fg_color="transparent", border_width=1, border_color="#3A4252",
        hover_color="#1E2A17", font=("Segoe UI", 11),
        command=lambda: webbrowser.open(release_url)
    )
    # not packed by default -- only shown if the one-click install fails

    def dismiss():
        app_config["last_dismissed_version"] = latest_version
        save_config(app_config)
        update_banner.pack_forget()

    ctk.CTkButton(
        update_banner, text="\u2715", width=28, height=28, corner_radius=14,
        fg_color="transparent", hover_color="#1E2A17", text_color=MUTED,
        font=("Segoe UI", 12), command=dismiss
    ).pack(side="right", padx=14)


# Built once, toggled with place()/place_forget() -- an in-app card, never a
# separate OS window. The GitHub token itself still lives in config.json and
# is used for API calls, it's just not shown/edited in this UI.

settings_card = ctk.CTkFrame(
    root, width=380, fg_color=CARD, corner_radius=14,
    border_width=1, border_color=BORDER
)
settings_visible = False

settings_status_label = None
settings_check_btn = None


def hide_settings():
    global settings_visible
    settings_card.place_forget()
    settings_visible = False


def toggle_settings():
    global settings_visible
    if settings_visible:
        hide_settings()
    else:
        settings_card.place(relx=1.0, rely=0.0, x=-30, y=95, anchor="ne")
        settings_card.lift()
        settings_visible = True


def _build_settings_card():
    global settings_status_label, settings_check_btn

    wrap = ctk.CTkFrame(settings_card, fg_color="transparent")
    wrap.pack(fill="both", expand=True, padx=20, pady=18)

    top_row = ctk.CTkFrame(wrap, fg_color="transparent")
    top_row.pack(fill="x", pady=(0, 16))
    ctk.CTkLabel(top_row, text="Settings", font=("Segoe UI", 17, "bold")).pack(side="left")
    ctk.CTkButton(
        top_row, text="\u2715", width=26, height=26, corner_radius=13,
        fg_color=INPUT_BG, hover_color="#2A1414", text_color=MUTED,
        font=("Segoe UI", 12), command=hide_settings
    ).pack(side="right")

    # --- Version row ---
    version_row = ctk.CTkFrame(wrap, fg_color=INPUT_BG, corner_radius=9, border_width=1, border_color=BORDER)
    version_row.pack(fill="x", pady=(0, 10))
    v_inner = ctk.CTkFrame(version_row, fg_color="transparent")
    v_inner.pack(fill="x", padx=14, pady=12)
    ctk.CTkLabel(v_inner, text="Version", font=("Segoe UI", 13, "bold")).pack(side="left")
    ctk.CTkLabel(v_inner, text=APP_VERSION, font=("Segoe UI", 13), text_color=MUTED).pack(side="right")

    # --- Auto-update row ---
    auto_row = ctk.CTkFrame(wrap, fg_color=INPUT_BG, corner_radius=9, border_width=1, border_color=BORDER)
    auto_row.pack(fill="x", pady=(0, 10))
    a_inner = ctk.CTkFrame(auto_row, fg_color="transparent")
    a_inner.pack(fill="x", padx=14, pady=12)
    ctk.CTkLabel(a_inner, text="Check for updates on launch", font=("Segoe UI", 13, "bold")).pack(side="left")

    auto_var = ctk.BooleanVar(value=app_config.get("auto_check_updates", True))

    def toggle_auto():
        app_config["auto_check_updates"] = auto_var.get()
        save_config(app_config)

    ctk.CTkSwitch(
        a_inner, text="", variable=auto_var, command=toggle_auto,
        progress_color=ACCENT, button_color="#E5E7EB", width=40
    ).pack(side="right")

    # --- Check now row ---
    check_row = ctk.CTkFrame(wrap, fg_color=INPUT_BG, corner_radius=9, border_width=1, border_color=BORDER)
    check_row.pack(fill="x", pady=(0, 4))
    c_inner = ctk.CTkFrame(check_row, fg_color="transparent")
    c_inner.pack(fill="x", padx=14, pady=12)

    settings_status_label = ctk.CTkLabel(c_inner, text="", font=("Segoe UI", 11), text_color=MUTED, wraplength=180, justify="left")
    settings_status_label.pack(side="left")

    def handle_check_result(result, silent):
        settings_check_btn.configure(state="normal", text="Check Now")

        if not result.get("ok"):
            settings_status_label.configure(text=result.get("error", "Check failed"), text_color=RED)
            return

        latest = result["latest"]
        latest_clean = latest.lstrip("vV")

        if version_tuple(latest_clean) > version_tuple(APP_VERSION):
            settings_status_label.configure(text=f"Update available: {latest}", text_color=GREEN)
            show_update_banner(latest, result["url"])
        else:
            settings_status_label.configure(text="You're up to date", text_color=MUTED)

    def run_check():
        settings_check_btn.configure(state="disabled", text="Checking...")
        settings_status_label.configure(text="")
        check_for_updates_async(handle_check_result, silent=False)

    settings_check_btn = ctk.CTkButton(
        c_inner, text="Check Now", width=100, height=30, corner_radius=8,
        fg_color=ACCENT, text_color="#05210F", hover_color="#16A34A",
        font=("Segoe UI", 12, "bold"), command=run_check
    )
    settings_check_btn.pack(side="right")


_build_settings_card()


# =====================
# INIT
# =====================

redraw_current()
root.after(1200, maybe_auto_check_on_launch)  # slight delay so it doesn't block first paint

root.mainloop()