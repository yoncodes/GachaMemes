import json
import re
from pathlib import Path
from typing import Dict, Set, Tuple, List


class ProtocolCodegen:
    """Code generator for game protocol messages mimicking protobuf"""
    
    # Type mapping from schema → Rust
    TYPE_MAP = {
        "int8": "i8",
        "int16": "i16", 
        "int32": "i32",
        "int64str": "String",  # keep as string
        "string": "String",
    }
    
    # Reserved keyword mapping
    FIELD_NAME_MAP = {
        "type": "msg_type",
        "match": "match_value",
        "return": "return_value",
        "use": "use_value",
        "move": "move_value",
        "ref": "ref_value",
    }
    
    def __init__(self, mapping_file: str = "mapping.json"):
        """Initialize codegen with message definitions"""
        self.mapping_file = mapping_file
        self.messages: Dict = {}
        self.known_structs: Set[str] = set()
        self.unknown_types: Set[str] = set()
        
    def load_messages(self) -> None:
        """Load message definitions from JSON"""
        with open(self.mapping_file, "r", encoding="utf8") as f:
            self.messages = json.load(f)
        
        # Collect all known struct names
        self.known_structs = {
            msg_def["msg_name"] 
            for msg_def in self.messages.values() 
            if "msg_name" in msg_def
        }
    
    @staticmethod
    def clean_string(s: str) -> str:
        """Remove whitespace and normalize string"""
        return re.sub(r'[\r\n\t ]+', ' ', s or "").strip()
    
    @staticmethod
    def clean_comment(comment: str) -> str:
        """Clean and truncate comments for Rust doc comments"""
        if not comment:
            return ""
        cleaned = ProtocolCodegen.clean_string(comment)
        return re.sub(r'[^\w\s\u4e00-\u9fff.,!?()\-]', '', cleaned)[:200]
    
    def safe_field_name(self, name: str) -> Tuple[str, str]:
        """Convert field name to safe Rust identifier, returning (safe_name, original_name)"""
        clean_name = self.clean_string(name)
        if clean_name in self.FIELD_NAME_MAP:
            return self.FIELD_NAME_MAP[clean_name], clean_name
        return clean_name, clean_name
    
    @staticmethod
    def is_valid_rust_identifier(name: str) -> bool:
        """Check if name is a valid Rust identifier"""
        return bool(name and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))
    
    def rust_type(self, t: str, repeated: bool) -> str:
        """Convert schema type to Rust type"""
        clean_t = self.clean_string(t)
        
        if clean_t in self.TYPE_MAP:
            base = self.TYPE_MAP[clean_t]
        elif clean_t in self.known_structs:
            base = clean_t
        else:
            # Forward reference or missing struct
            print(f"Warning: Unknown type '{clean_t}' - assuming it's a valid struct")
            base = clean_t
            
        return f"Vec<{base}>" if repeated else base
    
    def decode_expr(self, fname: str, ftype: str, raw_type: str, 
                    repeated: bool, is_top_level: bool = False) -> str:
        """Generate decode expression for a field"""
        reader_ref = "&mut reader" if is_top_level else "reader"
        
        if repeated:
            inner = ftype.replace("Vec<", "").replace(">", "")
            inner_decode = self.decode_expr(fname, inner, raw_type, False, is_top_level)
            return f"""{{ 
            let count = reader.read_i16_padded() as usize; 
            let mut v = Vec::with_capacity(count); 
            for _ in 0..count {{ 
                v.push({inner_decode}); 
            }} 
            v 
        }}"""
        
        # Primitive types
        primitive_reads = {
            "i8": "reader.read_i8_padded()",
            "i16": "reader.read_i16_padded()",
            "i32": "reader.read_i32_padded()",
            "i64": "reader.read_i64_padded()",
            "u16": "reader.read_u16_padded()",
            "u32": "reader.read_u32_padded()",
            "u64": "reader.read_u64_padded()",
            "bool": "reader.read_bool_padded()",
        }
        
        if ftype in primitive_reads:
            return primitive_reads[ftype]
        elif ftype == "String" and raw_type == "int64str":
            return "reader.read_i64_padded().to_string()"
        elif ftype == "String":
            return "reader.read_string_padded()"
        else:
            # Struct type
            return f"{ftype}::decode({reader_ref})"
    
    def encode_expr(self, fname: str, ftype: str, raw_type: str, repeated: bool) -> str:
        """Generate encode expression for a field"""
        indent = " " * 8
        inner_indent = " " * 12
        
        if repeated:
            inner = ftype.replace("Vec<", "").replace(">", "")
            
            # Primitive types
            if inner in {"i8", "i16", "i32", "i64", "u16", "u32", "u64", "bool"}:
                return "\n".join([
                    f"{indent}buf.write_i16(self.{fname}.len() as i16);",
                    f"{indent}for v in &self.{fname} {{",
                    f"{inner_indent}buf.write_{inner}(*v);",
                    f"{indent}}}"
                ])
            elif inner == "String":
                return "\n".join([
                    f"{indent}buf.write_i16(self.{fname}.len() as i16);",
                    f"{indent}for v in &self.{fname} {{",
                    f"{inner_indent}buf.write_string(v);",
                    f"{indent}}}"
                ])
            else:
                # Struct type
                return "\n".join([
                    f"{indent}buf.write_i16(self.{fname}.len() as i16);",
                    f"{indent}for v in &self.{fname} {{",
                    f"{inner_indent}buf.write_raw_bytes(&v.encode());",
                    f"{indent}}}"
                ])
        
        # Non-repeated field
        primitive_writes = {
            "i8": f"{indent}buf.write_i8(self.{fname});",
            "i16": f"{indent}buf.write_i16(self.{fname});",
            "i32": f"{indent}buf.write_i32(self.{fname});",
            "i64": f"{indent}buf.write_i64(self.{fname});",
            "u16": f"{indent}buf.write_u16(self.{fname});",
            "u32": f"{indent}buf.write_u32(self.{fname});",
            "u64": f"{indent}buf.write_u64(self.{fname});",
            "bool": f"{indent}buf.write_bool(self.{fname});",
        }
        
        if ftype in primitive_writes:
            return primitive_writes[ftype]
        elif ftype == "String" and raw_type == "int64str":
            return f"{indent}buf.write_i64(self.{fname}.parse::<i64>().unwrap());"
        elif ftype == "String":
            return f"{indent}buf.write_string(&self.{fname});"
        else:
            # Struct type
            return f"{indent}buf.write_raw_bytes(&self.{fname}.encode());"
    
    def generate_struct(self, name: str, msg_def: Dict) -> List[str]:
        """Generate a single struct definition with impl block"""
        out = []
        fields = msg_def.get("fields", [])
        
        # Collect unknown types
        for field in fields:
            raw_type = self.clean_string(field.get("type", ""))
            if raw_type and raw_type not in self.TYPE_MAP and raw_type not in self.known_structs:
                self.unknown_types.add(raw_type)
        
        # Struct definition
        out.append("#[allow(non_camel_case_types)]")
        out.append("#[derive(Debug, Clone, Serialize, Deserialize)]")
        out.append(f"pub struct {name} {{")
        
        if not fields:
            out.append("    // no fields")
        else:
            for field in fields:
                original_name = self.clean_string(field.get("name", ""))
                raw_type = self.clean_string(field.get("type", ""))
                repeated = field.get("repeated", False)
                
                if not original_name or not raw_type:
                    print(f"Warning: Skipping field with missing name/type in {name}")
                    continue
                
                ftype = self.rust_type(raw_type, repeated)
                comment = self.clean_comment(field.get("desc", ""))
                safe_name, serde_name = self.safe_field_name(original_name)
                
                if comment:
                    out.append(f"    /// {comment}")
                if safe_name != serde_name:
                    out.append(f'    #[serde(rename = "{serde_name}")]')
                out.append(f"    pub {safe_name}: {ftype},")
        
        out.append("}\n")
        
        # Impl block
        out.extend(self.generate_impl(name, fields))
        out.append("")
        
        return out
    
    def generate_impl(self, name: str, fields: List[Dict]) -> List[str]:
        """Generate impl block with decode and encode methods"""
        out = []
        is_top_level = not name.startswith("pt_")
        
        out.append(f"impl {name} {{")
        
        # Decode method
        if name.startswith("pt_"):
            out.append("    pub fn decode(reader: &mut ProtocolByteBuf) -> Self {")
        else:
            out.append("    pub fn decode(data: &[u8]) -> Self {")
            out.append("        let mut reader = ProtocolByteBuf::new(data);")
            out.append(f'        info!("Decoding {name}, data length: {{}}", data.len());')
        
        out.append("        Self {")
        for field in fields:
            original_name = self.clean_string(field.get("name", ""))
            raw_type = self.clean_string(field.get("type", ""))
            if not original_name or not raw_type:
                continue
            
            fname, _ = self.safe_field_name(original_name)
            repeated = field.get("repeated", False)
            ftype = self.rust_type(raw_type, repeated)
            decode = self.decode_expr(fname, ftype, raw_type, repeated, is_top_level)
            out.append(f"            {fname}: {decode},")
        
        out.append("        }")
        out.append("    }")
        
        # Encode method
        out.append("    pub fn encode(&self) -> Vec<u8> {")
        out.append("        let mut buf = ProtocolByteBuf::new_write();")
        for field in fields:
            original_name = self.clean_string(field.get("name", ""))
            raw_type = self.clean_string(field.get("type", ""))
            if not original_name or not raw_type:
                continue
            
            fname, _ = self.safe_field_name(original_name)
            repeated = field.get("repeated", False)
            ftype = self.rust_type(raw_type, repeated)
            out.append(self.encode_expr(fname, ftype, raw_type, repeated))
        
        out.append("        buf.into_bytes()")
        out.append("    }")
        out.append("}")
        
        return out
    
    def generate_placeholder_structs(self) -> List[str]:
        """Generate placeholder structs for unknown types"""
        out = []
        
        if self.unknown_types:
            out.append("// Placeholder structs for unknown types")
            for unknown_type in sorted(self.unknown_types):
                if self.is_valid_rust_identifier(unknown_type):
                    out.append("#[allow(non_camel_case_types)]")
                    out.append("#[derive(Debug, Clone, Serialize, Deserialize)]")
                    out.append(f"pub struct {unknown_type} {{")
                    out.append("    // TODO: Define proper fields for this struct")
                    out.append("}\n")
                    
                    # Add decode + encode impl for placeholder
                    out.append(f"impl {unknown_type} {{")
                    out.append("    pub fn decode(_reader: &mut ProtocolByteBuf) -> Self {")
                    out.append("        // TODO: Implement proper decoding")
                    out.append("        Self {}")
                    out.append("    }")
                    out.append("")
                    out.append("    pub fn encode(&self) -> Vec<u8> {")
                    out.append("        // TODO: Implement proper encoding")
                    out.append("        Vec::new()")
                    out.append("    }")
                    out.append("}")
                    out.append("")
        
        return out
    
    def generate_messages(self) -> str:
        """Generate messages.rs file"""
        out = []
        
        # Header
        out.append("// Auto-generated from messages.json")
        out.append("")
        out.append("#![allow(non_local_definitions)]")
        out.append("use serde::{Serialize, Deserialize};")
        out.append("use crate::packet::ProtocolByteBuf;")
        out.append("use tracing::info;")
        out.append("")
        
        # Generate all structs
        for key, msg_def in self.messages.items():
            name = self.clean_string(msg_def.get("msg_name", ""))
            if not name or not self.is_valid_rust_identifier(name):
                continue
            out.extend(self.generate_struct(name, msg_def))
        
        # Generate placeholders
        out.extend(self.generate_placeholder_structs())
        
        return "\n".join(out)
    
    def generate_dispatch(self) -> str:
        """Generate dispatch.rs file"""
        out = []
        
        out.append("// Auto-generated dispatcher")
        out.append("use serde_json::Value;")
        out.append("use crate::messages::*;")
        out.append("")
        out.append("pub fn dispatch_cmd(cmd: u32, data: &[u8]) -> Option<Value> {")
        out.append("    match cmd {")
        
        for msg_id, msg_def in self.messages.items():
            name = self.clean_string(msg_def.get("msg_name", ""))
            if not name or not self.is_valid_rust_identifier(name):
                continue
            if not msg_id.isnumeric():
                print(f"Skipped Msg_id {msg_id}")
            else:
                out.append(f"        {msg_id} => Some(serde_json::to_value(&{name}::decode(data)).unwrap()),")
        
        out.append("        _ => None,")
        out.append("    }")
        out.append("}")
        
        return "\n".join(out)
    
    def generate(self, output_dir: str = ".") -> None:
        """Generate all output files"""
        output_path = Path(output_dir)
        
        # Load messages
        self.load_messages()
        
        # Generate messages.rs
        messages_code = self.generate_messages()
        (output_path / "messages.rs").write_text(messages_code, encoding="utf8")
        
        # Generate dispatch.rs
        dispatch_code = self.generate_dispatch()
        (output_path / "dispatch.rs").write_text(dispatch_code, encoding="utf8")
        
        print(f"[*] Generated messages.rs and dispatch.rs in {output_dir}")


def main():
    codegen = ProtocolCodegen("mapping.json")
    codegen.generate()


if __name__ == "__main__":
    main()