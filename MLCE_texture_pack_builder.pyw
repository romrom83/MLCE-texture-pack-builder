import sys
import os
import struct
import argparse

# it writes two .pck files, an info pack (the icon etc) and a texture pack
# TODO potentially .arc file for the UI? i know it uses .swf files and i have no idea how they work

PARAM_TYPE_TO_NAME = {0: "DISPLAYNAME", 1: "PACKID", 2: "PACKVERSION", 3: "DATAPATH", 4: "ANIM"}
TYPE_TEXTURE = 2 # this is a mess but those are the internal IDs the game expects
TYPE_PACKCONFIG = 4 # i.e that stupid DLCTexturePack.cpp and DLCManager.h i've been fighting with
TYPE_TEXTUREPACK = 5
TYPE_LOCALISATION = 6
TYPE_COLOURTABLE = 9

def pack_u32(value):
    return struct.pack("<I", int(value) & 0xFFFFFFFF) # 32 bits little endian because this is for PC, for PS3 we'd need big endian, i think?

def utf16z(text):
    return (text + "\0").encode("utf-16-le")

def make_param(type_id, value):
    s = value or ""
    out = bytearray()
    out += pack_u32(type_id)
    out += pack_u32(len(s))
    out += utf16z(s)
    out += b"\x00\x00" # 4J internally wants 2 bytes padding
    return bytes(out)

def build_pack(param_map, files):
    pack = bytearray()
    pack += pack_u32(3) # pack version, 4J's minimum is at 3
    keys = sorted(param_map.keys())
    pack += pack_u32(len(keys))
    for k in keys:
        pack += make_param(k, param_map[k]) # this is the header

    pack += pack_u32(len(files))
    for f in files:
        name = f["name"] or ""
        pack += struct.pack("<I", len(f["payload"]) & 0xFFFFFFFF)
        pack += struct.pack("<I", int(f["type"]) & 0xFFFFFFFF)
        pack += struct.pack("<I", len(name))
        pack += (name + "\0").encode("utf-16-le")
        pack += b"\x00\x00" # 4J wants 2 bytes padding

    for f in files:
        # i miss cpp types god python is uglyy
        params = f.get("params", [])
        pack += pack_u32(len(params))
        for (tid, val) in params:
            pack += make_param(tid, val)
        pack += f["payload"]

    return bytes(pack)

