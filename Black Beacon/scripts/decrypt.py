import os
import sys
import lzma
import struct
import json
import re

def custom_rc4(key: bytes, data: bytes) -> bytes:
    """Modified RC4 implementation"""
    K = [0] * 256
    S = [0] * 256
    
    for i in range(256):
        K[i] = key[i % len(key)]
    
    for i in range(256):
        S[i] = i
    
    j = 0
    for i in range(256):
        j = (j + S[i] + K[i]) % 256
        S[i], S[j] = S[j], S[i]
    
    result = bytearray()
    i = 0
    j = 0
    
    for byte_idx in range(len(data)):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        k_idx = (S[i] + S[j]) % 256
        keystream_byte = S[k_idx] & 0xFF
        result.append(data[byte_idx] ^ keystream_byte)
    
    return bytes(result)

KEY2_DECODESCRIPT = bytes.fromhex(
    "8974ea6638cfdbe0f3ed0b283621d6bc31296082d9ccf432b107a03450171e7a"
    "0338c54d7354a3abba68632fc9f2290a89241c2aa427a7f65f4739c65c309285"
    "c11e5b9da9411da6321750dd2a0d9ffebb240c6df4ef1d55a3aab9a85eb1e4a4"
    "3324efc4d0f95dcba5520bcecc4ce1de371b9a4e02bbcf1b4dfdfd87912fa371"
    "c732145a644943bf6d5a12c0b0f4619974e179f78d8b02bf38f32a38b69e222e"
    "fc149b1c696275cde3562e9d5bb456c2f23da1bbddc5c063442aa9b51a637dc3"
    "5581a5f06ae064e870576e75db9fc19938d35515c539dccd5c2431268d459ac4"
    "5c1796e67dc745ae7e552b81c7346c02d53a1fa69b1df16e6f4ebbd46a752769"
)

def decode_custom_lzma(data):
    """Decode custom LZMA format with reordered size bytes"""
    b0, b1, b2, b3 = data[0], data[1], data[2], data[3]
    uncompressed_size = (b0 << 24) | (b2 << 16) | (b1 << 8) | b3
    
    print(f"[*] Uncompressed size: {uncompressed_size:,} bytes")
    
    lzma_props = data[4:9]
    uncompressed_size_8bytes = struct.pack('<Q', uncompressed_size)
    standard_lzma = lzma_props + uncompressed_size_8bytes + data[9:]
    
    try:
        decompressed = lzma.decompress(standard_lzma, format=lzma.FORMAT_ALONE)
    except:  # noqa: E722
        unknown_size = struct.pack('<Q', 0xFFFFFFFFFFFFFFFF)
        standard_lzma = lzma_props + unknown_size + data[9:]
        decompressed = lzma.decompress(standard_lzma, format=lzma.FORMAT_ALONE)
    
    print(f"[+] Decompressed: {len(decompressed):,} bytes")
    return decompressed

def extract_lua_filepath(lua_data):
    """Extract filepath from Lua 5.4 bytecode"""
    try:
        offset = 0x20
        str_len = lua_data[offset]
        offset += 1
        
        if str_len == 0xFF:
            str_len = struct.unpack('<Q', lua_data[offset:offset+8])[0]
            offset += 8
        
        if str_len > 0 and str_len < 5000:
            raw_string = lua_data[offset:offset+str_len-1].decode('utf-8', errors='ignore')
            
            if raw_string.startswith('@'):
                raw_string = raw_string[1:]
            
            match = re.match(r'^([a-zA-Z0-9_/.-]+\.lua)', raw_string)
            if match:
                return match.group(1)
            
            if '.lua' in raw_string:
                lua_pos = raw_string.find('.lua')
                filepath = raw_string[:lua_pos + 4]
                filepath = ''.join(c for c in filepath if c.isprintable() or c == '/')
                return filepath
    except:  # noqa: E722
        pass
    
    return None

def sanitize_filepath(filepath):
    """Sanitize filepath"""
    if not filepath:
        return None
    
    filepath = filepath.replace('\\', '/')
    filepath = filepath.replace('..', '_')
    filepath = re.sub(r'/+', '/', filepath)
    filepath = filepath.lstrip('/')
    
    return filepath if filepath else None

def extract_lua_files(data, output_dir):
    """Extract Lua bytecode files"""
    print("\n[*] Extracting Lua files...\n")
    
    offset = 0
    file_num = 0
    success_count = 0
    
    while offset < len(data):
        pos = data.find(b'\x1bLua', offset)
        if pos == -1:
            break
        
        next_pos = data.find(b'\x1bLua', pos + 4)
        size = (len(data) - pos) if next_pos == -1 else (next_pos - pos)
        
        lua_data = data[pos:pos+size]
        file_num += 1
        
        filepath = extract_lua_filepath(lua_data)
        filepath = sanitize_filepath(filepath) if filepath else None
        
        if filepath:
            if not filepath.endswith('.luac'):
                filepath = filepath.rsplit('.', 1)[0] + '.luac' if '.' in filepath else filepath + '.luac'
            output_path = os.path.join(output_dir, filepath)
            status = "✓"
            success_count += 1
        else:
            output_path = os.path.join(output_dir, f"unknown/script_{file_num:04d}.luac")
            filepath = f"unknown/script_{file_num:04d}.luac"
            status = "?"
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(lua_data)
            print(f"[{status}] [{file_num:4d}] {filepath:<65s} ({size:7,d} bytes)")
        except Exception as e:
            print(f"[-] Failed {filepath}: {e}")
        
        offset = pos + size
    
    print(f"\n[+] Extracted {success_count}/{file_num} files with original paths")
    return file_num


