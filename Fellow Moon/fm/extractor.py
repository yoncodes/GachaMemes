import os
import io
import struct
import json
import zipfile
from pathlib import Path
from fm.decryptor import CustomDecryptor
import logging
import time
from fm.asset import Asset
from fm.proto_builder import ProtoBuilder
import UnityPy

log = logging.getLogger(__name__)

class PakExtractor:

    def __init__(self, xapk_path: str | None = None):
        self.decryptor = CustomDecryptor()
        self.asset_path = r"gameres\assets"
        self.xapk_path = xapk_path
        self.layer_zips: list[zipfile.ZipFile] = []

        if xapk_path and os.path.exists(xapk_path):
            self._open_nested_archives(xapk_path)

    # ------------------------------------------------------------------ #
    def _open_nested_archives(self, xapk_path: str):
        """Open XAPK → gameres.apk → assets/*.zip automatically."""
        log.info(f"[+] Opening {xapk_path}")
        outer = zipfile.ZipFile(xapk_path, "r")

        gameres_name = next((n for n in outer.namelist() if n.endswith("gameres.apk")), None)
        if not gameres_name:
            log.info("✗ gameres.apk not found in XAPK")
            return
        log.info(f"  ↳ Found gameres.apk: {gameres_name}")
        gameres_bytes = outer.read(gameres_name)
        inner_apk = zipfile.ZipFile(io.BytesIO(gameres_bytes), "r")

        asset_zips = [n for n in inner_apk.namelist() if n.startswith("assets/") and n.endswith(".zip")]
        if not asset_zips:
            log.info("✗ No asset zips found under assets/")
            return
        log.info(f"  ↳ Found {len(asset_zips)} asset zip(s): {', '.join(asset_zips)}")

        for name in asset_zips:
            bytes_data = inner_apk.read(name)
            self.layer_zips.append(zipfile.ZipFile(io.BytesIO(bytes_data), "r"))

        log.info(f"[✓] Loaded {len(self.layer_zips)} nested asset zip(s).")

    # ------------------------------------------------------------------ #
    def _read_file_bytes(self, path: str) -> bytes:
        """Read bytes from nested zips first, then local disk."""
        norm = path.replace("\\", "/")
        for z in self.layer_zips:
            try:
                with z.open(norm, "r") as f:
                    return f.read()
            except KeyError:
                continue
        with open(path, "rb") as f:
            return f.read()

    # ------------------------------------------------------------------ #
    @staticmethod
    def get_string_hash(content):
        if not content:
            return 0
        hash_val = 0
        for char in content:
            hash_val = (31 * hash_val + ord(char)) & 0xFFFFFFFF
        return hash_val
    
    def read_string(self, data, offset):
        length = 0
        shift = 0
        while True:
            byte = data[offset]
            offset += 1
            length |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        
        string = data[offset:offset + length].decode('utf-8')
        offset += length
        return string, offset
    
    def load_pak(self, pak_path):
        data = self._read_file_bytes(pak_path)
        
        offset = 0
        version = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        md5 = data[offset:offset+16]
        offset += 16
        file_count = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        
        entries = {}
        for i in range(file_count):
            filename, offset = self.read_string(data, offset)
            file_offset = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            file_size = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            entries[filename] = {
                'offset': file_offset,
                'size': file_size,
                'hash': self.get_string_hash(filename)
            }
        
        return data, entries, {'version': version, 'md5': md5.hex(), 'count': file_count}
    
    def get_resource_name(self, filepath):
        filename = os.path.basename(filepath)
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]
        return filename
    
    def detect_file_type(self, data):
        if len(data) < 7:
            return 'bin'
        if data[0] == 0x1B and data[1] == 0x4C:
            if data[2] in (0x75, 0x4A):
                return 'luac'
        if len(data) >= 8 and data[4] == 0x1B and data[5] == 0x4C:
            if data[6] in (0x75, 0x4A):
                return 'luac'
        if data.startswith(b'--') or data.startswith(b'return') or data.startswith(b'local'):
            return 'lua'
        elif data.startswith(b'<?xml'):
            return 'xml'
        elif data.startswith(b'{') or data.startswith(b'['):
            return 'json'
        else:
            try:
                decoded = data[:100].decode('utf-8')
                if any(kw in decoded for kw in ['function', 'end', 'if', 'then']):
                    return 'lua'
            except:  # noqa: E722
                pass
        return 'bin'
    
    def parse_index_json(self, index_path='LuaScript_index.json'):
        if self.layer_zips:
            # try to read index.json from zip layers first
            for z in self.layer_zips:
                for candidate in [index_path, "assets/Lua/LuaScript_index.json"]:
                    try:
                        with z.open(candidate, "r") as f:
                            log.info(f"[✓] Loaded index from {candidate} in zip")
                            return list(json.load(f).keys())
                    except KeyError:
                        continue
        if not os.path.exists(index_path):
            log.info(f"✗ LuaScript_index.json not found at {index_path}")
            return []
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        return list(index.keys())
    
    def find_pak_files(self, search_dir='.', index_path='Lua'):
        log.info(f"\n{'='*70}")
        log.info("SCANNING FOR PAK FILES")
        log.info(f"{'='*70}")
        
        expected_files = self.parse_index_json(index_path)
        log.info(f"\nFound {len(expected_files)} PAK files in LuaScript_index.json")

        found_files = []
        if self.layer_zips:
            # search in zip layers
            zip_names = set()
            for z in self.layer_zips:
                zip_names |= set(z.namelist())
            for expected in expected_files:
                for prefix in ["Lua/", "data/", "cache/"]:
                    if prefix + expected in zip_names or expected in zip_names:
                        log.info(f"  ✓ Found in zip: {expected}")
                        found_files.append(expected if expected in zip_names else prefix + expected)
                        break
                else:
                    log.info(f"  ✗ Missing: {expected}")
        else:
            search_path = Path(search_dir)
            for expected in expected_files:
                possible_paths = [
                    search_path / expected,
                    search_path / 'cache' / expected,
                    search_path / 'data' / expected,
                    search_path / 'lua' / expected,
                ]
                for path in possible_paths:
                    if path.exists():
                        log.info(f"  ✓ Found: {expected}")
                        found_files.append(str(path))
                        break
                else:
                    log.info(f"  ✗ Missing: {expected}")
        
        log.info(f"\nFound {len(found_files)}/{len(expected_files)} PAK files")
        return found_files
    
    def find_encrypted_files_recursive(self, search_dir='.'):
        """Recursively find all files with encryption marker 22 4A 67."""
        log.info(f"\n{'='*70}")
        log.info("SCANNING FOR ENCRYPTED FILES (RECURSIVE)")
        log.info(f"{'='*70}")
        
        encrypted_marker = bytes([0x22, 0x4A, 0x67])
        found_files = []
        
        if self.layer_zips:
            # Search in zip layers
            all_names = set()
            for z in self.layer_zips:
                all_names |= set(z.namelist())
            
            for name in sorted(all_names):
                if name.endswith('/'):  # Skip directories
                    continue
                
                try:
                    data = self._read_file_bytes(name)
                    # Check for encryption marker at start
                    if len(data) >= 3 and data[:3] == encrypted_marker:
                        found_files.append(name)
                        log.info(f"  ✓ Encrypted: {name}")
                except Exception:
                    pass  # Skip files we can't read
        else:
            # Search local filesystem
            search_path = Path(search_dir)
            for file_path in search_path.rglob('*'):
                if file_path.is_file():
                    try:
                        with open(file_path, 'rb') as f:
                            header = f.read(3)
                            if header == encrypted_marker:
                                found_files.append(str(file_path))
                                log.info(f"  ✓ Encrypted: {file_path}")
                    except Exception:
                        pass  # Skip files we can't read
        
        log.info(f"\nFound {len(found_files)} encrypted files")
        return found_files

    def extract_all_from_index(
        self,
        search_dir='.',
        index_path='Lua',
        base_output_dir='extracted',
        save_encrypted=False,
        include_recursive=True,
        stop_event=None
    ):
        """Extract all PAKs + recursively search for encrypted files."""

        # --- Early abort ---
        if stop_event and stop_event.is_set():
            log.warning("Extraction aborted before start.")
            return {}, {}

        pak_files = self.find_pak_files(search_dir, index_path)

        log.info(f"\n{'#'*70}")
        log.info(f"# EXTRACTING {len(pak_files)} PAK FILE(S)")
        log.info(f"{'#'*70}")

        total_stats = {'total': 0, 'success': 0, 'failed': 0}
        combined_mapping = {}
        file_types = {}

        # --- Process each PAK ---
        for pak_idx, pak_path in enumerate(pak_files, 1):
            if stop_event and stop_event.is_set():
                log.warning("Extraction aborted by user.")
                log.info(f"Processed {pak_idx-1} of {len(pak_files)} PAK files.")
                return total_stats, combined_mapping

            pak_name = os.path.basename(pak_path)
            log.info(f"\n{'='*70}")
            log.info(f"[{pak_idx}/{len(pak_files)}] EXTRACTING PAK: {pak_name[:60]}")
            log.info(f"{'='*70}")

            try:
                pak_data, entries, info = self.load_pak(pak_path)
            except Exception as e:
                log.error(f"Failed to load {pak_name}: {e}")
                continue

            log.info(f"  Version: {info['version']}")
            log.info(f"  MD5: {info['md5']}")
            log.info(f"  Files: {info['count']}")

            total_stats['total'] += len(entries)

            for i, (filepath, entry) in enumerate(entries.items(), 1):
                if stop_event and stop_event.is_set():
                    log.warning("Extraction aborted inside PAK loop.")
                    log.info(f"Processed {i-1}/{len(entries)} entries in {pak_name}")
                    return total_stats, combined_mapping

                # yield every few iterations for UI responsiveness
                if i % 5 == 0:
                    time.sleep(0.01)

                file_hash = entry['hash']
                combined_mapping[str(file_hash)] = filepath
                if i % 20 == 1 or i == len(entries):
                    log.info(f"  Progress: [{i}/{len(entries)}]")

                try:
                    start = entry['offset']
                    end = start + entry['size']
                    encrypted_data = pak_data[start:end]

                    if stop_event and stop_event.is_set():
                        log.warning("Extraction interrupted before decrypting next file.")
                        return total_stats, combined_mapping

                    resource_name = self.get_resource_name(filepath)
                    decrypted = self.decryptor.decrypt_custom_format(encrypted_data, resource_name)

                    if stop_event and stop_event.is_set():
                        log.warning("Extraction interrupted during decryption.")
                        return total_stats, combined_mapping

                    if decrypted:
                        file_type = self.detect_file_type(decrypted)
                        file_types[file_type] = file_types.get(file_type, 0) + 1
                        ext = {'luac': '.luac', 'lua': '.lua', 'json': '.json', 'xml': '.xml'}.get(file_type, '.bin')

                        output_path = os.path.join(base_output_dir, 'by_path', filepath + ext)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(decrypted)

                        if stop_event and stop_event.is_set():
                            log.warning("Extraction interrupted during write.")
                            return total_stats, combined_mapping

                        hash_path = os.path.join(base_output_dir, 'by_hash', f"{file_hash}{ext}")
                        os.makedirs(os.path.dirname(hash_path), exist_ok=True)
                        with open(hash_path, 'wb') as f:
                            f.write(decrypted)

                        total_stats['success'] += 1
                    else:
                        total_stats['failed'] += 1

                except Exception as e:
                    total_stats['failed'] += 1
                    log.error(f"[!] Failed to extract {filepath}: {e}")

            time.sleep(0.01)  # small yield after each PAK

        # --- Optional recursive pass ---
        if include_recursive and not (stop_event and stop_event.is_set()):
            log.info(f"\n{'#'*70}")
            log.info("# SEARCHING FOR ADDITIONAL ENCRYPTED FILES")
            log.info(f"{'#'*70}")

            encrypted_files = self.find_encrypted_files_recursive(search_dir)
            pak_processed = set(combined_mapping.values())
            new_files = [f for f in encrypted_files if f not in pak_processed]

            if new_files:
                log.info(f"\n{'='*70}")
                log.info(f"EXTRACTING {len(new_files)} ADDITIONAL ENCRYPTED FILES")
                log.info(f"{'='*70}")

                for file_idx, file_path in enumerate(new_files, 1):
                    if stop_event and stop_event.is_set():
                        log.warning("Extraction aborted during additional file search.")
                        log.info(f"Processed {file_idx-1}/{len(new_files)} extra files.")
                        return total_stats, combined_mapping

                    if file_idx % 3 == 0:
                        time.sleep(0.01)

                    try:
                        file_data = self._read_file_bytes(file_path)
                        resource_name = self.get_resource_name(file_path)
                        decrypted = self.decryptor.decrypt_custom_format(file_data, resource_name)

                        if stop_event and stop_event.is_set():
                            log.warning("Extraction interrupted during extra file decryption.")
                            return total_stats, combined_mapping

                        if decrypted:
                            file_hash = self.get_string_hash(file_path)
                            combined_mapping[str(file_hash)] = file_path
                            file_type = self.detect_file_type(decrypted)
                            file_types[file_type] = file_types.get(file_type, 0) + 1
                            ext = {'luac': '.luac', 'lua': '.lua', 'json': '.json', 'xml': '.xml'}.get(file_type, '.bin')

                            output_file_path = file_path
                            if file_type == 'luac' and file_path.endswith('.lua'):
                                output_file_path = file_path[:-4] + '.luac'

                            output_path = os.path.join(base_output_dir, 'by_path', output_file_path)
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            with open(output_path, 'wb') as f:
                                f.write(decrypted)

                            hash_path = os.path.join(base_output_dir, 'by_hash', f"{file_hash}{ext}")
                            os.makedirs(os.path.dirname(hash_path), exist_ok=True)
                            with open(hash_path, 'wb') as f:
                                f.write(decrypted)

                            log.info(f"  ✓ Decrypted as {file_type} → {os.path.basename(output_file_path)}")
                            total_stats['total'] += 1
                            total_stats['success'] += 1
                        else:
                            log.info("  ✗ Decryption failed")
                            total_stats['total'] += 1
                            total_stats['failed'] += 1

                    except Exception as e:
                        log.info(f"  ✗ Error: {e}")
                        total_stats['total'] += 1
                        total_stats['failed'] += 1
            else:
                log.warning("\n✓ No additional encrypted files found")

        # --- Stop before summary if cancelled ---
        if stop_event and stop_event.is_set():
            log.warning("Extraction stopped before writing summary files.")
            return total_stats, combined_mapping

        # --- Save metadata ---
        combined_path = os.path.join(base_output_dir, 'all_hashes.json')
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(combined_mapping, f, indent=2, ensure_ascii=False)

        info_path = os.path.join(base_output_dir, 'extraction_info.json')
        with open(info_path, 'w') as f:
            json.dump({
                'total_paks': len(pak_files),
                'total_files': total_stats['total'],
                'stats': total_stats,
                'file_types': file_types
            }, f, indent=2)

        log.info(f"\n{'#'*70}")
        log.info("# OVERALL SUMMARY")
        log.info(f"{'#'*70}")
        log.info(f"\nTotal PAK files:  {len(pak_files)}")
        log.info(f"Total files:      {total_stats['total']}")
        log.info(f"Decrypted:        {total_stats['success']}")
        log.info(f"Failed:           {total_stats['failed']}")
        if total_stats['total'] > 0:
            log.info(f"Success rate:     {total_stats['success']/total_stats['total']*100:.1f}%")

        if file_types:
            log.info("\nFile types:")
            for ftype, count in sorted(file_types.items(), key=lambda x: -x[1]):
                log.info(f"  {ftype}: {count}")

        log.info(f"\n✓ Complete hash mapping: {combined_path}")
        log.info(f"✓ Extraction info: {info_path}")
        log.info(f"✓ Output directory: {base_output_dir}/")

        return total_stats, combined_mapping


