from hashlib import sha256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import os
from pathlib import Path


def decrypt_flatbuffer(data: bytes, password: bytes, verbose: bool = False) -> bytes:
    hash_password = sha256(password).digest()
    
    # Extract components
    data_part = data[:0x10] + data[0x20:]
    salt = data[0x10:0x20]
    
    # Derive keys with PBKDF2
    keys = PBKDF2(hash_password, salt, 0x30, count=10)

    if verbose:
        print(f"  Salt = {salt.hex()}")
        print(f"  Key  = {keys[:0x20].hex()}")
        print(f"  IV   = {keys[0x20:0x30].hex()}")
    
    # Decrypt with AES-CBC
    cipher = AES.new(key=keys[:0x20], iv=keys[0x20:0x30], mode=AES.MODE_CBC)
    decrypted = unpad(cipher.decrypt(data_part), block_size=0x10, style="pkcs7")
    
    return decrypted[0x10:]  # Strip data_salt


# Keys you captured
KEYS = [
    bytes.fromhex('3263623863623064666338386532333135323639336430363034356664313432'),
    bytes.fromhex('2e272c272b201e202a25211f222b2c29232926202d2a1f2a1f1e252c241f292e202d2e24211e1f1f1e2c2520212c29242c22201e1e1e212b262a2b2b2c222d2b'),
]


def decrypt_master_file(encrypted_path: str, output_path: str, verbose: bool = False) -> bool:
    """
    Decrypt a single master file trying all available keys.
    
    Args:
        encrypted_path: Path to encrypted .bytes file
        output_path: Path for decrypted output file
        verbose: Print detailed decryption info
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(encrypted_path, 'rb') as f:
            encrypted = f.read()
        
        # Try each key
        for i, key in enumerate(KEYS):
            try:
                if verbose:
                    print(f"  Trying key {i+1}/{len(KEYS)}...")
                
                decrypted = decrypt_flatbuffer(encrypted, key, verbose=verbose)
                
                # Create parent directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    f.write(decrypted)
                
                return True
                
            except Exception as e:
                if verbose:
                    print(f"    Key {i+1} failed: {e}")
                continue
        
        return False
        
    except Exception as e:
        print(f"  Error reading file: {e}")
        return False


def decrypt_directory_with_structure(input_dir: str, output_dir: str,
                                    input_extension: str = '.bytes',
                                    output_extension: str = '.fb',
                                    verbose: bool = True):
    """
    Recursively decrypt files and recreate directory structure in output folder.
    
    Args:
        input_dir: Source directory (e.g., "Assets/AssetBundles/Master")
        output_dir: Output directory (e.g., "DecryptedMaster")
        input_extension: Extension of files to decrypt (default: .bytes)
        output_extension: Extension for decrypted files (default: .fb)
        verbose: Print progress messages
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Statistics
    stats = {
        'processed': 0,
        'succeeded': 0,
        'failed': 0,
        'skipped': 0
    }
    
    if not input_path.exists():
        print(f"❌ Error: Input directory '{input_dir}' does not exist!")
        return stats
    
    print(f"Input:  {input_path.absolute()}")
    print(f"Output: {output_path.absolute()}")
    print(f"Keys available: {len(KEYS)}")
    print("="*60)
    
    # Walk through all directories and files
    for root, dirs, files in os.walk(input_path):
        # Calculate relative path from input_dir
        rel_path = Path(root).relative_to(input_path)
        
        # Create corresponding output directory
        current_output_dir = output_path / rel_path
        
        # Filter files
        target_files = [f for f in files if f.endswith(input_extension)]
        
        if target_files:
            # Create output directory only if there are files to process
            current_output_dir.mkdir(parents=True, exist_ok=True)
            
            if verbose:
                print(f"\n📁 {rel_path if str(rel_path) != '.' else '(root)'}")
        
        # Process each file
        for filename in files:
            if not filename.endswith(input_extension):
                stats['skipped'] += 1
                continue
            
            stats['processed'] += 1
            
            # Build paths
            encrypted_path = Path(root) / filename
            output_filename = filename.replace(input_extension, output_extension)
            output_file = current_output_dir / output_filename
            
            if verbose:
                print(f"  Processing: {filename}...", end=' ')
            
            # Decrypt the file
            success = decrypt_master_file(str(encrypted_path), str(output_file), verbose=False)
            
            if success:
                stats['succeeded'] += 1
                file_size = output_file.stat().st_size / 1024
                if verbose:
                    print(f"✓ → {output_filename} ({file_size:.2f} KB)")
            else:
                stats['failed'] += 1
                if verbose:
                    print(f"✗ Failed to decrypt")
    
    # Print summary
    print("\n" + "="*60)
    print("Decryption Summary")
    print("="*60)
    print(f"Total files processed: {stats['processed']}")
    print(f"Successfully decrypted: {stats['succeeded']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped (wrong extension): {stats['skipped']}")
    
    if stats['succeeded'] > 0:
        success_rate = (stats['succeeded'] / stats['processed']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    print("="*60)
    
    return stats


# Example usage
if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("FlatBuffer Master File Decryption Tool")
    print("="*60)
    print()
    
    if len(sys.argv) >= 3:
        input_directory = sys.argv[1]
        output_directory = sys.argv[2]
    else:
        # Default paths
        input_directory = "Assets/AssetBundles/Master"
        output_directory = "DecryptedMaster"
        
        print(f"Usage: {sys.argv[0]} <input_dir> <output_dir>")
        print("Using defaults:")
        print(f"  Input:  {input_directory}")
        print(f"  Output: {output_directory}")
        print()
    
    # Check if input exists
    if not os.path.exists(input_directory):
        print(f"❌ Error: Input directory '{input_directory}' does not exist!")
        sys.exit(1)
    
    # Run decryption
    stats = decrypt_directory_with_structure(
        input_dir=input_directory,
        output_dir=output_directory,
        input_extension='.bytes',
        output_extension='.fb',
        verbose=True
    )
    
    # Exit with appropriate code
    if stats['succeeded'] > 0:
        print(f"\n✅ Successfully decrypted {stats['succeeded']} files!")
        print(f"📂 Output saved to: {os.path.abspath(output_directory)}")
        sys.exit(0)
    else:
        print("\n⚠️  No files were successfully decrypted.")
        if stats['processed'] == 0:
            print("No .bytes files found in the input directory.")
        else:
            print("All decryption attempts failed. Check your keys.")
        sys.exit(1)