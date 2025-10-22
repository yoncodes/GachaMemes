import zipfile
import os
import struct
import logging

log = logging.getLogger(__name__)

class Metadata:

    def __init__(self):
        self.metadata_path = "assets/bin/Data/Managed/Metadata/global-metadata.dat"


    def extract_and_decrypt(self, xapk_path, output_dir="extracted"):
        """Extract and decrypt global-metadata.dat from XAPK"""
        
        if not os.path.exists(xapk_path):
            log.info(f"Error: {xapk_path} not found")
            return
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Open XAPK and find APK
        with zipfile.ZipFile(xapk_path, 'r') as xapk:
            apk_files = [f for f in xapk.namelist() if f.endswith('.apk')]
            if not apk_files:
                log.info("No APK found in XAPK")
                return
            
            target_apk = next((f for f in apk_files if 'p42' in f), apk_files[0])
            log.info(f"Extracting: {target_apk}")
            
            temp_apk = os.path.join(output_dir, "temp.apk")
            with open(temp_apk, 'wb') as f:
                f.write(xapk.read(target_apk))
        
        # Extract metadata from APK
        metadata_path = self.metadata_path
        
        with zipfile.ZipFile(temp_apk, 'r') as apk:
            if metadata_path not in apk.namelist():
                # Fallback search
                metadata_path = next((f for f in apk.namelist() if 'global-metadata.dat' in f.lower()), None)
                if not metadata_path:
                    log.info("Metadata not found")
                    os.remove(temp_apk)
                    return
            
            log.info(f"Found: {metadata_path}")
            encrypted_file = os.path.join(output_dir, "global-metadata.dat")
            
            with open(encrypted_file, 'wb') as f:
                f.write(apk.read(metadata_path))
        
        os.remove(temp_apk)
        
        # Decrypt
        with open(encrypted_file, 'rb') as f:
            data = f.read()
        
        log.info(f"Size: {len(data)} bytes")
        log.info(f"First bytes: {' '.join(f'{b:02X}' for b in data[:16])}")
        
        # Detect or use key
        expected = bytes([0xAF, 0x1B, 0xB1, 0xFA])
        if data[:4] == expected:
            log.info("Already decrypted")
            return encrypted_file
        
        key = data[0] ^ expected[0]
        log.info(f"XOR key: 0x{key:02X}")
        
        decrypted = bytes([b ^ key for b in data])
        
        if decrypted[:4] == expected:
            version = struct.unpack('<I', decrypted[4:8])[0]
            log.info(f"✓ Valid IL2CPP header (version {version})")
        else:
            log.info("Warning: Invalid header after decryption")
        
        decrypted_file = os.path.join(output_dir, "global-metadata-decrypted.dat")
        with open(decrypted_file, 'wb') as f:
            f.write(decrypted)
        
        log.info(f"✓ Encrypted: {encrypted_file}")
        log.info(f"✓ Decrypted: {decrypted_file}")
        
        return decrypted_file