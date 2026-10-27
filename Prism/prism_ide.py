import tkinter as tk
from tkinter import scrolledtext, messagebox, Menu, filedialog, simpledialog
import re
import os
import sys

PREBUILT_LIBRARY_NAMES = {"wc": "WC", "bitwin": "Bitwin"}


def get_library_directory():
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(app_data, "Prism", "libraries")


def install_library(name):
    canonical_name = PREBUILT_LIBRARY_NAMES.get(name.lower())
    if canonical_name is None:
        raise ValueError(
            f"Unknown library '{name}'. Available libraries: WC, Bitwin."
        )

    bundle_directory = getattr(
        sys,
        "_MEIPASS",
        os.path.dirname(os.path.abspath(__file__))
    )
    source_path = os.path.join(bundle_directory, "libraries", f"{canonical_name}.prism")
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Prebuilt library package not found: {source_path}")

    install_directory = get_library_directory()
    os.makedirs(install_directory, exist_ok=True)
    destination_path = os.path.join(install_directory, f"{canonical_name}.prism")
    with open(source_path, "r", encoding="utf-8") as package:
        package_contents = package.read()
    with open(destination_path, "w", encoding="utf-8") as package:
        package.write(package_contents)
    return destination_path


class PrismInterpreter:
    def __init__(self, root_tk, output_callback, settings_provider):
        self.root_tk = root_tk
        self.owns_root_tk = False
        self.output_callback = output_callback
        self.settings_provider = settings_provider # Access IDE settings (e.g. show_comments)
        self.variables = {}
        self.functions = {}
        self.classes = {} # Stores user-defined classes
        self.key_functions = {}
        self.windows = {} # Stores active GUI windows & canvases
        self.persistent_store = {} # Simulates database store
        self.loaded_libraries = set()

    def log(self, text):
        self.output_callback(text + "\n")

    def get_root_tk(self):
        if self.root_tk is None:
            # Create a hidden root window for CLI GUI operations if needed
            self.root_tk = tk.Tk()
            self.root_tk.withdraw()
            self.owns_root_tk = True
        return self.root_tk

    def create_toplevel(self, parent):
        window = tk.Toplevel(parent)
        if self.owns_root_tk:
            window.bind("<Destroy>", self.close_cli_root_when_last_window_closes, add="+")
        return window

    def close_cli_root_when_last_window_closes(self, event):
        if self.root_tk is None:
            return

        for window_data in self.windows.values():
            try:
                if window_data["window"].winfo_exists():
                    return
            except tk.TclError:
                continue

        self.root_tk.after_idle(self.root_tk.destroy)

    def run(self, code):
        self.variables.clear()
        self.functions.clear()
        self.classes.clear()
        self.key_functions.clear()
        self.persistent_store.clear()
        self.loaded_libraries.clear()
        
        # Close any lingering windows from previous runs
        for w_data in self.windows.values():
            try:
                w_data["window"].destroy()
            except:
                pass
        self.windows.clear()

        lines = code.split('\n')
        self.execute_block(lines)

    def execute_block(self, lines):
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("#"): # Skip blank lines and standalone compiler comments
                i += 1
                continue
            
            # 1. Comments: c.comment("...")
            if line.startswith("c.comment("):
                if self.settings_provider().get("show_comments", False):
                    match = re.search(r'c\.comment\((.*?)\)', line)
                    if match:
                        cmt_text = match.group(1).strip('"\'')
                        self.log(f"[Comment]: {cmt_text}")
                i += 1
                continue

            # 2. Installed prebuilt libraries: library.use;[WC|Bitwin]
            elif line.lower().startswith("library.use;"):
                match = re.fullmatch(r'library\.use;\[(.*?)\]', line, re.IGNORECASE)
                if not match:
                    raise ValueError("Invalid library syntax. Use library.use;[WC] or library.use;[Bitwin].")
                requested_name = match.group(1)
                library_name = PREBUILT_LIBRARY_NAMES.get(requested_name.lower())
                if library_name is None:
                    raise ValueError(f"Unknown library '{requested_name}'. Available libraries: WC, Bitwin.")
                package_path = os.path.join(get_library_directory(), f"{library_name}.prism")
                if not os.path.isfile(package_path):
                    raise FileNotFoundError(
                        f"Library '{library_name}' is not installed. Run 'prism install {library_name}' first."
                    )
                self.loaded_libraries.add(library_name)
                self.log(f"Library loaded: {library_name}")

            # Bitwin runs UTF-8 Prism source encoded as hexadecimal.
            elif line.lower().startswith("bitwin.run;"):
                if "Bitwin" not in self.loaded_libraries:
                    raise RuntimeError("Bitwin is not loaded. Add library.use;[Bitwin] before using it.")
                match = re.fullmatch(r'bitwin\.run;\[(.*?)\]', line, re.IGNORECASE)
                if not match:
                    raise ValueError("Invalid Bitwin syntax. Use bitwin.run;[hex_encoded_prism_source].")
                hex_source = match.group(1)
                if not hex_source or len(hex_source) % 2 or not re.fullmatch(r'[0-9a-fA-F]+', hex_source):
                    raise ValueError("Bitwin input must be a non-empty, even-length hexadecimal string.")
                try:
                    decoded_source = bytes.fromhex(hex_source).decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ValueError("Bitwin hex must decode to valid UTF-8 Prism source.") from error
                self.execute_block(decoded_source.splitlines())

            # Window Customization (WC) operations.
            elif line.lower().startswith("wc.window."):
                if "WC" not in self.loaded_libraries:
                    raise RuntimeError("WC is not loaded. Add library.use;[WC] before using it.")
                match = re.fullmatch(
                    r'wc\.window\.(title|background|size);\s*\((.*?)\);\s*\((.*?)\)(?:;\s*\((.*?)\))?',
                    line,
                    re.IGNORECASE
                )
                if not match:
                    raise ValueError(
                        'Invalid WC syntax. Use wc.window.title;(Window);("Title"), '
                        'wc.window.background;(Window);(#RRGGBB), or '
                        'wc.window.size;(Window);(width);(height).'
                    )
                operation, window_name, first_value, second_value = match.groups()
                window_name = window_name.strip().strip('"\'')
                if window_name not in self.windows:
                    raise ValueError(f"WC window '{window_name}' does not exist.")
                window_data = self.windows[window_name]
                if operation.lower() == "title":
                    window_data["window"].title(first_value.strip().strip('"\''))
                elif operation.lower() == "background":
                    color = first_value.strip().strip('"\'')
                    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                        raise ValueError("WC background color must be a six-digit hex color such as #336699.")
                    window_data["window"].configure(bg=color)
                    window_data["canvas"].configure(bg=color)
                else:
                    if second_value is None:
                        raise ValueError("WC window size requires both width and height.")
                    try:
                        width = int(first_value.strip())
                        height = int(second_value.strip())
                    except ValueError as error:
                        raise ValueError("WC window size must use positive integer dimensions.") from error
                    if width <= 0 or height <= 0:
                        raise ValueError("WC window size must use positive integer dimensions.")
                    window_data["window"].geometry(f"{width}x{height}")

            # 3. Class Definition: c.create.new.type((class); ("class_name")); {
            elif line.startswith("c.create.new.type("):
                match = re.search(r'c\.create\.new\.type\(\(class\);\s*\([\"\']?(.*?)[\"\']?\);\s*\{?', line)
                if match:
                    class_name = match.group(1).strip()
                    class_lines = []
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.strip() == "}":
                            i += 1
                            break
                        elif next_line.startswith("     ") or next_line.startswith("\t") or next_line.startswith("  "):
                            class_lines.append(next_line.strip())
                            i += 1
                        else:
                            break
                    self.classes[class_name] = class_lines
                    self.persistent_store[class_name] = {"type": "class", "lines": class_lines}
                    self.log(f"Class Defined & Registered: '{class_name}'")
                    continue

            # 3. Variable Definition: h.func.define;[var]
            elif line.startswith("h.func.define;"):
                match = re.search(r'h\.func\.define;\[(.*?)\]', line)
                if match:
                    var_name = match.group(1)
                    self.variables[var_name] = None
            
            # 4. Variable Change: h.change;variable:[var];[val]
            elif line.startswith("h.change;variable:"):
                match = re.search(r'h\.change;variable:\[(.*?)\];\[(.*?)\]', line)
                if match:
                    var_name = match.group(1)
                    val = match.group(2)
                    try:
                        if '.' in val:
                            val = float(val)
                        else:
                            val = int(val)
                    except ValueError:
                        pass
                    self.variables[var_name] = val

            # 5. User Input Prompt: askuser.h.func.input;[var]=("Prompt?")
            elif line.startswith("askuser.h.func.input;"):
                match = re.search(r'askuser\.h\.func\.input;\[(.*?)\]=\("(.*?)"\)', line)
                if match:
                    var_name = match.group(1)
                    prompt_text = match.group(2)
                    if self.root_tk is not None and hasattr(self.root_tk, "winfo_exists"):
                        user_val = simpledialog.askstring("Prism Input", prompt_text, parent=self.root_tk)
                    else:
                        user_val = input(prompt_text)
                    
                    if user_val is not None:
                        try:
                            if '.' in user_val:
                                user_val = float(user_val)
                            else:
                                user_val = int(user_val)
                        except ValueError:
                            pass
                        self.variables[var_name] = user_val
                        self.log(f"User Input stored in [{var_name}]: {user_val}")

            # 6. Printline
            elif line.startswith("h.printline;"):
                content = line[len("h.printline;"):].strip()
                if content.startswith('"') and content.endswith('"'):
                    self.log(content[1:-1])
                elif content.startswith('[') and content.endswith(']'):
                    var_name = content[1:-1]
                    self.log(str(self.variables.get(var_name, f"Undefined variable: {var_name}")))
                elif content.startswith("get.store."):
                    match = re.search(r'get\.store\.(list|array);\s*item\("(.*?)"\)', content)
                    if match:
                        stype = match.group(1)
                        item_name = match.group(2)
                        self.log(f"[Retrieved {stype.upper()} Item]: '{item_name}'")
                    else:
                        self.log(content)
                else:
                    self.log(content)

            # 7. scan.store
            elif line.startswith("scan.store"):
                self.log("\n--- [SCAN.STORE] DATABASE DUMP ---")
                if not self.persistent_store and not self.variables and not self.classes:
                    self.log("(Store & Memory are currently empty)")
                else:
                    if self.variables:
                        self.log("Variables:")
                        for vk, vv in self.variables.items():
                            self.log(f"  [{vk}] = {vv}")
                    if self.classes:
                        self.log("Defined Classes:")
                        for ck in self.classes.keys():
                            self.log(f"  [Class] -> {ck}")
                    if self.persistent_store:
                        self.log("Persistent Store Database:")
                        for sk, sv in self.persistent_store.items():
                            self.log(f"  Stored Asset: [{sk}] -> {sv}")
                self.log("------------------------------------\n")

            # 8. GUI Window Creation: display.h.window.show; (x); (y); (z); (window_name)
            elif line.startswith("display.h.window.show;"):
                match = re.findall(r'\((.*?)\)', line)
                if len(match) >= 4:
                    width = self.get_val(match[0])
                    height = self.get_val(match[1])
                    z_val = self.get_val(match[2])
                    w_name = match[3].strip()
                    try:
                        r = self.get_root_tk()
                        win = self.create_toplevel(r)
                        win.title(w_name)
                        win.geometry(f"{width}x{height}")
                        win.configure(bg="#ffffff")
                        canvas = tk.Canvas(win, bg="#ffffff", highlightthickness=0)
                        canvas.pack(fill=tk.BOTH, expand=True)
                        win.focus_set()
                        win.focus_force()
                        self.windows[w_name] = {"window": win, "canvas": canvas, "shapes": {}, "coords": {}}
                        self.persistent_store[w_name] = {"type": "window", "object": str(w_name)}
                        self.log(f"GUI Window Created & Stored: '{w_name}' ({width}x{height})")
                    except Exception as e:
                        self.log(f"Window Error: {e}")

            # 9. GUI 2D Shape Drawing: display.window(window name); draw(...); (x); (y); (z); (shape_name)
            elif "display.window(" in line and "draw(" in line:
                match = re.search(r'display\.window\((.*?)\);\s*draw\((.*?):\s*(.*?)\);\s*\((.*?)\);\s*\((.*?)\);\s*\((.*?)\);\s*\((.*?)\)', line)
                if match:
                    w_name = match.group(1).strip()
                    stype = match.group(3).strip().lower()
                    px = self.get_val(match[4])
                    py = self.get_val(match[5])
                    pz = self.get_val(match[6])
                    shape_name = match.group(7).strip()
                    
                    if w_name not in self.windows:
                        r = self.get_root_tk()
                        win = self.create_toplevel(r)
                        win.title(w_name)
                        win.geometry("500x400")
                        win.configure(bg="#ffffff")
                        canvas = tk.Canvas(win, bg="#ffffff", highlightthickness=0)
                        canvas.pack(fill=tk.BOTH, expand=True)
                        win.focus_set()
                        win.focus_force()
                        self.windows[w_name] = {"window": win, "canvas": canvas, "shapes": {}, "coords": {}}

                    w_data = self.windows[w_name]
                    canvas = w_data["canvas"]
                    
                    size = 50 + (pz * 10)
                    item_id = None
                    if stype == "circle":
                        item_id = canvas.create_oval(px, py, px + size, py + size, fill="#0d6efd", outline="#084298", width=2, tags=shape_name)
                    elif stype == "square":
                        item_id = canvas.create_rectangle(px, py, px + size, py + size, fill="#198754", outline="#0f5132", width=2, tags=shape_name)
                    elif stype == "triangle":
                        half = size / 2
                        item_id = canvas.create_polygon(px + half, py, px, py + size, px + size, py + size, fill="#ffc107", outline="#d39e00", width=2, tags=shape_name)
                    elif stype == "rectangle":
                        item_id = canvas.create_rectangle(px, py, px + size * 1.5, py + size, fill="#dc3545", outline="#b02a37", width=2, tags=shape_name)
                    else:
                        item_id = canvas.create_rectangle(px, py, px + size, py + size, fill="#6c757d", outline="#495057", width=2, tags=shape_name)
                        
                    w_data["shapes"][shape_name] = item_id
                    w_data["coords"][shape_name] = {"x": px, "y": py, "z": pz, "size": size}
                    self.persistent_store[shape_name] = {"type": "shape", "window": w_name, "id": str(item_id)}
                    self.log(f"GUI Shape Drawn: '{shape_name}' ({stype}) on '{w_name}' at ({px}, {py})")

            # 10. Draw a selectable grid of 3D shapes:
            # 3D.raycast.shapes; (columns x rows); (cube|sphere|cylinder|pyramid);
            elif line.lower().startswith("3d.raycast.shapes"):
                match = re.fullmatch(
                    r'3d\.raycast\.shapes\s*;\s*\(\s*(\d+)\s*x\s*(\d+)\s*\)\s*;\s*\(\s*([a-z]+)\s*\)\s*;?',
                    line,
                    re.IGNORECASE
                )
                if not match:
                    raise ValueError(
                        "Invalid 3D raycast syntax. Use "
                        "3D.raycast.shapes; (columns x rows); (cube|sphere|cylinder|pyramid);"
                    )
                columns, rows = int(match.group(1)), int(match.group(2))
                shape_type = match.group(3).lower()
                if not 1 <= columns <= 32 or not 1 <= rows <= 32:
                    raise ValueError("3D raycast grid dimensions must be between 1 and 32.")
                if shape_type not in {"cube", "sphere", "cylinder", "pyramid"}:
                    raise ValueError(
                        f"Unsupported 3D raycast shape '{shape_type}'. "
                        "Choose cube, sphere, cylinder, or pyramid."
                    )
                self.draw_raycast_grid(columns, rows, shape_type)

            # 3D Wolfenstein-style raycast map:
            # 3D.raycast.wolfensteinformula.shapes; (map_pattern); (columns x rows);
            elif line.lower().startswith("3d.raycast.wolfensteinformula.shapes"):
                # Accept a map pattern (string) and a grid size; the pattern repeats to fill the map
                match = re.fullmatch(
                    r'3d\.raycast\.wolfensteinformula\.shapes\s*;\s*\(\s*(.*?)\s*\)\s*;\s*\(\s*(\d+)\s*x\s*(\d+)\s*\)\s*;?',
                    line,
                    re.IGNORECASE
                )
                if not match:
                    raise ValueError(
                        "Invalid Wolfenstein raycast syntax. Use: 3D.raycast.wolfensteinformula.shapes; (pattern); (cols x rows);"
                    )
                pattern_raw = match.group(1).strip()
                cols, rows = int(match.group(2)), int(match.group(3))
                if not 1 <= cols <= 64 or not 1 <= rows <= 64:
                    raise ValueError("Wolfenstein grid dimensions must be between 1 and 64.")
                # Remove optional surrounding quotes
                if (pattern_raw.startswith('"') and pattern_raw.endswith('"')) or (
                    pattern_raw.startswith("'") and pattern_raw.endswith("'")
                ):
                    pattern = pattern_raw[1:-1]
                else:
                    pattern = pattern_raw
                if not pattern:
                    raise ValueError("Pattern cannot be empty for wolfenstein raycast map.")
                self.draw_wolfenstein_map(pattern, cols, rows)

            # 11. 3D Shape Rendering with Naming Support: shapes.draw.h.3d.type(...); vector1; ...; endvector; ...; :("shape_name"):
            elif line.startswith("shapes.draw.h.3d.type("):
                match = re.search(r'shapes\.draw\.h\.3d\.type\((.*?)\);\s*vector1;\s*\((.*?)\);\s*\((.*?)\);\s*\((.*?)\);\s*endvector;\s*\((.*?)\);\s*\((.*?)\);\s*\((.*?)\)(?:;\s*:\((?:\"|\')?(.*?)(?:\"|\')?\):)?', line)
                if match:
                    stype = match.group(1).strip().lower()
                    v1_x = self.get_val(match.group(2))
                    v1_y = self.get_val(match.group(3))
                    v1_z = self.get_val(match.group(4))
                    v2_x = self.get_val(match.group(5))
                    v2_y = self.get_val(match.group(6))
                    v2_z = self.get_val(match.group(7))
                    shape_name_raw = match.group(8)
                    
                    shape_name = shape_name_raw.strip('"\'') if shape_name_raw else f"3d_shape_{len(self.persistent_store)}"
                    
                    w_name = "3D_Viewport"
                    w_data = self.ensure_3d_viewport()
                    canvas = w_data["canvas"]
                    
                    depth_offset = v1_z * 10
                    x1 = v1_x + depth_offset
                    y1 = v1_y + depth_offset
                    w = v2_x
                    h = v2_y
                    depth = v2_z * 15
                    
                    if stype == "cube":
                        canvas.create_rectangle(x1, y1, x1 + w, y1 + h, outline="#0dcaf0", width=2, tags=shape_name)
                        canvas.create_rectangle(x1 + depth, y1 - depth, x1 + w + depth, y1 + h - depth, outline="#6f42c1", width=2, tags=shape_name)
                        canvas.create_line(x1, y1, x1 + depth, y1 - depth, fill="#adb5bd", width=2, tags=shape_name)
                        canvas.create_line(x1 + w, y1, x1 + w + depth, y1 - depth, fill="#adb5bd", width=2, tags=shape_name)
                        canvas.create_line(x1, y1 + h, x1 + depth, y1 + h - depth, fill="#adb5bd", width=2, tags=shape_name)
                        canvas.create_line(x1 + w, y1 + h, x1 + w + depth, y1 + h - depth, fill="#adb5bd", width=2, tags=shape_name)
                    elif stype == "sphere":
                        canvas.create_oval(x1, y1, x1 + w, y1 + h, outline="#ffc107", fill="#fd7e14", width=2, tags=shape_name)
                        canvas.create_oval(x1 + (w/4), y1 + (h/4), x1 + (3*w/4), y1 + (3*h/4), outline="#ffeeba", width=1, tags=shape_name)
                    elif stype == "cylinder":
                        canvas.create_oval(x1, y1, x1 + w, y1 + 30, outline="#20c997", width=2, tags=shape_name)
                        canvas.create_rectangle(x1, y1 + 15, x1 + w, y1 + h + 15, outline="#20c997", fill="#0f5132", width=2, tags=shape_name)
                        canvas.create_oval(x1, y1 + h, x1 + w, y1 + h + 30, outline="#20c997", width=2, tags=shape_name)
                    else:
                        canvas.create_rectangle(x1, y1, x1 + w, y1 + h, outline="#d63384", width=2, tags=shape_name)
                        canvas.create_rectangle(x1 + depth, y1 - depth, x1 + w + depth, y1 + h - depth, outline="#d63384", width=2, tags=shape_name)
                        canvas.create_line(x1, y1, x1 + depth, y1 - depth, fill="#d63384", width=2, tags=shape_name)
                        canvas.create_line(x1 + w, y1, x1 + w + depth, y1 - depth, fill="#d63384", width=2, tags=shape_name)

                    w_data["shapes"][shape_name] = shape_name
                    self.persistent_store[shape_name] = {"type": "3d_shape", "window": w_name}
                    self.log(f"3D Render & Named: '{shape_name}' ({stype}) at vector ({v1_x}, {v1_y}, {v1_z})")

            # 11. Shape Position Change: h.change.shape.pos(shape_name); (x); (y); (z);
            elif line.startswith("h.change.shape.pos("):
                match = re.findall(r'\((.*?)\)', line)
                if len(match) >= 4:
                    shape_name = match[0].strip()
                    nx = self.get_val(match[1])
                    ny = self.get_val(match[2])
                    nz = self.get_val(match[3])
                    self.update_shape_position(shape_name, nx, ny, nz)

            # 12. Apply Movement Player: apply.movement.player(shape_name); (w); (a); (s); (d)
            elif line.startswith("apply.movement.player("):
                match = re.search(r'apply\.movement\.player\((.*?)\);(.*)', line)
                if match:
                    shape_name = match.group(1).strip()
                    keys_part = match.group(2)
                    keys = re.findall(r'\((.*?)\)', keys_part)
                    
                    for w_name, w_data in self.windows.items():
                        if shape_name in w_data["shapes"]:
                            win = w_data["window"]
                            win.focus_set()
                            win.focus_force()
                            for k in keys:
                                k_clean = k.strip().lower()
                                win.bind(f"<Key-{k_clean}>", lambda event, sk=shape_name, kc=k_clean: self.handle_key_event(event, sk, kc))
                                win.bind(f"<Key-{k_clean.upper()}>", lambda event, sk=shape_name, kc=k_clean: self.handle_key_event(event, sk, kc))
                                win.bind(f"<{k_clean}>", lambda event, sk=shape_name, kc=k_clean: self.handle_key_event(event, sk, kc))
                            win.bind("<Key>", lambda event, sk=shape_name: self.handle_generic_keypress(event, sk))
                            self.log(f"Movement bound for player shape '{shape_name}' with keys: {keys}")

            # 13. Define Key Function: h.define.display.key.func(key);
            elif line.startswith("h.define.display.key.func;"):
                match = re.search(r'h\.define\.display\.key\.func;\((.*?)\);', line)
                if match:
                    key_name = match.group(1).strip().lower()
                    func_lines = []
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.startswith("     ") or next_line.startswith("\t") or next_line.startswith("  "):
                            func_lines.append(next_line.strip())
                            i += 1
                        else:
                            break
                    self.key_functions[key_name] = func_lines
                    continue

            # 14. Store Reference / Shape Store / Collections
            elif line.startswith("store.") or line.startswith("list.store") or line.startswith("array.store"):
                if line.startswith("store.shape("):
                    match = re.search(r'store\.shape\((.*?)\)', line)
                    if match:
                        s_name = match.group(1).strip()
                        self.persistent_store[s_name] = "shape_record"
                        self.log(f"Store Action: Successfully persisted shape reference '{s_name}'")
                elif line.startswith("store.func("):
                    match = re.search(r'store\.func\((.*?)\)', line)
                    if match:
                        f_name = match.group(1).strip()
                        if f_name in self.functions:
                            self.persistent_store[f_name] = {"type": "function", "lines": self.functions[f_name]}
                            self.log(f"Store Action: Successfully persisted function '{f_name}'")
                elif line.startswith("store."):
                    match = re.search(r'store\.[\(\[]?(.*?)[\)\]]?;?', line)
                    if match:
                        s_name = match.group(1).strip()
                        self.persistent_store[s_name] = "saved_record"
                        self.log(f"Store Action: Successfully stored reference '{s_name}'")
                elif line.startswith("list.store") or line.startswith("array.store"):
                    coll_type = "list" if "list.store" in line else "array"
                    self.persistent_store[f"collection_{len(self.persistent_store)}"] = coll_type
                    self.log(f"Store Action: Persisted in-memory {coll_type} to database store.")

            # 15. Display Text on Window: show.text.display.h; (window_name); (x); (y); (z); ("Text")
            elif line.startswith("show.text.display.h;"):
                match = re.findall(r'\((.*?)\)', line)
                if len(match) >= 5:
                    w_name = match[0].strip()
                    px = self.get_val(match[1])
                    py = self.get_val(match[2])
                    pz = self.get_val(match[3])
                    txt_raw = match[4].strip()
                    
                    if txt_raw.startswith('"') and txt_raw.endswith('"'):
                        txt_val = txt_raw[1:-1]
                    elif txt_raw.startswith('[') and txt_raw.endswith(']'):
                        txt_val = str(self.variables.get(txt_raw[1:-1], ""))
                    else:
                        txt_val = txt_raw

                    if w_name in self.windows:
                        canvas = self.windows[w_name]["canvas"]
                        canvas.create_text(px, py, text=txt_val, anchor=tk.NW, fill="#212529", font=("Segoe UI", 10))
                        self.log(f"Rendered text on canvas '{w_name}' at ({px}, {py}): '{txt_val}'")
                    else:
                        self.log(f"Error: Window '{w_name}' not found.")

            # 16. Store CRUD: Run / Execute Stored Class or Function (find.store.[name]; run)
            elif "find.store." in line and "; run" in line:
                match = re.search(r'find\.store\.[\(\[]?(.*?)[\)\]]?;\s*run', line)
                if match:
                    name = match.group(1).strip()
                    executed = False
                    if name in self.classes:
                        self.log(f"--- Executing Class '{name}' ---")
                        self.execute_block(self.classes[name])
                        executed = True
                    elif name in self.functions:
                        self.log(f"--- Executing Function '{name}' ---")
                        self.execute_block(self.functions[name])
                        executed = True
                    elif name in self.persistent_store:
                        item = self.persistent_store[name]
                        if isinstance(item, dict) and item.get("type") == "class":
                            self.log(f"--- Executing Class '{name}' ---")
                            self.execute_block(item.get("lines", []))
                            executed = True
                    
                    if not executed:
                        self.log(f"Store Error: Item '{name}' cannot be executed.")

            # 17. Store CRUD: Delete / Remove Shape, Window, or Class (find.store.[name]; del)
            elif "find.store." in line and "; del" in line:
                match = re.search(r'find\.store\.[\(\[]?(.*?)[\)\]]?;\s*del', line)
                if match:
                    name = match.group(1).strip()
                    deleted = False
                    for w_name, w_data in self.windows.items():
                        if name in w_data["shapes"] or name in w_data["canvas"].find_withtag(name):
                            w_data["canvas"].delete(name)
                            if name in w_data["shapes"]:
                                del w_data["shapes"][name]
                            if name in w_data["coords"]:
                                del w_data["coords"][name]
                            deleted = True
                    if name in self.windows:
                        self.windows[name]["window"].destroy()
                        del self.windows[name]
                        deleted = True
                    if name in self.classes:
                        del self.classes[name]
                        deleted = True
                    if name in self.persistent_store:
                        del self.persistent_store[name]
                        deleted = True
                        
                    if deleted:
                        self.log(f"Store Action: Deleted/Removed asset '{name}' from database.")
                    else:
                        self.log(f"Store Error: Item '{name}' not found.")

            # 18. Store CRUD: Edit (find.store.[name]; edit.new.name; ([new name]); ([new val]);)
            elif "find.store." in line and "; edit.new.name;" in line:
                match = re.search(r'find\.store\.[\(\[]?(.*?)[\)\]]?;\s*edit\.new\.name;\s*\((.*?)\);\s*\((.*?)\)', line)
                if match:
                    old_name = match.group(1).strip()
                    new_name = match.group(2).strip()
                    new_val = match.group(3).strip()
                    if old_name in self.persistent_store:
                        del self.persistent_store[old_name]
                    self.persistent_store[new_name] = new_val
                    self.log(f"Store Action [EDIT]: Renamed/Updated '{old_name}' -> New Record '{new_name}'")

            # 19. Store CRUD: Replace (find.store.[name]; replace.new([new_item]);)
            elif "find.store." in line and "; replace.new" in line:
                match = re.search(r'find\.store\.[\(\[]?(.*?)[\)\]]?;\s*replace\.new\((.*?)\)', line)
                if match:
                    name = match.group(1).strip()
                    new_item = match.group(2).strip()
                    self.persistent_store[name] = new_item
                    self.log(f"Store Action [REPLACE]: Target '{name}' replaced with '{new_item}'.")

            # 20. Store Retrieval: get.store.list or get.store.array (Standalone)
            elif line.startswith("get.store."):
                match = re.search(r'get\.store\.(list|array);\s*item\("(.*?)"\)', line)
                if match:
                    stype = match.group(1)
                    item_name = match.group(2)
                    self.log(f"Store Retrieval [{stype.upper()}]: Successfully fetched item '{item_name}'.")

            # 21. Function Definition: h.func.definefunc;(name);
            elif line.startswith("h.func.definefunc;"):
                match = re.search(r'h\.func\.definefunc;\((.*?)\);', line)
                if match:
                    func_name = match.group(1).strip()
                    func_lines = []
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.startswith("     ") or next_line.startswith("\t") or next_line.startswith("  "):
                            func_lines.append(next_line.strip())
                            i += 1
                        else:
                            break
                    self.functions[func_name] = func_lines
                    continue

            # 22. Count-Based Loops: loop.func.times(N);
            elif line.startswith("loop.func.times("):
                match = re.search(r'loop\.func\.times\((.*?)\);', line)
                if match:
                    count = int(self.get_val(match.group(1)))
                    loop_lines = []
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.startswith("     ") or next_line.startswith("\t") or next_line.startswith("  "):
                            loop_lines.append(next_line.strip())
                            i += 1
                        else:
                            break
                    for _ in range(count):
                        self.execute_block(loop_lines)
                    continue

            # 23. Function Call: c.func_name();
            elif line.startswith("c.") and line.endswith("();"):
                match = re.search(r'c\.(.*?)\(\);', line)
                if match:
                    func_name = match.group(1)
                    if func_name in self.functions:
                        self.execute_block(self.functions[func_name])
                    else:
                        self.log(f"Error: Function '{func_name}' not found.")

            # 24. Standard Math Operations (SUM, SUB, MUL, DIV)
            elif line.startswith("maths.h.") and not line.startswith("maths.h.complexfunc."):
                op = line.split(';')[0].replace("maths.h.", "")
                match = re.findall(r'\((.*?)\)', line)
                if len(match) >= 2:
                    v1 = self.get_val(match[0])
                    v2 = self.get_val(match[1])
                    try:
                        if op == "SUM": res = v1 + v2
                        elif op == "SUB": res = v1 - v2
                        elif op == "MUL": res = v1 * v2
                        elif op == "DIV": res = v1 / v2 if v2 != 0 else "Error: Division by zero"
                        else: res = f"Unknown operation {op}"
                        self.log(f"Math Result ({op}): {res}")
                    except Exception as e:
                        self.log(f"Math Error: {e}")

            # 25. Complex Math Operations
            elif line.startswith("maths.h.complexfunc."):
                match = re.search(r'maths\.h\.complexfunc\.([A-Z]+)\b', line)
                if match:
                    op = match.group(1)
                    arguments = re.findall(r'\((.*?)\)', line)
                    try:
                        if op == "FIBONACCI":
                            if len(arguments) == 2:
                                starting_values = arguments[0].split(",")
                                if len(starting_values) != 2:
                                    raise ValueError("Fibonacci requires two starting numbers")
                                first, second = (self.get_val(value) for value in starting_values)
                                count = int(self.get_val(arguments[1]))
                            elif len(arguments) == 3:
                                first = self.get_val(arguments[0])
                                second = self.get_val(arguments[1])
                                count = int(self.get_val(arguments[2]))
                            else:
                                raise ValueError("Fibonacci requires two starting numbers and a term count")
                            if count < 0:
                                raise ValueError("Fibonacci term count cannot be negative")
                            sequence = []
                            for _ in range(count):
                                sequence.append(first)
                                first, second = second, first + second
                            self.log(f"Complex Math (Fibonacci, {count} terms): {sequence}")
                        elif not arguments:
                            self.log(f"Unknown complex operation: {op}")
                        elif op == "SQU":
                            val = self.get_val(arguments[0])
                            res = val ** 2
                            self.log(f"Complex Math (Square of {val}): {res}")
                        elif op == "CUB":
                            val = self.get_val(arguments[0])
                            res = val ** 3
                            self.log(f"Complex Math (Cube of {val}): {res}")
                        elif op == "SQUROOT":
                            val = self.get_val(arguments[0])
                            res = val ** 0.5
                            self.log(f"Complex Math (Square Root of {val}): {res}")
                        else:
                            self.log(f"Unknown complex operation: {op}")
                    except Exception as e:
                        self.log(f"Complex Math Error: {e}")

            i += 1

    def ensure_3d_viewport(self):
        w_name = "3D_Viewport"
        if w_name not in self.windows:
            root = self.get_root_tk()
            win = self.create_toplevel(root)
            win.title("Prism 3D Viewport")
            win.geometry("900x700")
            win.configure(bg="#1e1e1e")
            canvas = tk.Canvas(win, bg="#1e1e1e", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            win.focus_set()
            win.focus_force()
            self.windows[w_name] = {"window": win, "canvas": canvas, "shapes": {}, "coords": {}}

        w_data = self.windows[w_name]
        w_data.setdefault("raycast_objects", {})
        canvas = w_data["canvas"]
        if not w_data.get("raycast_bound"):
            canvas.bind("<Button-1>", self.handle_3d_raycast)
            w_data["raycast_bound"] = True
        return w_data

    def draw_raycast_grid(self, columns, rows, shape_type):
        w_data = self.ensure_3d_viewport()
        canvas = w_data["canvas"]
        viewport_width, viewport_height = 900, 700
        cell_size = min(28, (viewport_width - 72) / columns, (viewport_height - 96) / rows)
        step = cell_size * 1.12
        shape_size = cell_size * 0.78
        grid_width = columns * step
        grid_height = rows * step
        start_x = (viewport_width - grid_width) / 2
        start_y = (viewport_height - grid_height) / 2
        grid_index = sum(
            1 for key, value in self.persistent_store.items()
            if key.startswith("raycast_grid_") and value.get("type") == "3d_raycast_grid"
        ) + 1
        grid_name = f"raycast_grid_{grid_index}"

        for row in range(rows):
            for column in range(columns):
                shape_name = f"{grid_name}_{row + 1}_{column + 1}"
                object_tag = f"raycast_object:{shape_name}"
                x = start_x + column * step
                y = start_y + row * step
                bounds = (x, y, x + shape_size, y + shape_size)
                tags = ("raycast_object", object_tag)
                self.draw_raycast_shape(
                    canvas, shape_type, x, y, shape_size, shape_size * 0.22, tags
                )
                w_data["raycast_objects"][object_tag] = {
                    "name": shape_name,
                    "type": shape_type,
                    "row": row + 1,
                    "column": column + 1,
                    "bounds": bounds
                }
                w_data["shapes"][shape_name] = object_tag
                self.persistent_store[shape_name] = {
                    "type": "3d_raycast_shape",
                    "window": "3D_Viewport",
                    "shape": shape_type,
                    "row": row + 1,
                    "column": column + 1
                }

        self.persistent_store[grid_name] = {
            "type": "3d_raycast_grid",
            "window": "3D_Viewport",
            "columns": columns,
            "rows": rows,
            "shape": shape_type
        }
        self.log(
            f"3D raycast grid created: {columns}x{rows} {shape_type} shapes. "
            "Click a shape in the viewport to raycast-select it."
        )

    def draw_raycast_shape(self, canvas, shape_type, x, y, size, depth, tags):
        right, bottom = x + size, y + size
        if shape_type == "cube":
            canvas.create_polygon(
                x, y, x + depth, y - depth, right + depth, y - depth, right, y,
                fill="#6f42c1", outline="#c9b6f2", width=1, tags=tags
            )
            canvas.create_polygon(
                right, y, right + depth, y - depth, right + depth, bottom - depth,
                right, bottom, fill="#0b7285", outline="#75d5e3", width=1, tags=tags
            )
            canvas.create_rectangle(
                x, y, right, bottom, fill="#0dcaf0", outline="#b9f2fb", width=1, tags=tags
            )
        elif shape_type == "sphere":
            canvas.create_oval(
                x, y, right, bottom, fill="#fd7e14", outline="#ffc107", width=2, tags=tags
            )
            canvas.create_arc(
                x + size * 0.2, y + size * 0.2, right - size * 0.2, bottom - size * 0.2,
                start=35, extent=110, style=tk.ARC, outline="#ffeeba", width=2, tags=tags
            )
        elif shape_type == "cylinder":
            cap_height = size * 0.28
            canvas.create_rectangle(
                x, y + cap_height / 2, right, bottom - cap_height / 2,
                fill="#0f5132", outline="#20c997", width=2, tags=tags
            )
            canvas.create_oval(
                x, y, right, y + cap_height, fill="#198754", outline="#20c997", width=2, tags=tags
            )
            canvas.create_arc(
                x, bottom - cap_height, right, bottom, start=180, extent=180,
                style=tk.ARC, outline="#20c997", width=2, tags=tags
            )
        else:
            canvas.create_polygon(
                x, bottom, x + size / 2 + depth / 2, y - depth, right + depth, bottom,
                fill="#d63384", outline="#ffb3d2", width=2, tags=tags
            )
            canvas.create_line(
                x + size / 2 + depth / 2, y - depth, x + size / 2, bottom,
                fill="#ffb3d2", width=1, tags=tags
            )

    def draw_wolfenstein_map(self, pattern, cols, rows):
        # Simple Wolfenstein-style raycast renderer (top-down map + vertical slice view)
        w_name = "3D_Viewport"
        w_data = self.ensure_3d_viewport()
        canvas = w_data["canvas"]
        # Clear previous raycast_objects for cleanliness
        w_data["raycast_objects"] = {}
        # Build map array repeating pattern to fill cols*rows
        total = cols * rows
        repeated = (pattern * (total // len(pattern) + 1))[:total]
        grid = [list(repeated[i * cols:(i + 1) * cols]) for i in range(rows)]
        # Map char -> wall presence/type
        def char_to_wall(ch):
            ch = ch.lower()
            if ch in ("0", " "):
                return None
            if ch in ("1", "c", "w"):
                return "cube"
            if ch in ("2", "s"):
                return "sphere"
            if ch in ("3", "y"):
                return "cylinder"
            if ch in ("4", "p"):
                return "pyramid"
            return "cube"

        # Canvas geometry
        width = int(canvas.winfo_width() or 900)
        height = int(canvas.winfo_height() or 700)
        # Partition canvas: left 40% = top-down map, right 60% = vertical projection
        left_w = int(width * 0.4)
        right_x = left_w + 8
        # Draw top-down map
        cell_w = max(6, left_w // max(1, cols))
        cell_h = max(6, height // max(1, rows))
        map_origin_x = (left_w - (cell_w * cols)) / 2
        map_origin_y = (height - (cell_h * rows)) / 2
        # draw grid and walls
        for r in range(rows):
            for c in range(cols):
                ch = grid[r][c]
                wall = char_to_wall(ch)
                x = map_origin_x + c * cell_w
                y = map_origin_y + r * cell_h
                if wall:
                    fill = "#7b3cff" if wall == "cube" else ("#ff8c00" if wall == "sphere" else ("#198754" if wall == "cylinder" else "#d63384"))
                    canvas.create_rectangle(x, y, x + cell_w - 1, y + cell_h - 1, fill=fill, outline="#222222", tags=("wolf_map_cell",))
                else:
                    canvas.create_rectangle(x, y, x + cell_w - 1, y + cell_h - 1, fill="#111111", outline="#1a1a1a", tags=("wolf_map_cell",))
        # Player starting position at center
        player_x = cols / 2.0
        player_y = rows / 2.0
        player_angle = 0.0
        # Draw player on map
        px = map_origin_x + player_x * cell_w
        py = map_origin_y + player_y * cell_h
        canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#ffffff", tags=("wolf_player",))

        # Vertical projection
        slice_width = max(2, (width - right_x) // 180)
        num_slices = (width - right_x) // slice_width
        fov = 60.0 * (3.14159 / 180.0)
        half_fov = fov / 2.0
        max_view_distance = max(cols, rows) * 1.5
        proj_origin_x = right_x
        proj_origin_y = 0
        proj_height = height

        # raycast for each slice
        for i in range(num_slices):
            ray_angle = player_angle - half_fov + (i / max(1, num_slices - 1)) * fov
            # step along ray
            distance = 0.0
            hit = None
            step = 0.1
            while distance < max_view_distance:
                test_x = player_x + distance * (math_cos := __import__('math').cos(ray_angle))
                test_y = player_y + distance * (math_sin := __import__('math').sin(ray_angle))
                gx = int(test_x)
                gy = int(test_y)
                if gx < 0 or gx >= cols or gy < 0 or gy >= rows:
                    break
                if char_to_wall(grid[gy][gx]):
                    hit = (gx, gy)
                    break
                distance += step
            if hit:
                # simple fisheye correction
                corrected = distance * __import__('math').cos(ray_angle - player_angle)
                wall_height = int(min(proj_height, (proj_height * 1.5) / max(0.001, corrected)))
                shade = int(max(40, 255 - min(200, corrected * 18)))
                color = f"#{shade:02x}{shade:02x}{shade:02x}"
                x = proj_origin_x + i * slice_width
                y1 = (proj_height - wall_height) // 2
                y2 = y1 + wall_height
                canvas.create_rectangle(x, y1, x + slice_width, y2, fill=color, outline=color, tags=("wolf_proj",))
                # draw ray on map
                canvas.create_line(px, py, map_origin_x + (hit[0] + 0.5) * cell_w, map_origin_y + (hit[1] + 0.5) * cell_h, fill="#ffff66", width=1, tags=("wolf_ray",))
        self.persistent_store[f"wolf_map_{len(self.persistent_store)}"] = {"type": "wolfenstein_map", "cols": cols, "rows": rows}
        self.log(f"Wolfenstein raycast map rendered ({cols}x{rows}) from pattern: '{pattern[:64]}'")

    def handle_3d_raycast(self, event):
        w_data = self.windows.get("3D_Viewport")
        if not w_data:
            return
        canvas = w_data["canvas"]
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        overlapping = canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)
        for item_id in reversed(overlapping):
            for tag in canvas.gettags(item_id):
                hit = w_data["raycast_objects"].get(tag)
                if hit:
                    canvas.delete("raycast_selection")
                    left, top, right, bottom = hit["bounds"]
                    canvas.create_rectangle(
                        left - 2, top - 2, right + 2, bottom + 2,
                        outline="#ffffff", width=2, tags="raycast_selection"
                    )
                    canvas.tag_raise("raycast_selection")
                    self.variables["raycast_hit"] = hit["name"]
                    self.log(
                        f"3D raycast hit: '{hit['name']}' ({hit['type']}) "
                        f"at grid cell ({hit['row']}, {hit['column']})"
                    )
                    return

    def update_shape_position(self, shape_name, nx, ny, nz):
        for w_name, w_data in self.windows.items():
            if shape_name in w_data["shapes"]:
                canvas = w_data["canvas"]
                item_id = w_data["shapes"][shape_name]
                if shape_name in w_data["coords"]:
                    c_data = w_data["coords"][shape_name]
                    size = c_data["size"]
                    c_data["x"] = nx
                    c_data["y"] = ny
                    c_data["z"] = nz
                    canvas.coords(item_id, nx, ny, nx + size, ny + size)
                self.log(f"Shape Position Updated: '{shape_name}' -> ({nx}, {ny})")

    def handle_generic_keypress(self, event, shape_name):
        char = event.char.lower() if event.char else event.keysym.lower()
        if char in self.key_functions:
            self.handle_key_event(event, shape_name, char)
        else:
            step = 15
            for w_name, w_data in self.windows.items():
                if shape_name in w_data["shapes"] and shape_name in w_data["coords"]:
                    c = w_data["coords"][shape_name]
                    x, y, z = c["x"], c["y"], c["z"]
                    if char in ['w', 'up']: y -= step
                    elif char in ['s', 'down']: y += step
                    elif char in ['a', 'left']: x -= step
                    elif char in ['d', 'right']: x += step
                    else: return
                    self.update_shape_position(shape_name, x, y, z)

    def handle_key_event(self, event, shape_name, key_char):
        key_char = key_char.lower()
        if key_char in self.key_functions:
            for f_line in self.key_functions[key_char]:
                if "h.change.shape.pos" in f_line:
                    for w_name, w_data in self.windows.items():
                        if shape_name in w_data["shapes"] and shape_name in w_data["coords"]:
                            c = w_data["coords"][shape_name]
                            x, y, z = c["x"], c["y"], c["z"]
                            step = 15
                            if key_char in ['w', 'up']: y -= step
                            elif key_char in ['s', 'down']: y += step
                            elif key_char in ['a', 'left']: x -= step
                            elif key_char in ['d', 'right']: x += step
                            self.update_shape_position(shape_name, x, y, z)
                else:
                    self.execute_block([f_line])
        else:
            self.handle_generic_keypress(event, shape_name)

    def get_val(self, token):
        token = token.strip()
        if token.startswith('[') and token.endswith(']'):
            return self.variables.get(token[1:-1], 0)
        try:
            if '.' in token:
                return float(token)
            return int(token)
        except ValueError:
            return token


class PrismIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("Prism Language IDE - Untitled.prism")
        self.root.geometry("1080x780")
        
        # User Settings State
        self.settings = {
            "username": "User",
            "show_comments": False,
            "show_console": True,
            "theme": "light"
        }

        self.current_file_path = None

        # Top Toolbar Frame
        self.toolbar = tk.Frame(root, height=50)
        self.toolbar.pack(fill=tk.X, padx=10, pady=10)

        self.run_btn = tk.Button(self.toolbar, text="▶ Run Code", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, command=self.run_code)
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.compile_btn = tk.Button(self.toolbar, text="⚙ Compile / Export", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=12, pady=5, command=self.compile_prism_file)
        self.compile_btn.pack(side=tk.LEFT, padx=5)

        self.open_btn = tk.Button(self.toolbar, text="📂 Open", font=("Segoe UI", 10), relief=tk.FLAT, padx=10, pady=5, command=self.open_file)
        self.open_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = tk.Button(self.toolbar, text="💾 Save", font=("Segoe UI", 10), relief=tk.FLAT, padx=10, pady=5, command=self.save_file)
        self.save_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = tk.Button(self.toolbar, text="Clear Console", font=("Segoe UI", 10), relief=tk.FLAT, padx=10, pady=5, command=self.clear_console)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        self.settings_btn = tk.Button(self.toolbar, text="⚙ Options", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=12, pady=5, command=self.show_options)
        self.settings_btn.pack(side=tk.LEFT, padx=5)

        self.help_btn = tk.Button(self.toolbar, text="❓ Help & Syntax", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=12, pady=5, command=self.show_help)
        self.help_btn.pack(side=tk.LEFT, padx=5)

        # Examples Dropdown Menu Button
        self.examples_btn = tk.Menubutton(self.toolbar, text="📚 Examples ▼", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=12, pady=5)
        
        self.menu = Menu(self.examples_btn, tearoff=0, font=("Segoe UI", 10))
        self.examples_btn["menu"] = self.menu
        
        self.menu.add_command(label="1. Variables & Basic Math", command=lambda: self.load_example("vars_math"))
        self.menu.add_command(label="2. Custom Functions & Calls", command=lambda: self.load_example("functions"))
        self.menu.add_command(label="3. Advanced Complex Math", command=lambda: self.load_example("complex_math"))
        self.menu.add_command(label="4. GUI Display & Windows", command=lambda: self.load_example("gui_display"))
        self.menu.add_command(label="5. GUI Shapes & Canvas Store", command=lambda: self.load_example("gui_shapes"))
        self.menu.add_command(label="6. Interactive Shape Movement", command=lambda: self.load_example("interactive_movement"))
        self.menu.add_command(label="7. User Input & Loops", command=lambda: self.load_example("input_loops"))
        self.menu.add_command(label="8. 3D Shapes & scan.store", command=lambda: self.load_example("shapes_3d"))
        self.menu.add_command(label="9. Custom Classes & find.store run", command=lambda: self.load_example("classes"))
        self.menu.add_command(label="10. 3D Raycast Grid", command=lambda: self.load_example("raycast_grid"))
        self.menu.add_command(label="11. Wolfenstein Raycast Map", command=lambda: self.load_example("wolfenstein_map"))
        
        self.examples_btn.pack(side=tk.LEFT, padx=5)

        # Main Layout Split (Editor & Console)
        self.paned = tk.PanedWindow(root, orient=tk.VERTICAL, sashwidth=6)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Editor Frame
        self.editor_frame = tk.Frame(self.paned)
        self.editor_label = tk.Label(self.editor_frame, text="Code Editor (.prism)", font=("Segoe UI", 9, "bold"))
        self.editor_label.pack(anchor=tk.W, padx=5, pady=2)
        
        self.editor = scrolledtext.ScrolledText(self.editor_frame, wrap=tk.WORD, font=("Consolas", 11), bd=1, relief=tk.SOLID)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.load_example("classes")
        self.paned.add(self.editor_frame, height=400)

        # Console Output Frame
        self.console_frame = tk.Frame(self.paned)
        self.console_label = tk.Label(self.console_frame, text="Console Output", font=("Segoe UI", 9, "bold"))
        self.console_label.pack(anchor=tk.W, padx=5, pady=2)

        self.console = scrolledtext.ScrolledText(self.console_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED, bd=1, relief=tk.SOLID)
        self.console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.paned.add(self.console_frame)

        # Initialize Interpreter
        self.interpreter = PrismInterpreter(self.root, self.write_output, lambda: self.settings)

        # Apply Default Theme
        self.apply_theme(self.settings["theme"])

    def apply_theme(self, theme_name):
        self.settings["theme"] = theme_name
        
        themes = {
            "light": {
                "root_bg": "#f5f6f8", "toolbar_bg": "#e9ecef",
                "btn_run": "#0d6efd", "btn_run_fg": "#ffffff",
                "btn_comp": "#198754", "btn_comp_fg": "#ffffff",
                "btn_std": "#495057", "btn_std_fg": "#ffffff",
                "btn_opt": "#17a2b8", "btn_opt_fg": "#ffffff",
                "btn_ex": "#6f42c1", "btn_ex_fg": "#ffffff",
                "editor_bg": "#ffffff", "editor_fg": "#111111", "editor_lbl": "#212529",
                "console_bg": "#f1f3f5", "console_fg": "#111111", "console_lbl": "#212529",
                "paned_bg": "#dee2e6"
            },
            "dark": {
                "root_bg": "#181818", "toolbar_bg": "#252526",
                "btn_run": "#0e639c", "btn_run_fg": "#ffffff",
                "btn_comp": "#2ea043", "btn_comp_fg": "#ffffff",
                "btn_std": "#3c3c3c", "btn_std_fg": "#ffffff",
                "btn_opt": "#007acc", "btn_opt_fg": "#ffffff",
                "btn_ex": "#68217a", "btn_ex_fg": "#ffffff",
                "editor_bg": "#1e1e1e", "editor_fg": "#ffffff", "editor_lbl": "#f8f9fa",
                "console_bg": "#121212", "console_fg": "#ffffff", "console_lbl": "#f8f9fa",
                "paned_bg": "#333333"
            },
            "grey": {
                "root_bg": "#343a40", "toolbar_bg": "#495057",
                "btn_run": "#198754", "btn_run_fg": "#ffffff",
                "btn_comp": "#20c997", "btn_comp_fg": "#111111",
                "btn_std": "#6c757d", "btn_std_fg": "#ffffff",
                "btn_opt": "#0dcaf0", "btn_opt_fg": "#111111",
                "btn_ex": "#ffc107", "btn_ex_fg": "#111111",
                "editor_bg": "#212529", "editor_fg": "#ffffff", "editor_lbl": "#ffffff",
                "console_bg": "#1a1d20", "console_fg": "#ffffff", "console_lbl": "#ffffff",
                "paned_bg": "#495057"
            }
        }

        t = themes.get(theme_name, themes["light"])
        
        self.root.configure(bg=t["root_bg"])
        self.toolbar.configure(bg=t["toolbar_bg"])
        self.paned.configure(bg=t["paned_bg"])

        self.run_btn.configure(bg=t["btn_run"], fg=t["btn_run_fg"])
        self.compile_btn.configure(bg=t["btn_comp"], fg=t["btn_comp_fg"])
        self.open_btn.configure(bg=t["btn_std"], fg=t["btn_std_fg"])
        self.save_btn.configure(bg=t["btn_std"], fg=t["btn_std_fg"])
        self.clear_btn.configure(bg=t["btn_std"], fg=t["btn_std_fg"])
        self.settings_btn.configure(bg=t["btn_opt"], fg=t["btn_opt_fg"])
        self.help_btn.configure(bg=t["btn_opt"], fg=t["btn_opt_fg"])
        self.examples_btn.configure(bg=t["btn_ex"], fg=t["btn_ex_fg"])

        self.editor_frame.configure(bg=t["root_bg"])
        self.editor_label.configure(bg=t["root_bg"], fg=t["editor_lbl"])
        self.editor.configure(bg=t["editor_bg"], fg=t["editor_fg"], insertbackground=t["editor_fg"])

        self.console_frame.configure(bg=t["root_bg"])
        self.console_label.configure(bg=t["root_bg"], fg=t["console_lbl"])
        self.console.configure(bg=t["console_bg"], fg=t["console_fg"])

    def show_options(self):
        opt_win = tk.Toplevel(self.root)
        opt_win.title("Prism IDE - Settings & Options")
        opt_win.geometry("400x380")
        
        bg_col = "#252526" if self.settings["theme"] == "dark" else ("#343a40" if self.settings["theme"] == "grey" else "#f5f6f8")
        fg_col = "#ffffff" if self.settings["theme"] in ["dark", "grey"] else "#111111"
        entry_bg = "#1e1e1e" if self.settings["theme"] == "dark" else ("#212529" if self.settings["theme"] == "grey" else "#ffffff")
        
        opt_win.configure(bg=bg_col)
        opt_win.grab_set()

        tk.Label(opt_win, text="IDE Preferences & Options", font=("Segoe UI", 12, "bold"), bg=bg_col, fg=fg_col).pack(pady=12)

        # Username Field
        user_frame = tk.Frame(opt_win, bg=bg_col)
        user_frame.pack(anchor=tk.W, padx=30, pady=5, fill=tk.X)
        tk.Label(user_frame, text="Username:", font=("Segoe UI", 10, "bold"), bg=bg_col, fg=fg_col).pack(side=tk.LEFT, padx=(0, 10))
        user_entry = tk.Entry(user_frame, font=("Segoe UI", 10), bg=entry_bg, fg=fg_col, insertbackground=fg_col, bd=1, relief=tk.SOLID)
        user_entry.insert(0, self.settings["username"])
        user_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Option 1 Var: Show comments in output
        comm_var = tk.BooleanVar(value=self.settings["show_comments"])
        tk.Checkbutton(opt_win, text="Option 1: Show comments in output", variable=comm_var, font=("Segoe UI", 10), bg=bg_col, fg=fg_col, selectcolor=bg_col, activebackground=bg_col, activeforeground=fg_col).pack(anchor=tk.W, padx=30, pady=5)

        # Option 2 Var: Show output tab / console
        console_var = tk.BooleanVar(value=self.settings["show_console"])
        tk.Checkbutton(opt_win, text="Option 2: Show output tab (Console)", variable=console_var, font=("Segoe UI", 10), bg=bg_col, fg=fg_col, selectcolor=bg_col, activebackground=bg_col, activeforeground=fg_col).pack(anchor=tk.W, padx=30, pady=5)

        # Option 3 Var: Preferred View Theme
        tk.Label(opt_win, text="Option 3: Preferred View Theme", font=("Segoe UI", 10, "bold"), bg=bg_col, fg=fg_col).pack(anchor=tk.W, padx=30, pady=(12, 2))
        
        theme_var = tk.StringVar(value=self.settings["theme"])
        theme_frame = tk.Frame(opt_win, bg=bg_col)
        theme_frame.pack(anchor=tk.W, padx=30, pady=5)

        for th in ["light", "dark", "grey"]:
            tk.Radiobutton(theme_frame, text=th.capitalize(), variable=theme_var, value=th, font=("Segoe UI", 10), bg=bg_col, fg=fg_col, selectcolor=bg_col, activebackground=bg_col, activeforeground=fg_col).pack(side=tk.LEFT, padx=5)

        def save_options():
            uname = user_entry.get().strip()
            self.settings["username"] = uname
            self.settings["show_comments"] = comm_var.get()
            self.settings["show_console"] = console_var.get()
            
            # Sisyphus Prime Easter Egg Trigger
            if uname == "hmm, appetizer":
                self.write_output("\nsisyphus prime reference lol\n")

            if self.settings["show_console"]:
                try:
                    self.paned.add(self.console_frame)
                except:
                    pass
            else:
                try:
                    self.paned.remove(self.console_frame)
                except:
                    pass

            self.apply_theme(theme_var.get())
            opt_win.destroy()

        save_btn = tk.Button(opt_win, text="Save & Apply", bg="#0d6efd", fg="#ffffff", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, command=save_options)
        save_btn.pack(pady=18)

    def write_output(self, text):
        if self.settings["show_console"]:
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, text)
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)

    def clear_console(self):
        self.console.config(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.config(state=tk.DISABLED)

    def open_file(self):
        file_path = filedialog.askopenfilename(defaultextension=".prism", filetypes=[("Prism Files", "*.prism"), ("All Files", "*.*")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    code = file.read()
                self.editor.delete("1.0", tk.END)
                self.editor.insert(tk.END, code)
                self.current_file_path = file_path
                self.root.title(f"Prism Language IDE - {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")

    def save_file(self):
        if self.current_file_path:
            try:
                code = self.editor.get("1.0", tk.END)
                with open(self.current_file_path, "w", encoding="utf-8") as file:
                    file.write(code)
                messagebox.showinfo("Success", f"File saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{e}")
        else:
            self.save_as_file()

    def save_as_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".prism", filetypes=[("Prism Files", "*.prism"), ("All Files", "*.*")])
        if file_path:
            try:
                code = self.editor.get("1.0", tk.END)
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(code)
                self.current_file_path = file_path
                self.root.title(f"Prism Language IDE - {file_path}")
                messagebox.showinfo("Success", f"File saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{e}")

    def compile_prism_file(self):
        """Compiles and exports code into a standalone runnable .prism package file."""
        file_path = filedialog.asksaveasfilename(defaultextension=".prism", filetypes=[("Prism Standalone Executable", "*.prism"), ("All Files", "*.*")])
        if file_path:
            try:
                code = self.editor.get("1.0", tk.END)
                compiled_payload = f"# Prism Standalone Package v1.0\n# Compiled by: {self.settings['username']}\n\n{code}"
                
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(compiled_payload)
                
                self.write_output(f"\n[Compiler Success]: Compiled and exported standalone binary to:\n{file_path}\n")
                messagebox.showinfo("Compilation Success", f"Standalone .prism file compiled and saved successfully!\n\nPath: {file_path}")
            except Exception as e:
                messagebox.showerror("Compilation Error", f"Could not compile standalone file:\n{e}")

    def load_example(self, ex_key):
        self.editor.delete("1.0", tk.END)
        self.current_file_path = None
        self.root.title("Prism Language IDE - Untitled.prism")
        
        examples = {
            "vars_math": '''c.comment("Example 1: Variables and Arithmetic")

h.func.define;[score]
h.change;variable:[score];[50]

h.printline;"Initial score value:"
h.printline;[score]

maths.h.SUM; ([score]); ([score]);
maths.h.SUB; ([score]); ([10]);
maths.h.MUL; ([score]); ([2]);
''',
            "functions": '''c.comment("Example 2: Custom Functions & Store")

h.func.definefunc;(system_startup);
     h.printline;"Initializing Prism Engine..."
     h.printline;"Status: All systems online."

store.func(system_startup)
c.system_startup();
''',
            "complex_math": '''c.comment("Example 3: Advanced Complex Math")

h.func.define;[number]
h.change;variable:[number];[16]

h.printline;"Working with value: 16"
maths.h.complexfunc.SQU([number])
maths.h.complexfunc.CUB([number])
maths.h.complexfunc.SQUROOT([number])
maths.h.complexfunc.FIBONACCI; (0, 1); (10);
''',
            "gui_display": '''c.comment("Example 4: GUI Display Window")

display.h.window.show; (350); (200); (1); (MyDashboard)
store.(MyDashboard)

show.text.display.h; (MyDashboard); (30); (40); (1); ("Welcome to Prism GUI Engine!")
show.text.display.h; (MyDashboard); (30); (80); (1); ("Status: Running smoothly.")
''',
            "gui_shapes": '''c.comment("Example 5: GUI Shapes & Canvas Store")

display.window(ArtCanvas); draw(shape type: circle); (50); (50); (1); (cir1)
store.shape(cir1)

display.window(ArtCanvas); draw(shape type: square); (150); (50); (1); (sq1)
store.shape(sq1)

display.window(ArtCanvas); draw(shape type: triangle); (250); (50); (2); (tri1)
store.shape(tri1)
''',
            "interactive_movement": '''c.comment("Example 6: Interactive Shape Movement")

display.window(GameArena); draw(shape type: circle); (200); (200); (1); (player)
store.shape(player)

apply.movement.player(player); (w); (a); (s); (d)

h.define.display.key.func(w);
     h.change.shape.pos(player); (200); (180); (1);

h.define.display.key.func(s);
     h.change.shape.pos(player); (200); (220); (1);

h.define.display.key.func(a);
     h.change.shape.pos(player); (180); (200); (1);

h.define.display.key.func(d);
     h.change.shape.pos(player); (220); (200); (1);
''',
            "input_loops": '''c.comment("Example 7: User Input & Loops")

askuser.h.func.input;[username]=("Enter your name: ")
h.printline;"Hello, "
h.printline;[username]

c.comment("Looping a print statement 3 times")
loop.func.times(3);
     h.printline;"Repeating loop action..."
''',
            "shapes_3d": '''c.comment("Example 8: 3D Shapes & scan.store")

shapes.draw.h.3d.type(cube); vector1; (100); (100); (2); endvector; (120); (120); (3); :("my_cube"):
store.[my_cube]

shapes.draw.h.3d.type(sphere); vector1; (300); (100); (1); endvector; (100); (100); (2); :("my_sphere"):
store.[my_sphere]

scan.store
''',
            "raycast_grid": '''c.comment("Example 10: Clickable 3D Raycast Grid")

3D.raycast.shapes; (16x16); (cube);

c.comment("Click a shape in the 3D viewport to select it.")
c.comment("The selected name is stored in [raycast_hit].")
''',
            "wolfenstein_map": '''c.comment("Example 11: Wolfenstein-style Raycast Map")

3D.raycast.wolfensteinformula.shapes; (1011001100); (16x16);

c.comment("This uses a repeating pattern where '1' is a wall and '0' is empty.")
c.comment("Top-down and a simple vertical projection are rendered in the 3D viewport.")
''',
            "classes": '''c.comment("Example 9: Custom Classes & find.store run")

c.create.new.type((class); ("PlayerEntity")); {
     h.func.define;[health]
     h.change;variable:[health];[100]
     h.printline;"PlayerEntity class initialized!"
     h.printline;[health]
}
store.[PlayerEntity]

c.comment("Execute the stored class via find.store")
find.store.[PlayerEntity]; run
'''
        }
        
        if ex_key in examples:
            self.editor.insert(tk.END, examples[ex_key])

    def show_help(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("Prism Language - Master Syntax Reference Sheet")
        help_win.geometry("700x680")
        
        bg_col = "#252526" if self.settings["theme"] == "dark" else ("#343a40" if self.settings["theme"] == "grey" else "#f5f6f8")
        fg_col = "#ffffff" if self.settings["theme"] in ["dark", "grey"] else "#111111"
        txt_bg = "#1e1e1e" if self.settings["theme"] == "dark" else ("#212529" if self.settings["theme"] == "grey" else "#ffffff")

        help_win.configure(bg=bg_col)

        label = tk.Label(help_win, text="Master Syntax Reference Sheet (v3.5)", font=("Segoe UI", 12, "bold"), bg=bg_col, fg=fg_col)
        label.pack(anchor=tk.W, padx=15, pady=10)

        help_text = scrolledtext.ScrolledText(help_win, wrap=tk.WORD, font=("Consolas", 10), bg=txt_bg, fg=fg_col, bd=1, relief=tk.SOLID)
        help_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        guide_content = """--- PRISM LANGUAGE COMPLETE SYNTAX GUIDE ---

1. COMMAND LINE EXECUTION (CLI):
   Run a Prism file from the Prism folder (or with prism on PATH):
   > prism script.prism
   Install a prebuilt library:
   > prism install WC
   > prism install Bitwin

2. PREBUILT LIBRARIES:
   Install libraries with "prism install WC" or "prism install Bitwin", then
   load them in a script with library.use;[WC] or library.use;[Bitwin].

   WC (Window Customization):
   wc.window.title;(MyWindow);("Custom title")
   wc.window.background;(MyWindow);(#336699)
   wc.window.size;(MyWindow);(800);(600)

   Bitwin runs UTF-8 Prism source encoded as hexadecimal:
   bitwin.run;[682e7072696e746c696e653b2248656c6c6f22]
   (The hex must be an even-length sequence of valid hexadecimal digits.)

3. STANDALONE COMPILER:
   Click "⚙ Compile / Export" on the IDE toolbar to package your script into a standalone runnable .prism file!

4. CUSTOM CLASSES & STORE EXECUTION:
   Syntax:
   c.create.new.type((class); ("class_name")); {
        (your code here, must have indentation)
   }
   store.[class_name]
   
   Execute Class:
   find.store.[class_name]; run

5. DATABASE STORE & SCANNING:
   Scan Store: scan.store (prints all stored items, classes, and variables to console)
   Store item: store.[name]
   Delete item: find.store.[name]; del

6. COMPLEX MATH:
    Fibonacci sequence: maths.h.complexfunc.FIBONACCI; (0, 1); (10);
    The last group is the number of terms to generate. The starting pair can also
    be given in separate groups, for example: (0); (1); (10).

7. 3D RAYCAST SHAPES:
   Syntax: 3D.raycast.shapes; (columns x rows); (shape_type);
   Example: 3D.raycast.shapes; (16x16); (cube);
   Grid dimensions must each be from 1 to 32. Supported shapes are cube, sphere,
   cylinder, and pyramid. Click a shape in the 3D viewport to select it; the
   selected shape name is stored in [raycast_hit] and reported in the console.

8. WOLFENSTEIN-STYLE RAYCAST MAPS:
   Syntax: 3D.raycast.wolfensteinformula.shapes; (pattern); (columns x rows);
   Example: 3D.raycast.wolfensteinformula.shapes; (101100); (16x16);
   The pattern is repeated to fill the grid (cols*rows). Characters '1' (or c/w)
   represent walls; '0' (or space) are empty. This renders a simple top-down
   map and a basic vertical projection using Wolfenstein-style raycasting.
"""
        help_text.insert(tk.END, guide_content)
        help_text.config(state=tk.DISABLED)

    def run_code(self):
        self.clear_console()
        code = self.editor.get("1.0", tk.END)
        try:
            self.interpreter.run(code)
            self.write_output("\n--- Execution Finished Successfully ---\n")
        except Exception as e:
            self.write_output(f"\n[Runtime Error]: {str(e)}\n")


def run_cli(arguments):
    if not arguments:
        return None

    if arguments[0] in ("--help", "-h"):
        print("Usage: prism <script.prism> | pr-install <WC|Bitwin>")
        return 0

    if arguments[0].lower() in ("pr-install", "install"):
        if len(arguments) != 2:
            print("Usage: pr-install <WC|Bitwin>", file=sys.stderr)
            return 2
        try:
            installed_path = install_library(arguments[1])
            print(f"Installed {PREBUILT_LIBRARY_NAMES[arguments[1].lower()]} to {installed_path}")
            return 0
        except (OSError, ValueError) as error:
            print(f"Prism library install error: {error}", file=sys.stderr)
            return 1

    if len(arguments) != 1:
        print("Usage: prism <script.prism> | pr-install <WC|Bitwin>", file=sys.stderr)
        return 2

    target_file = arguments[0]
    if not os.path.isfile(target_file):
        print(f"Prism Error: File '{target_file}' not found.", file=sys.stderr)
        return 1

    try:
        with open(target_file, "r", encoding="utf-8-sig") as script_file:
            file_code = script_file.read()
    except (OSError, UnicodeError) as error:
        print(f"Prism Error: Could not read '{target_file}': {error}", file=sys.stderr)
        return 1

    cli_interpreter = PrismInterpreter(
        root_tk=None,
        output_callback=print,
        settings_provider=lambda: {"show_comments": True}
    )
    print(f"--- Running Prism Script: {target_file} ---")
    try:
        cli_interpreter.run(file_code)
        print("\n--- Execution Finished Successfully ---")
        if cli_interpreter.windows and cli_interpreter.root_tk is not None:
            cli_interpreter.root_tk.mainloop()
        return 0
    except Exception as error:
        print(f"\n[Runtime Error]: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    cli_exit_code = run_cli(sys.argv[1:])
    if cli_exit_code is not None:
        sys.exit(cli_exit_code)

    root = tk.Tk()
    app = PrismIDE(root)
    root.mainloop()