#!/usr/bin/env python3
import struct
import json
import sys
from pathlib import Path

def u16(b, off): return struct.unpack_from("<H", b, off)[0], off+2
def u32(b, off): return struct.unpack_from("<I", b, off)[0], off+4

def packvalue_to_int(v):
    # v = (x+1)*2  => x = v//2 - 1
    return v//2 - 1

def read_packbytes(b, off):
    size, off = u32(b, off)
    end = off + size
    if end > len(b): raise EOFError("packbytes exceeds buffer")  # noqa: E701
    return b[off:end], end

def decode_field_record(blob):
    off = 0
    nfields, off = u16(blob, off)  # 4/5/6/7
    # tag0: name placeholder
    t0, off = u16(blob, off)
    assert t0 == 0, f"field tag0!=0x0000 ({t0:#04x})"

    # tag1: buildin or skip
    t1, off = u16(blob, off)
    buildin = None
    if t1 != 1:  # not skip
        buildin = packvalue_to_int(t1)

    # tag2: type or skip
    t2, off = u16(blob, off)
    type_id = None
    if t2 != 1:  # not skip
        type_id = packvalue_to_int(t2)

    # tag3: field tag (required)
    t3, off = u16(blob, off)
    field_tag = packvalue_to_int(t3)

    array = False
    key_tag = None
    map_tag = None

    if nfields >= 5:
        t4, off = u16(blob, off)
        array = (packvalue_to_int(t4) == 1)  # should be 1
    if nfields >= 6:
        t5, off = u16(blob, off)
        key_tag = packvalue_to_int(t5)
    if nfields >= 7:
        t6, off = u16(blob, off)
        map_tag = packvalue_to_int(t6)

    # name (external object)
    name_bytes, off = read_packbytes(blob, off)
    name = name_bytes.decode('utf-8', errors='ignore')

    return {
        "name": name,
        "tag": field_tag,
        "buildin": buildin,   # 0=int,1=bool,2=string/binary,3=double, None=custom type
        "type_id": type_id,   # reference to type index (0-based) if custom
        "array": array,
        "key_tag": key_tag,
        "map": (map_tag is not None)
    }

def decode_fields_blob(b):
    off = 0
    items = []
    while off < len(b):
        rec, off2 = read_packbytes(b, off)
        items.append(decode_field_record(rec))
        off = off2
    return items

def decode_type_record(blob):
    off = 0
    nfields, off = u16(blob, off)  # 1 or 2
    # tag0 name placeholder
    t0, off = u16(blob, off)
    assert t0 == 0, f"type tag0!=0x0000 ({t0:#04x})"
    if nfields == 1:
        name_bytes, off = read_packbytes(blob, off)
        name = name_bytes.decode('utf-8', errors='ignore')
        fields = []
    else:
        # tag1 field array placeholder
        t1, off = u16(blob, off)
        assert t1 == 0, f"type tag1!=0x0000 ({t1:#04x})"
        name_bytes, off = read_packbytes(blob, off)
        name = name_bytes.decode('utf-8', errors='ignore')
        fields_blob, off = read_packbytes(blob, off)
        fields = decode_fields_blob(fields_blob)
    return {"name": name, "fields": fields}

def decode_types_blob(b):
    off = 0
    items = []
    while off < len(b):
        rec, off2 = read_packbytes(b, off)
        items.append(decode_type_record(rec))
        off = off2
    return items

def decode_proto_record(blob):
    off = 0
    nfields, off = u16(blob, off)  # 2/3/4/5
    t0, off = u16(blob, off)       # name placeholder
    assert t0 == 0, f"proto tag0!=0x0000 ({t0:#04x})"
    tag_u16, off = u16(blob, off)  # tag
    ptag = packvalue_to_int(tag_u16)

    req = None
    resp = None
    confirm = False

    if nfields >= 3:
        t2, off = u16(blob, off)
        if t2 != 1:  # request present
            req = packvalue_to_int(t2)
    if nfields >= 4:
        t3, off = u16(blob, off)
        if t3 == 1:
            # could be confirm field (nfields==5)
            if nfields == 5:
                c, off = u16(blob, off)
                confirm = (packvalue_to_int(c) == 1)
        else:
            resp = packvalue_to_int(t3)

    name_bytes, off = read_packbytes(blob, off)
    name = name_bytes.decode('utf-8', errors='ignore')

    return {"name": name, "tag": ptag, "request_id": req, "response_id": resp, "confirm": confirm}

def decode_protos_blob(b):
    off = 0
    items = []
    while off < len(b):
        rec, off2 = read_packbytes(b, off)
        items.append(decode_proto_record(rec))
        off = off2
    return items

def decode_group(b):
    off = 0
    count, off = u16(b, off)              # 1 or 2
    t0, off = u16(b, off); assert t0 == 0  # noqa: E702
    t1 = None
    if count >= 2:
        t1, off = u16(b, off); assert t1 == 0  # noqa: E702

    types_blob, off = read_packbytes(b, off)
    protos_blob = b''
    if count >= 2:
        protos_blob, off = read_packbytes(b, off)

    types = decode_types_blob(types_blob)
    # Build name -> id mapping by sorted order used when packing:
    # In packer, types are sorted by name to assign ids (0..N-1).
    # The blob you have should already be in that same order, so:
    type_id_by_name = {t["name"]: idx for idx, t in enumerate(types)}
    for t in types:
        for f in t["fields"]:
            if f["buildin"] is None and f["type_id"] is not None:
                # later you can resolve to name if needed
                pass

    protos = decode_protos_blob(protos_blob) if protos_blob else []

    return {"types": types, "protocols": protos, "type_id_by_name": type_id_by_name}

def main():
    if len(sys.argv) != 2:
        print("Usage: python proto2json.py spb.bytes")
        sys.exit(1)
    p = Path(sys.argv[1])
    data = p.read_bytes()
    decoded = decode_group(data)

    # Optionally resolve custom field type ids -> names
    names_by_id = {v:k for k,v in decoded["type_id_by_name"].items()}
    for t in decoded["types"]:
        for f in t["fields"]:
            if f["buildin"] is None and f["type_id"] is not None:
                f["type_name"] = names_by_id.get(f["type_id"])

    out = p.with_suffix(".json")
    out.write_text(json.dumps(decoded, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Decoded → {out}")

if __name__ == "__main__":
    main()
