import sys
import os
import struct
import argparse
import re

PARAM_ID_ENUM = {
    0: "DISPLAYNAME",
    1: "THEMENAME",
    2: "FREE",
    3: "CREDIT",
    4: "CAPEPATH",
    5: "BOX",
    6: "ANIM",
    7: "PACKID",
    8: "NETHERPARTICLECOLOUR",
    9: "ENCHANTTEXTCOLOUR",
    10: "ENCHANTTEXTFOCUSCOLOUR",
    11: "DATAPATH",
    12: "PACKVERSION",
}
locales = [
            "en-EN",
            "de-DE",
            "fr-FR",
            "it-IT",
            "es-ES",
            "pt-PT",
            "ja-JP",
            "ko-KR",
            "pt-BR",
            "zh-CHT",
        ]
TYPE_TEXTURE = 2
TYPE_PACKCONFIG = 4
TYPE_TEXTUREPACK = 5
TYPE_LOCALISATION = 6
TYPE_COLOURTABLE = 9


def pack_u32(value):
    return struct.pack("<I", int(value) & 0xFFFFFFFF)


def utf16z(text):
    return (text + "\0").encode("utf-16-le")


def make_param(type_id, value):
    s = value or ""
    out = bytearray()
    out += pack_u32(type_id)
    wch_count = len(utf16z(s)) // 2 - 1
    out += pack_u32(wch_count)
    out += utf16z(s)
    out += b"\x00\x00"
    return bytes(out)


def build_pack(param_map, files): # big and ugly but works
    pack = bytearray()
    pack += pack_u32(3)
    keys = sorted(param_map.keys())
    pack += pack_u32(len(keys))
    for k in keys:
        pack += make_param(k, param_map[k])

    pack += pack_u32(len(files))
    for f in files:
        name = f.get("name") or ""
        pack += struct.pack("<I", len(f.get("payload") or b"") & 0xFFFFFFFF)
        pack += struct.pack("<I", int(f.get("type")) & 0xFFFFFFFF)
        name_wch_count = len(utf16z(name)) // 2 - 1
        pack += struct.pack("<I", name_wch_count)
        pack += (name + "\0").encode("utf-16-le")
        pack += b"\x00\x00"

    for f in files:
        params = f.get("params", [])
        pack += pack_u32(len(params))
        for (tid, val) in params:
            pack += make_param(tid, val)
        pack += f.get("payload") or b""

    return bytes(pack)


