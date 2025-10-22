import re
import json
import sys
from pathlib import Path

# Match both message and struct blocks
block_re = re.compile(r'([A-Za-z0-9_]+)\s*=\s*{', re.DOTALL)

# Match field lines inside blocks
# Handles both: {"field", "string", "desc"} and {"field", pt_pay_info, "desc", "repeated"}
field_re = re.compile(
    r'\{\s*"([^"]+)"\s*,\s*("?[\w\d_]+"?)\s*,\s*"([^"]*)"(?:\s*,\s*"?(\w+)"?)?\s*\}'
)

def extract_blocks(text: str):
    """Extract balanced {...} blocks following a name = { ... }"""
    results = []
    for m in block_re.finditer(text):
        name = m.group(1)
        start = m.end()
        depth, pos = 1, start
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        body = text[start:pos-1]
        results.append((name, body))
    return results

def parse_lua_protocol(path: Path):
    text = path.read_text(encoding="utf-8")
    result = {}

    for name, body in extract_blocks(text):
        lines = [l.strip().strip(",") for l in body.splitlines() if l.strip()]

        # Messages start with numeric msg_id, structs do not
        msg_id = None
        if lines and re.match(r'^\d+', lines[0]):
            msg_id = int(re.match(r'(\d+)', lines[0]).group(1))

        fields = []
        for f in field_re.finditer(body):
            fname, ftype, fdesc, frep = f.groups()
            fields.append({
                "name": fname,
                "type": ftype.strip('"'),
                "desc": fdesc or "",
                "repeated": (frep == "repeated")
            })

        entry = {"msg_name": name, "fields": fields}

        if msg_id is not None:
            result[msg_id] = entry
        else:
            result[name] = entry  # Struct definition

    return result

def merge_all(luas_dir: Path, out_json: Path):
    all_defs = {}
    for path in luas_dir.glob("*.lua"):
        proto = parse_lua_protocol(path)
        for key, entry in proto.items():
            if key in all_defs:
                print(f"[!] Duplicate {key} in {path.name}, skipping")
                continue
            all_defs[key] = entry

    out_json.write_text(
        json.dumps(all_defs, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[+] Wrote {len(all_defs)} entries → {out_json}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python parse_protocol.py <luas_dir> <mappings.json>")
        sys.exit(1)

    merge_all(Path(sys.argv[1]), Path(sys.argv[2]))