def create_packs(source_dir, pack_id=6767, scale=16, output_path=None):
    if not output_path:
        output_path = os.path.join(os.getcwd(), "output")
    data_path = os.path.join(output_path, "Data")

    if not os.path.exists(data_path):
        os.makedirs(data_path, exist_ok=True)

    all_files = []     # ugly ugly but it works
    for root, dirs, filenames in os.walk(source_dir):
        for f in filenames:
            if f.lower().endswith(".png") or f.lower().endswith(".col"):
                all_files.append(os.path.join(root, f))

    if not all_files:
        raise RuntimeError("No files found in source folder; wrong folder structure?")

    data_map = {}
    for p in all_files:
        rel = os.path.relpath(p, source_dir).replace("\\", "/")
        name_lower = os.path.basename(p).lower()
        if name_lower in ["icon.png", "comparison.png", "banner.png", "languages.loc"]:
            continue

        internal_path = ""
        if rel.lower().startswith("res/"):
            internal_path = rel
        elif rel.lower() == "colours.col":
            internal_path = "colours.col"
        else:
            internal_path = "res/" + rel

        with open(p, "rb") as f:
            data_map[internal_path] = f.read()

    # Data pack (x16Data / x32Data)
    files = []
    files.append({"type": TYPE_PACKCONFIG, "name": "0", "params": [(1, "0"), (2, "0")], "payload": b""})
    for rel in sorted(data_map.keys()):
        t = TYPE_COLOURTABLE if rel.lower().endswith(".col") else TYPE_TEXTURE
        files.append({"type": t, "name": rel, "params": [], "payload": data_map[rel]})

    data_bytes = build_pack(PARAM_TYPE_TO_NAME, files)
    data_filename = f"x{int(scale)}Data.pck"
    with open(os.path.join(data_path, data_filename), "wb") as f:
        f.write(data_bytes)

    # info pack.pck
    info_files = []
    for img_name in ["icon.png", "banner.png", "comparison.png"]:
        full_p = os.path.join(source_dir, img_name)
        if os.path.exists(full_p):
            with open(full_p, "rb") as f:
                info_files.append({"type": TYPE_TEXTURE, "name": img_name, "params": [], "payload": f.read()})

    if not info_files:
        raise RuntimeError("You need at least icon.png in the source folder")

    info_bytes = build_pack(PARAM_TYPE_TO_NAME, info_files)

    top_files = []
    top_files.append({"type": TYPE_PACKCONFIG, "name": "0", "params": [(1, str(pack_id)), (2, "0")], "payload": b""})

    lang_path = os.path.join(source_dir, "languages.loc")
    if os.path.exists(lang_path):
        with open(lang_path, "rb") as f:
            top_files.append({"type": TYPE_LOCALISATION, "name": "languages.loc", "params": [], "payload": f.read()})

    info_name = f"x{int(scale)}/x{int(scale)}Info.pck"
    top_files.append({"type": TYPE_TEXTUREPACK, "name": info_name, "params": [(1, "0"), (0, " "), (3, data_filename)], "payload": info_bytes})

    top_bytes = build_pack(PARAM_TYPE_TO_NAME, top_files)
    with open(os.path.join(output_path, "TexturePack.pck"), "wb") as f:
        f.write(top_bytes)

    return os.path.abspath(output_path)


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
        src_entry = tk.Entry(root, textvariable=src_var, width=60)
        src_entry.grid(row=1, column=1, padx=4, pady=10)

        img_holder = None
        image_label = tk.Label(root)
        image_label.grid(row=0, column=3, rowspan=3, padx=8, pady=4)

        def browse():
            d = filedialog.askdirectory()
            if d:
                src_var.set(d)
                update_icon_preview(d)

        def update_icon_preview(folder):
            nonlocal img_holder
            icon_path = os.path.join(folder, "icon.png")
            if not os.path.exists(icon_path):
                image_label.config(image="", text="No icon.png")
                img_holder = None
                return
            
            try:
                from PIL import Image, ImageTk
                img = Image.open(icon_path)
                previewheight, previewwidth = 256, 256
                imgwidth, imageheight = img.size
                scale = min(previewheight / imgwidth, previewwidth / imageheight)
                new_size = int(imgwidth * scale), int(imageheight * scale)
                img = img.resize(new_size, Image.LANCZOS)
                img_holder = ImageTk.PhotoImage(img)
                image_label.config(image=img_holder, text="")
            except Exception:
                try:
                    img_holder = tk.PhotoImage(file=icon_path) # if they dont have PIL we just display the image
                    image_label.config(image=img_holder, text="")
                except Exception:
                    image_label.config(image="", text="Can't load icon")
                    img_holder = None

        tk.Button(root, text="Browse...", command=browse).grid(row=1, column=2, padx=4)

        tk.Label(root, text="Pack ID:").grid(row=2, column=0, sticky="w")
        id_var = tk.StringVar(value=str(args.id))
        tk.Entry(root, textvariable=id_var).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        tk.Label(root, text="Keep this at 6767 if unsure", fg="#747474").grid(row=3, column=1, sticky="w", padx=4)

        tk.Label(root, text="Resolution:").grid(row=4, column=0, sticky="w")
        scale_var = tk.StringVar(value=args.scale)
        tk.Radiobutton(root, text="16x", variable=scale_var, value="16").grid(row=4, column=1, sticky="w")
        tk.Radiobutton(root, text="32x", variable=scale_var, value="32").grid(row=4, column=1, sticky="e")

        def do_convert():
            src = src_var.get()
            try:
                pid = int(id_var.get())
            except Exception:
                messagebox.showerror("Error", "Pack ID must be a number") # check all values are valid before giving it to converter
                return
            sc = int(scale_var.get())
            if not src or not os.path.isdir(src):
                messagebox.showerror("Error", "Please select a valid source directory")
                return
            try:
                out = create_packs(src, pack_id=pid, scale=sc)
                messagebox.showinfo("Done", f"All done! your pack is at {out}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(root, text="Convert!", command=do_convert, width=20).grid(row=5, column=1, pady=8)
        if initial_source:
            src_var.set(initial_source)
            root.after(100, lambda: update_icon_preview(initial_source))
            
        root.mainloop()
        return

    if not args.source_dir:
        print("Usage: python script.py <source_dir> or use --gui")
        return

    out = create_packs(args.source_dir, pack_id=args.id, scale=int(args.scale))
    print("All done! Output:", out)

if __name__ == "__main__":
    main()