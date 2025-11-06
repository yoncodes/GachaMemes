#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

TYPE_MAP = {0: "i32", 1: "bool", 2: "String", 3: "f64"}

def rust_ident(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)

def rust_struct(t):
    name = rust_ident(t["name"])
    lines = ["#[derive(Serialize, Deserialize, Debug, Clone)]",
             f"pub struct {name} {{"]
    for f in t["fields"]:
        typename = None
        if f["buildin"] is not None:
            typename = TYPE_MAP.get(f["buildin"], "i32")
        elif f.get("type_name"):
            typename = rust_ident(f["type_name"])
        else:
            typename = "i32"
        if f["array"]:
            typename = f"Vec<{typename}>"
        lines.append(f"    pub {rust_ident(f['name'])}: {typename},")
    lines.append("}\n")
    return "\n".join(lines)

def rust_enum(proto_list):
    lines = ["#[repr(u16)]", "#[derive(Debug, Clone, Copy, PartialEq, Eq)]", "pub enum MsgID {"]
    for p in proto_list:
        enum_name = re.sub(r'[^A-Za-z0-9]', '_', p["name"].title())
        lines.append(f"    {enum_name} = {p['tag']},")
    lines.append("}\n")
    lines.append("impl MsgID {")
    lines.append("    pub fn as_str(&self) -> &'static str {")
    lines.append("        match self {")
    for p in proto_list:
        enum_name = re.sub(r'[^A-Za-z0-9]', '_', p["name"].title())
        lines.append(f'            MsgID::{enum_name} => "{p["name"]}",')
    lines.append('            _ => "unknown",')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python sproto2rust.py spb.json")
        sys.exit(1)

    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    types = data["types"]
    protocols = data["protocols"]

    msg_rs = "\n".join(rust_struct(t) for t in types)
    msgid_rs = rust_enum(protocols)

    (path.parent / "message.rs").write_text(msg_rs, encoding="utf-8")
    (path.parent / "msgid.rs").write_text(msgid_rs, encoding="utf-8")
    print("[+] Generated message.rs and msgid.rs")

if __name__ == "__main__":
    main()
