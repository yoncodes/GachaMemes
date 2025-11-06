#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def typename(buildin, type_name):
    if buildin is None:
        return type_name or "?"
    return {0: "integer", 1: "boolean", 2: "string", 3: "double"}.get(buildin, "?")

def field_line(f):
    tname = typename(f["buildin"], f.get("type_name"))
    if f["array"]:
        tname = "*" + tname
    extras = []
    if f["key_tag"] is not None:
        extras.append(f"key_tag={f['key_tag']}")
    if f["map"]:
        extras.append("map")
    extra = f" -- {' '.join(extras)}" if extras else ""
    return f"  {f['name']} {f['tag']} : {tname}{extra}"

def type_block(t):
    lines = [f".type {t['name']} {{"] + [field_line(f) for f in t["fields"]] + ["}"]
    return "\n".join(lines)

def proto_block(p, types):
    name = p["name"]
    tag = p["tag"]
    out = [f".protocol {name} {tag} {{"]
    if p.get("request_id") is not None:
        req_name = types.get(p["request_id"], f"type{p['request_id']}")
        out.append(f"  request {req_name}")
    if p.get("response_id") is not None:
        resp_name = types.get(p["response_id"], f"type{p['response_id']}")
        out.append(f"  response {resp_name}")
    if p.get("confirm"):
        out.append("  response nil -- confirm")
    out.append("}")
    return "\n".join(out)

def main():
    if len(sys.argv) < 2:
        print("Usage: python json_to_sproto.py spb.json")
        sys.exit(1)
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))

    type_list = data["types"]
    proto_list = data["protocols"]
    name_by_id = {v: k for k, v in data["type_id_by_name"].items()}

    blocks = []
    for t in type_list:
        blocks.append(type_block(t))
    for p in proto_list:
        blocks.append(proto_block(p, name_by_id))

    out_text = "\n\n".join(blocks)
    out_path = path.with_suffix(".sproto")
    out_path.write_text(out_text, encoding="utf-8")
    print(f"[+] Wrote {out_path} ({len(type_list)} types, {len(proto_list)} protocols)")

if __name__ == "__main__":
    main()
