import sys
import os
import struct

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

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <source_dir>")
        return

    source_dir = sys.argv[1]
    pack_id = 6767 # i am SO FUNNY
    
    output_path = os.path.join(os.getcwd(), "output")
    data_path = os.path.join(output_path, "Data")
    
    if not os.path.exists(data_path):
        os.makedirs(data_path)

    all_files = []     # ugly ugly but it works
    for root, dirs, filenames in os.walk(source_dir):
        for f in filenames:
            if f.lower().endswith(".png") or f.lower().endswith(".col"):
                all_files.append(os.path.join(root, f))

    if not all_files:
        print("Error: No files found, wrong folder structure?")
        return

    data_map = {}
    for p in all_files:
        rel = os.path.relpath(p, source_dir).replace("\\", "/")
        name_lower = os.path.basename(p).lower()
        if name_lower in ["icon.png", "comparison.png", "banner.png", "languages.loc"]:
            continue
        
        # not 100% sure of the internal structure, i just extracted all the pngs from the candy pack wihout structure inside so i'm just making guesses until it works
        internal_path = ""
        if rel.lower().startswith("res/"):
            internal_path = rel
        elif rel.lower() == "colours.col":
            internal_path = "colours.col"
        else:
            internal_path = "res/" + rel
            
        with open(p, "rb") as f:
            data_map[internal_path] = f.read()

    # x16Data .pck so packconfig + .pngs + .col
    x16_files = []
    x16_files.append({"type": TYPE_PACKCONFIG, "name": "0", "params": [(1, "0"), (2, "0")], "payload": b""})
    
    for rel in sorted(data_map.keys()):
        t = TYPE_COLOURTABLE if rel.lower().endswith(".col") else TYPE_TEXTURE
        x16_files.append({"type": t, "name": rel, "params": [], "payload": data_map[rel]})

    x16_bytes = build_pack(PARAM_TYPE_TO_NAME, x16_files)
    with open(os.path.join(data_path, "x16Data.pck"), "wb") as f:
        f.write(x16_bytes)

    # info pack.pck
    info_files = []
    for img_name in ["icon.png", "banner.png", "comparison.png"]:
        full_p = os.path.join(source_dir, img_name)
        if os.path.exists(full_p):
            with open(full_p, "rb") as f:
                info_files.append({"type": TYPE_TEXTURE, "name": img_name, "params": [], "payload": f.read()})

    if not info_files:
        # For all i know it could work wihout it but i'm not taking risks
        print("You need at least icon.png")
        return

    info_bytes = build_pack(PARAM_TYPE_TO_NAME, info_files)

    top_files = []
    top_files.append({"type": TYPE_PACKCONFIG, "name": "0", "params": [(1, str(pack_id)), (2, "0")], "payload": b""})
    
    # I dont see how it works, i havent seen it in other texture packs but apparently 4J uses the languages.loc in a texture pack first so i'm including it
    lang_path = os.path.join(source_dir, "languages.loc") # look at DLCTexturePack.cpp DLCLocalisationFile, lots of potential :3
    if os.path.exists(lang_path):
        with open(lang_path, "rb") as f:
            top_files.append({"type": TYPE_LOCALISATION, "name": "languages.loc", "params": [], "payload": f.read()})
            
    top_files.append({"type": TYPE_TEXTUREPACK, "name": "x16/x16Info.pck", "params": [(1, "0"), (0, " "), (3, "x16Data.pck")], "payload": info_bytes})

    top_bytes = build_pack(PARAM_TYPE_TO_NAME, top_files)
    with open(os.path.join(output_path, "TexturePack.pck"), "wb") as f:
        f.write(top_bytes)

    print("All done!")

if __name__ == "__main__":
    main()