class ProtoExtractor:
    """
    Decodes a single downloaded proto AssetBundle file using the Asset class.
    Looks inside downloads/proto/ and outputs to the configured folder (default: proto/).
    """

    def __init__(self, proto_dir="downloads/proto", output_dir="proto"):
        self.proto_dir = Path(proto_dir)
        self.output_dir = Path(output_dir)
        self.asset = Asset()

    # ------------------------------------------------------------------ #
    def extract_and_decode(self, stop_event=None):
        if stop_event and stop_event.is_set():
            log.warning("ProtoExtractor aborted before start.")
            return

        if not self.proto_dir.exists():
            log.warning(f"Proto directory not found: {self.proto_dir}")
            return

        ab_files = list(self.proto_dir.glob("*.ab*"))
        if not ab_files:
            log.warning(f"No .ab files found in {self.proto_dir}")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        log.info(f"Found {len(ab_files)} proto file(s) in {self.proto_dir}")

        try:
            # Decode the entire proto_dir once
            if hasattr(self.asset, "batch_decode"):
                self.asset.batch_decode(str(self.proto_dir), str(self.output_dir), stop_event=stop_event)
                log.info(f"  ✓ Decoded all .ab files from {self.proto_dir} → {self.output_dir}")
            else:
                log.warning("  ⚠ Asset has no batch_decode() method — skipping decode phase.")
        except Exception as e:
            log.error(f"  ✗ batch_decode failed: {e}")


        decoded_files = list(self.output_dir.glob("*.ab")) or ab_files
        log.info(f"Scanning {len(decoded_files)} decoded .ab file(s) for TextAssets...")

        for idx, decoded_path in enumerate(decoded_files, 1):
            if stop_event and stop_event.is_set():
                log.warning("Proto extraction aborted by user.")
                break

            try:
                log.info(f"[{idx}/{len(decoded_files)}] Reading {decoded_path.name}")
                env = UnityPy.load(str(decoded_path))
                extracted = 0

                for obj in env.objects:
                    if stop_event and stop_event.is_set():
                        log.warning("Proto extraction stopped mid-process.")
                        return
                    if obj.type.name == "TextAsset":
                        data = obj.read()
                        out_name = "moon.pb"
                        out_path = os.path.join(self.output_dir, out_name)
                        with open(out_path, "wb") as f:
                            f.write(data.m_Script.encode("utf-8", "surrogateescape"))
                        log.info(f"  ✓ Extracted TextAsset → {out_path}")
                        extracted += 1
                        break

                if extracted == 0:
                    log.warning(f"  ✗ No TextAsset found in {decoded_path.name}")

            except Exception as e:
                log.error(f"[!] Failed to process {decoded_path}: {e}")

        builder = ProtoBuilder()
        builder.build_from_file(os.path.join(self.output_dir, "moon.pb"), self.output_dir / "generated")

        log.info(f"Proto extraction complete → {self.output_dir.resolve()}\n")