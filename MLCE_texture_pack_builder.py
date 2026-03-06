import argparse
import struct
import sys
from pathlib import Path

# it writes two .pck files, an info pack (the icon etc) and a texture pack
# TODO potentially .arc file for the UI? i know it uses .swf files and i have no idea how they work

PARAM_TYPE_TO_NAME = {0: "DISPLAYNAME", 1: "PACKID", 2: "PACKVERSION", 3: "DATAPATH", 4: "ANIM"}
TYPE_TEXTURE = 2 # this is a mess but those are the internal IDs the game expects
TYPE_PACKCONFIG = 4 # i.e that stupid DLCTexturePack.cpp and DLCManager.h i've been fighting with
TYPE_TEXTUREPACK = 5
TYPE_LOCALISATION = 6
TYPE_COLOURTABLE = 9

# bunch of macros, which should work more or less
def make_texture_from_path(path, name=None):
    name = name or path.name
    return {"type": TYPE_TEXTURE, "name": name, "params": [], "payload": path.read_bytes()}

def make_texture_from_bytes(data_bytes, name):
    return {"type": TYPE_TEXTURE, "name": name, "params": [], "payload": data_bytes}

def make_packconfig(pack_id):
    return {"type": TYPE_PACKCONFIG, "name": "0", "params": [(1, str(pack_id)), (2, "0")], "payload": b""}

def make_loc(path):
    return {"type": TYPE_LOCALISATION, "name": "languages.loc", "params": [], "payload": path.read_bytes()}

def make_texturepack_entry(info_bytes): # i miss cpp types it feels so wrong to just pack bytes like that
    return {"type": TYPE_TEXTUREPACK, "name": "x16/x16Info.pck", "params": [(1, "0"), (0, " "), (3, "x16Data.pck")], "payload": info_bytes}

def add_packconfig(files, pack_id=0):
    files.append(make_packconfig(pack_id))

def add_texture_bytes(files, name, data_bytes):
    files.append(make_texture_from_bytes(data_bytes, name))

def add_colourtable_bytes(files, name, data_bytes):
    entry = make_texture_from_bytes(data_bytes, name)
    entry["type"] = TYPE_COLOURTABLE
    files.append(entry)

def pack_u32(value):
    return struct.pack("<I", int(value) & 0xFFFFFFFF) # it NEEDS to be 32 bits little endian because this is for PC, for PS3 we'd need big endian

def utf16z(text):
    return (text + "\0").encode("utf-16-le")

def make_param_record(type_id, value): # TODO code repetition BAD
    s = value or ""
    out = bytearray()
    out += pack_u32(type_id)
    out += pack_u32(len(s))
    out += utf16z(s)
    out += b"\x00\x00" 
    return bytes(out)

def make_file_header(size, file_type, name):
    name = name or ""
    out = bytearray()
    out += struct.pack("<I", int(size) & 0xFFFFFFFF)
    out += struct.pack("<I", int(file_type) & 0xFFFFFFFF)
    out += struct.pack("<I", len(name))
    out += (name + "\0").encode("utf-16-le")
    out += b"\x00\x00" # 4J wants 2 bytes padding
    return bytes(out)


def build_pack(param_map, files):
    out = bytearray()
    out += pack_u32(3)  # pack version, 4J's minimum is at 3
    keys = sorted(param_map.keys())
    out += pack_u32(len(keys))

    for k in keys:
        out += make_param_record(k, param_map[k])

    out += pack_u32(len(files))

    for f in files:
        out += make_file_header(len(f["payload"]), f["type"], f["name"])

    for f in files:
        params = f.get("params", [])
        out += pack_u32(len(params))
        for (tid, val) in params:
            out += make_param_record(tid, val)
        out += f["payload"]

    return bytes(out)


def find_files(src: Path, exts): # ugly ugly but it works
    want = {e.lower().lstrip('.') for e in exts}
    found = []
    for p in sorted(src.rglob("*")): # recursively take the files, if it matches ext, we keep it
        if not p.is_file():
            continue
        if p.suffix.lower().lstrip('.') in want:
            found.append(p)
    return found


def data_relative(path: Path, src: Path):
    rel = path.relative_to(src).as_posix()
    if rel.lower().startswith("res/"): # not 100% sure of the internal structure, i just extracted all the pngs from the candy pack wihout structure inside so i'm just making guesses until it works
        return rel
    if rel.lower() == "colours.col":
        return "colours.col"
    return "res/" + rel


def build_texture_pack(source_dir: str, pack_id: int, pack_name: str, include_exts):
    src = Path(source_dir).resolve()
    out_root = Path(__file__).resolve().parent / "output"
    data_dir = out_root / "Data"
    out_root.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    files = find_files(src, include_exts)
    if not files:
        raise SystemExit("Error: No files found, wrong folder structure?")
    
    data_map = {}
    for p in files:
        key = p.relative_to(src).as_posix().lower()
        if key in {"icon.png", "comparison.png", "banner.png", "languages.loc"}:
            continue
        data_map[data_relative(p, src)] = p.read_bytes()

    if not data_map:
        raise SystemExit("Error: This should never happen DM me if it does")

    # x16Data .pck so packconfig + .pngs + .col
    files = []
    add_packconfig(files, 0)
    for rel in sorted(data_map.keys()):
        if rel.lower().endswith('.col'):
            add_colourtable_bytes(files, rel, data_map[rel])
        else:
            add_texture_bytes(files, rel, data_map[rel])

    x16bytes = build_pack(PARAM_TYPE_TO_NAME, files)
    x16path = data_dir / "x16Data.pck"
    x16path.write_bytes(x16bytes)

    # info pack.pck
    info_files = []
    icon = src / "icon.png"
    banner = src / "banner.png"
    comp = src / "comparison.png"

    if icon.exists():
        info_files.append(make_texture_from_path(icon, "icon.png"))
    if banner.exists():
        info_files.append(make_texture_from_path(banner, "banner.png"))
    if comp.exists():
        info_files.append(make_texture_from_path(comp, "comparison.png"))

    if not info_files:
        raise SystemExit("You need at least icon.png") # For all i know it could work wihout it but i'm not taking risks

    info_bytes = build_pack(PARAM_TYPE_TO_NAME, info_files)

    top_files = []
    top_files.append(make_packconfig(pack_id))
    lang = src / "languages.loc" # I dont see how it works, i havent seen it in other texture packs but apparently you can override the languages.loc in a texture pack so i'm including it
    if lang.exists(): # REF DLCTexturePack.cpp DLCLocalisationFile, lots of potential :3
        top_files.append(make_loc(lang))
    top_files.append(make_texturepack_entry(info_bytes))

    top_bytes = build_pack(PARAM_TYPE_TO_NAME, top_files)
    top_path = out_root / "TexturePack.pck"
    top_path.write_bytes(top_bytes)

    return None


def parse_args():
    if len(sys.argv) >= 2 and all(not a.startswith("-") for a in sys.argv[1:]): # If we drag the folder on the script
        sys.argv[:] = [sys.argv[0], "--source-dir", sys.argv[1]]

    p = argparse.ArgumentParser(description="LCE pack builder, DM me for folder layout cause it needs to be very specific")
    p.add_argument("--source-dir", required=True)
    p.add_argument("--pack-id", type=int, default=6767) # kill me
    p.add_argument("--pack-name", default="Custom pack")
    p.add_argument("--include-ext", nargs="+", default=["png", "col"])
    return p.parse_args()


def main():
    args = parse_args()
    build_texture_pack(args.source_dir, args.pack_id, args.pack_name, args.include_ext)
    print("All done!")


if __name__ == "__main__":
    main()