def extract_json_files(data: bytes, output_dir: str):

    print("\n[*] Extracting JSON files (fast)...\n")
    os.makedirs(output_dir, exist_ok=True)

    matches = [m.start() for m in re.finditer(rb'\.json\x00', data)]
    if not matches:
        print("[!] No .json filenames found")
        return 0

    file_count = 0
    for idx, endpos in enumerate(matches):
        # find filename start
        start = endpos
        while start > 0 and 32 <= data[start - 1] < 127:
            start -= 1
        filename = data[start:endpos + 5].decode("ascii", "ignore")
        filename = re.sub(r"[^A-Za-z0-9._/\-]", "", filename)
        offset = endpos + 6

        next_start = matches[idx + 1] - 4 if idx + 1 < len(matches) else len(data)
        blob = data[offset:next_start]

        out_path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

    
        try:
            text = blob.decode("utf-8", errors="ignore")

            # trim anything after the last closing brace
            last_brace = text.rfind("}")
            if last_brace != -1:
                text = text[: last_brace + 1]

            # attempt to parse cleaned JSON
            parsed = json.loads(text)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            print(f"[✓] {filename}")

        except (UnicodeDecodeError, json.JSONDecodeError):

            try:
                text = blob.decode("utf-8", errors="ignore")
                last_brace = text.rfind("}")
                if last_brace != -1:
                    text = text[: last_brace + 1]
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"[!] {filename} (raw cleaned)")
            except Exception as e:
                with open(out_path, "wb") as f:
                    f.write(blob)
                print(f"[!] {filename} (binary fallback: {e})")

        file_count += 1

    print(f"\n[+] Extracted {file_count} JSON file(s)")
    return file_count



def detect_and_extract(data, output_dir):
    """Auto-detect content type and extract"""
    
    # Check for Lua bytecode
    if b'\x1bLua' in data[:1000]:
        print("[*] Detected: Lua bytecode container")
        return extract_lua_files(data, output_dir)
    
    # Check for JSON container
    elif b'.json\x00' in data[:100] or (data[4:50].count(b'.') > 0 and data[4:50].count(b'\x00') > 0):
        print("[*] Detected: JSON container")
        return extract_json_files(data, output_dir)
    
    else:
        print("[!] Unknown format")
        print(f"[*] First 100 bytes: {data[:100]}")
        
        output_path = os.path.join(output_dir, "unknown_data.bin")
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(data)
        print(f"[*] Saved to: {output_path}")
        return 0

def decrypt_and_extract(input_path, output_dir):
    """Main extraction function"""
    print(f"[*] Reading: {input_path}\n")
    
    with open(input_path, 'rb') as f:
        encrypted = f.read()
    
    print("="*80)
    print("STEP 1: RC4 Decryption")
    print("="*80)
    decrypted = custom_rc4(KEY2_DECODESCRIPT, encrypted)
    print(f"[+] Decrypted: {len(decrypted):,} bytes\n")
    
    print("="*80)
    print("STEP 2: LZMA Decompression")
    print("="*80)
    decompressed = decode_custom_lzma(decrypted)
    
    print("\n" + "="*80)
    print("STEP 3: Auto-Detect and Extract")
    print("="*80)
    
    file_count = detect_and_extract(decompressed, output_dir)
    
    print(f"\n{'='*80}")
    if file_count > 0:
        print(f"SUCCESS! Extracted {file_count} file(s)")
        print(f"Output: {os.path.abspath(output_dir)}")
    else:
        print("No files extracted")
    print(f"{'='*80}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage: python decrypt.py <input_file> [output_dir]")
        print("\nSupports:")
        print("  - Lua bytecode containers (multiple .luac files)")
        print("  - JSON configuration files (multiple .json files)")
        print("\nExamples:")
        print("  python decrypt.py luagame.txt extracted_lua")
        print("  python decrypt.py jsonconfig.txt extracted_json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    elif 'lua' in input_file.lower():
        output_dir = "extracted_lua"
    elif 'json' in input_file.lower():
        output_dir = "extracted_json"
    else:
        output_dir = "extracted"
    
    try:
        decrypt_and_extract(input_file, output_dir)
    except Exception as e:
        print(f"\n[-] Error: {e}")
        import traceback
        traceback.print_exc()