def create_packs(source_dir, pack_id=6767, scale=16, output_path=None, display_name_override=None, description_override=None):
    if not output_path:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        output_root = os.path.join(base_dir, "output")
        if display_name_override and display_name_override.strip() != "":
            pack_name = display_name_override.strip()
        else:
            pack_name = os.path.basename(os.path.abspath(source_dir))
        pack_dirname = "".join(c for c in pack_name if c.isalnum() or c in " -_.").strip().replace(" ", "_")
        if not pack_dirname:
            pack_dirname = "my_awesome_pack"
        output_path = os.path.join(output_root, pack_dirname)
    data_path = os.path.join(output_path, "Data")
    os.makedirs(data_path, exist_ok=True)

    all_files = []
    for root, dirs, filenames in os.walk(source_dir):
        for f in filenames:
            if f.lower().endswith(".png") or f.lower().endswith(".col"):
                all_files.append(os.path.join(root, f))
    if not all_files:
        raise RuntimeError("No files found in source folder; wrong folder structure?")

    display_name = None
    pack_version = None

    if display_name_override is not None and display_name_override != "":
        display_name = display_name_override
    pack_description = None
    if description_override is not None and description_override != "":
        pack_description = description_override

    data_map = {}
    for p in all_files:
        rel = os.path.relpath(p, source_dir).replace("\\", "/")
        name_lower = os.path.basename(p).lower()
        if name_lower in ["icon.png", "comparison.png", "banner.png", "languages.loc"]:
            continue
        if name_lower == "colours.col":
            internal_path = "colours.col"
        elif rel.lower().startswith("res/"):
            internal_path = rel
        else:
            internal_path = "res/" + rel
        with open(p, "rb") as f:
            data_map[internal_path] = f.read()
    # config
    files = []
    files.append({"type": TYPE_PACKCONFIG, "name": "0", "params": [(7, str(pack_id)), (12, "0")], "payload": b""})
    for rel in sorted(data_map.keys()):
        t = TYPE_COLOURTABLE if rel.lower().endswith(".col") else TYPE_TEXTURE
        files.append({"type": t, "name": rel, "params": [], "payload": data_map[rel]})

    data_bytes = build_pack(PARAM_ID_ENUM, files)
    data_filename = "x" + str(scale) + "Data.pck"

    with open(os.path.join(data_path, data_filename), "wb") as f:
        f.write(data_bytes)

    # info pck
    info_files = []
    for img_name in ["icon.png", "banner.png", "comparison.png"]:
        full_p = os.path.join(source_dir, img_name)
        if os.path.exists(full_p):
            with open(full_p, "rb") as f:
                info_files.append({"type": TYPE_TEXTURE, "name": img_name, "params": [], "payload": f.read()})
    if not info_files:
        raise RuntimeError("You need at least icon.png in the source folder")
    info_bytes = build_pack(PARAM_ID_ENUM, info_files)

    top_files = []
    top_files.append({"type": TYPE_PACKCONFIG, "name": "0", "params": [(7, str(pack_id)), (12, str(pack_version if pack_version is not None else 0))], "payload": b""})



    if display_name is not None or pack_description is not None:
        def int32be(v):
            return ((v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)

        def int16be(v):
            return ((v >> 8) & 0xFF, v & 0xFF)

        def fourj_utf_8(text):
            if text is None:
                text = ""
            out = bytearray()
            for ch in text:
                c = ord(ch)
                if 0x0001 <= c <= 0x007F:
                    out.append(c & 0xFF)
                elif c > 0x07FF:
                    out.append(0xE0 | ((c >> 12) & 0x0F))
                    out.append(0x80 | ((c >> 6) & 0x3F))
                    out.append(0x80 | (c & 0x3F))
                else:
                    out.append(0xC0 | ((c >> 6) & 0x1F))
                    out.append(0x80 | (c & 0x3F))
            return bytes(out)

        def write_utf(buf, text):
            b = fourj_utf_8(text)
            buf.extend(bytes(int16be(len(b))))
            buf.extend(b)

        loc = []
        if display_name is not None:
            loc.append(("IDS_DISPLAY_NAME", display_name))
        if pack_description is not None:
            loc.append(("IDS_TP_DESCRIPTION", pack_description))

        language_bytes = {}
        for lid in locales:
            lang_bytes = bytearray()
            lang_bytes.extend(bytes(int32be(1)))  # langVersion
            lang_bytes.append(0)  # isStatic byte
            write_utf(lang_bytes, lid)  # langId

            lang_bytes.extend(bytes(int32be(len(loc))))
            for (k, v) in loc:
                write_utf(lang_bytes, k)
                write_utf(lang_bytes, v)
            language_bytes[lid] = bytes(lang_bytes)


        out = bytearray()
        out.extend(bytes(int32be(1)))
        out.extend(bytes(int32be(len(language_bytes))))

        blobs = bytearray()
        for lid in sorted(language_bytes.keys()):
            write_utf(out, lid)
            blob = language_bytes[lid]
            out.extend(bytes(int32be(len(blob))))
            blobs.extend(blob) # actually write the loc

        out.extend(blobs)

        languagesloc = bytes(out)
        top_files.append({"type": TYPE_LOCALISATION, "name": "languages.loc", "params": [], "payload": languagesloc})

    info_name = f"x{scale}/x{scale}Info.pck"

    if pack_version is not None:
        top_params = [(1, "0"), (0, ""), (12, str(pack_version)), (11, data_filename)]
    else:
        top_params = [(1, "0"), (0, ""), (11, data_filename)]

    top_files.append({"type": TYPE_TEXTUREPACK, "name": info_name, "params": top_params, "payload": info_bytes})
    top_bytes = build_pack(PARAM_ID_ENUM, top_files)
    with open(os.path.join(output_path, "TexturePack.pck"), "wb") as f:
        f.write(top_bytes)

    return os.path.abspath(output_path)


def launch_console(): # such a stupid fix
    if os.name != 'nt':
        return False
    try:
        import ctypes
        ATTACH_PARENT_PROCESS = -1
        if ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            try:
                sys.stdout = open("CONOUT$", "w")
                sys.stderr = open("CONOUT$", "w")
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


def main():
    parser = argparse.ArgumentParser(description="Build TexturePack.pck from a folder")
    parser.add_argument("source_dir", nargs="?", help="Source folder containing the pack")
    parser.add_argument("--scale", choices=("16", "32"), default="16", help="Texture scale (16 or 32) Defaults to 16")
    parser.add_argument("--id", type=int, default=6767, help="Pack ID (numeric) Default: 6767")
    parser.add_argument("--gui", action="store_true", help="Open GUI")
    args = parser.parse_args()

    initial_source = None
    if len(sys.argv) == 1:
        args.gui = True
    elif args.source_dir and os.path.isdir(args.source_dir) and len(sys.argv) == 2:
        args.gui = True
        initial_source = os.path.abspath(args.source_dir)

    if len(sys.argv) > 1 and not args.gui:
        launch_console()

    if args.gui:
        try:
            import tkinter as tk
            from tkinter import filedialog, messagebox
        except Exception:
            print("You need Tkinter for the GUI to work! use the cmd instead")
            return

        root = tk.Tk()
        root.title("MLCE Texture Pack Builder")

        tk.Label(root, text="Source folder:").grid(row=1, column=0, sticky="w")
        src_var = tk.StringVar()
        if initial_source:
            src_var.set(initial_source)
        src_frame = tk.Frame(root)
        src_frame.grid(row=1, column=1, padx=4, pady=10, sticky="we")
        src_entry = tk.Entry(src_frame, textvariable=src_var)
        src_entry.pack(side="left", fill="x", expand=True)

        img_holder = None
        image_label = tk.Label(root)
        image_label.grid(row=0, column=3, rowspan=3, padx=8, pady=4)

        pack_detect_var = tk.StringVar(value="")
        tk.Label(root, textvariable=pack_detect_var, fg="#747474").grid(row=5, column=1, sticky="w", padx=4)

        def update_icon_preview(folder):
            nonlocal img_holder
            icon_path = os.path.join(folder, "icon.png")
            if not os.path.exists(icon_path):
                image_label.config(image="", text="No icon.png")
                img_holder = None
                terrain_path = os.path.join(folder, "res", "terrain.png")
                try:
                    if os.path.exists(terrain_path):
                        timg = tk.PhotoImage(file=terrain_path)
                        w = timg.width()
                        h = timg.height()
                        if w == 256 and h == 256:
                            pack_detect_var.set("256x256 atlas detected, this pack will only work on Minecraft Legacy Console Edition")
                        elif w == 256 and h == 512:
                            pack_detect_var.set("256x512 atlas detected, this DLC will only work on Minecraft Consoles fork")
                        elif w == 512 and h == 512:
                            pack_detect_var.set("512x512 atlas detected, this pack will only work on Minecraft Legacy Console Edition")
                        elif w == 512 and h == 1024:
                            pack_detect_var.set("512x1024 atlas detected, this DLC will only work on Minecraft Consoles fork")
                        else:
                            pack_detect_var.set("")
                    else:
                        pack_detect_var.set("")
                except Exception:
                    pack_detect_var.set("")
                return
            try:
                img_holder = tk.PhotoImage(file=icon_path)
                image_label.config(image=img_holder, text="")
            except Exception:
                image_label.config(image="", text="Can't load icon")
                img_holder = None
            terrain_path = os.path.join(folder, "res", "terrain.png")
            try:
                if os.path.exists(terrain_path):
                    timg = tk.PhotoImage(file=terrain_path)
                    w = timg.width()
                    h = timg.height()
                    if w == 256 and h == 256:
                        pack_detect_var.set("256x256 atlas detected, this pack will only work on Minecraft Legacy Console Edition")
                    elif w == 256 and h == 512:
                        pack_detect_var.set("256x512 atlas detected, this DLC will only work on Minecraft Consoles fork")
                    elif w == 512 and h == 512:
                        pack_detect_var.set("512x512 atlas detected, this pack will only work on Minecraft Legacy Console Edition")
                    elif w == 512 and h == 1024:
                        pack_detect_var.set("512x1024 atlas detected, this DLC will only work on Minecraft Consoles fork")
                    else:
                        pack_detect_var.set("")
                else:
                    pack_detect_var.set("")
            except Exception:
                pack_detect_var.set("")
                

        def browse():
            folder = filedialog.askdirectory()
            if folder:
                src_var.set(folder)
                update_icon_preview(folder)

        def show_help():
            help_win = tk.Toplevel(root)
            help_win.title("Help")
            help_win.geometry("520x240")
            tk.Label(help_win, text="Whatcha need help with?").pack(anchor="w", padx=8, pady=4)
            txt = tk.Text(help_win, wrap="word")
            txt.pack(fill="both", expand=True, padx=8, pady=4)
            txt.insert("1.0", "If your game crashes with the DLC loaded: \nMake sure you're using the correct pack template for the game, MCLE uses a 256x256 terrain.png, and the Minecraft-Consoles fork requires a 256x512 terrain.png for the features it adds.")
            tk.Button(help_win, text="Close", command=help_win.destroy).pack(pady=6)

        tk.Button(src_frame, text="Browse...", command=browse).pack(side="right", padx=(4,0))

        tk.Label(root, text="Pack ID:").grid(row=2, column=0, sticky="w")
        id_var = tk.StringVar(value=str(args.id))
        tk.Entry(root, textvariable=id_var).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        tk.Label(root, text="Keep this at 6767 if unsure", fg="#747474").grid(row=3, column=1, sticky="w", padx=4)

        tk.Label(root, text="Resolution:").grid(row=4, column=0, sticky="w")
        scale_var = tk.StringVar(value=args.scale)
        tk.Radiobutton(root, text="16x", variable=scale_var, value="16").grid(row=4, column=1, sticky="w")
        tk.Radiobutton(root, text="32x", variable=scale_var, value="32").grid(row=4, column=1, sticky="e")

        tk.Label(root, text="Pack Name:").grid(row=6, column=0, sticky="w")
        name_placeholder = "Pack Name"
        name_var = tk.StringVar(value="")
        name_entry = tk.Entry(root, textvariable=name_var, width=60)
        name_entry.grid(row=6, column=1, padx=4, pady=4, sticky="w")

        tk.Label(root, text="Description:").grid(row=7, column=0, sticky="w")
        desc_placeholder = "Description"
        desc_var = tk.StringVar(value="")
        desc_entry = tk.Entry(root, textvariable=desc_var, width=60)
        desc_entry.grid(row=7, column=1, padx=4, pady=4, sticky="w")

        def placeholder_text(entry, var, placeholder):
            var.set(placeholder)
            entry.config(fg="#8F8F8F")

            def focus_in(_):
                if var.get() == placeholder:
                    entry.delete(0, "end")
                    entry.config(fg="black")

            def focus_out(_):
                if var.get().strip() == "":
                    var.set(placeholder)
                    entry.config(fg="#838282")

            entry.bind("<FocusIn>", focus_in)
            entry.bind("<FocusOut>", focus_out)

        placeholder_text(name_entry, name_var, name_placeholder)
        placeholder_text(desc_entry, desc_var, desc_placeholder)

        def convert():
            src = src_var.get()
            try:
                pid = int(id_var.get())
            except Exception:
                messagebox.showerror("Error", "Enter a number!")
                return
            sc = int(scale_var.get())
            if not src or not os.path.isdir(src):
                messagebox.showerror("Error", "Please select a valid source directory")
                return
            try:
                displaynametxt = name_var.get()
                displaydesctxt = desc_var.get()
                out = create_packs(src, pack_id=pid, scale=sc, display_name_override=displaynametxt, description_override=displaydesctxt)
                messagebox.showinfo("Done", f"All done! your pack is at {out}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        root.grid_columnconfigure(1, weight=0)
        root.grid_columnconfigure(3, weight=1)
        root.grid_rowconfigure(8, weight=1)

        tk.Button(root, text="Convert!", command=convert, width=20).grid(row=9, column=1, pady=8, padx=90, sticky="w")
        tk.Button(root, text="Help", command=show_help).grid(row=9, column=3, pady=8, padx=8, sticky="e")

        if initial_source:
            root.after(100, lambda: update_icon_preview(initial_source))
        root.mainloop()
        return

    if not args.gui:
        if not args.source_dir:
            parser.print_help()
            return
        out = create_packs(args.source_dir, pack_id=args.id, scale=int(args.scale))
        print("All done! Output:", out)


if __name__ == "__main__":
    main()
