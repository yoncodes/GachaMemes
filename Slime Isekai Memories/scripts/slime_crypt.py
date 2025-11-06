import os
from pathlib import Path
from typing import Union
import gzip
from hashlib import sha256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

class Cryptograph:
    @staticmethod
    def Encrypt(data: Union[str, bytes], password: Union[str, bytes]) -> bytes:
        if isinstance(data, str):
            data = data.encode("utf8")
        if isinstance(password, str):
            password = password.encode("utf8")
        data_salt = get_random_bytes(0x10)
        salt = get_random_bytes(0x10)
        hash_password = sha256(password).digest()
        encrypted = Cryptograph.EncryptInternal(data_salt + data, hash_password, salt)
        return encrypted[:0x10] + salt + encrypted[0x10:]

    @staticmethod
    def EncryptInternal(target: bytes, password: bytes, salt: bytes) -> bytes:
        keys = PBKDF2(password, salt, 0x30, count=10)
        cipher = AES.new(key=keys[:0x20], iv=keys[0x20:0x30], mode=AES.MODE_CBC)
        return cipher.encrypt(pad(target, block_size=0x10, style="pkcs7"))

    @staticmethod
    def Decrypt(data: bytes, password: bytes) -> bytes:
        hash_password = sha256(password).digest()
        decrypted = Cryptograph.DecryptInternal(bytes(data), hash_password)
        return decrypted[0x10:]  # strip data_salt

    @staticmethod
    def DecryptInternal(target: bytes, password: bytes) -> bytes:
        data = target[:0x10] + target[0x20:]
        salt = target[0x10:0x20]
        keys = PBKDF2(password, salt, 0x30, count=10)
        cipher = AES.new(key=keys[:0x20], iv=keys[0x20:0x30], mode=AES.MODE_CBC)
        return unpad(cipher.decrypt(data), block_size=0x10, style="pkcs7")


class LuaCryptPacker:
    # Python version
    aes_key = bytes.fromhex('F30847CEE4D5BD81C9F9F0122D19E01ED0AADD7ADE8B3C7374B3D1EF9FC5DFC3')
    AES_Key: bytes = aes_key

    @staticmethod
    def Pack(text: str) -> bytes:
        compressed = gzip.compress(text.encode("utf8"))
        encrypted = Cryptograph.Encrypt(compressed, LuaCryptPacker.AES_Key)
        return encrypted

    @staticmethod
    def Unpack(cipher: bytes) -> str:
        decrypted = Cryptograph.Decrypt(cipher, LuaCryptPacker.AES_Key)
        decompressed = gzip.decompress(decrypted)
        return decompressed.decode("utf8")


def decrypt_directory_recursive(input_dir: str, output_dir: str, 
                                file_extensions: tuple = ('.bytes',),
                                output_extension: str = '.lua',
                                verbose: bool = True):
    """
    Recursively decrypt all files in a directory tree and recreate the folder structure.
    
    Args:
        input_dir: Source directory containing encrypted files
        output_dir: Destination directory for decrypted files
        file_extensions: Tuple of file extensions to process
        output_extension: Extension for output files (default: .lua)
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
    
    # Walk through all directories and files
    for root, dirs, files in os.walk(input_path):
        # Calculate relative path from input_dir
        rel_path = Path(root).relative_to(input_path)
        
        # Create corresponding output directory
        current_output_dir = output_path / rel_path
        current_output_dir.mkdir(parents=True, exist_ok=True)
        
        if verbose and files:
            print(f"\n📁 Processing directory: {rel_path if str(rel_path) != '.' else '(root)'}")
        
        # Process each file
        for filename in files:
            input_file = Path(root) / filename
            
            # Check if file should be processed
            if not any(filename.lower().endswith(ext) for ext in file_extensions):
                stats['skipped'] += 1
                if verbose:
                    print(f"  ⊘ Skipped: {filename} (not a target extension)")
                continue
            
            stats['processed'] += 1
            
            # Determine output filename (replace .bytes with .lua)
            output_filename = filename
            for ext in file_extensions:
                if filename.lower().endswith(ext):
                    output_filename = filename[:-len(ext)] + output_extension
                    break
            
            output_file = current_output_dir / output_filename
            
            try:
                # Read encrypted file
                with open(input_file, 'rb') as f:
                    encrypted_data = f.read()
                
                # Decrypt
                decrypted_text = LuaCryptPacker.Unpack(encrypted_data)
                
                # Write decrypted file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(decrypted_text)
                
                stats['succeeded'] += 1
                
                if verbose:
                    size_kb = len(encrypted_data) / 1024
                    lines = decrypted_text.count('\n') + 1
                    print(f"  ✓ {filename} ({size_kb:.2f} KB, {lines} lines) -> {output_filename}")
                    
            except Exception as e:
                stats['failed'] += 1
                print(f"  ✗ Failed to decrypt {filename}: {e}")
    
    # Print summary
    print("\n" + "="*60)
    print("Decryption Summary")
    print("="*60)
    print(f"Total files processed: {stats['processed']}")
    print(f"Successfully decrypted: {stats['succeeded']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped (wrong extension): {stats['skipped']}")
    print("="*60)
    
    return stats

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) >= 3:
        input_directory = sys.argv[1]
        output_directory = sys.argv[2]
    else:
        # Default directories
        input_directory = "encrypted_lua"
        output_directory = "decrypted_lua"
        
        print(f"Usage: {sys.argv[0]} <input_dir> <output_dir>")
        print("Using default directories:")
        print(f"  Input:  {input_directory}")
        print(f"  Output: {output_directory}\n")
    
    # Check if input directory exists
    if not os.path.exists(input_directory):
        print(f"❌ Error: Input directory '{input_directory}' does not exist!")
        print("Please create it or specify a valid directory.")
        sys.exit(1)
    
    # Run recursive decryption
    print("Starting recursive decryption...")
    print(f"Input:  {os.path.abspath(input_directory)}")
    print(f"Output: {os.path.abspath(output_directory)}")
    print("Target: .bytes files → .lua files")
    print("="*60)
    
    stats = decrypt_directory_recursive(
        input_dir=input_directory,
        output_dir=output_directory,
        file_extensions=('.bytes', '.lua.bytes', '.bin'),  # Accept these extensions
        output_extension='.lua',
        verbose=True
    )
    
    if stats['succeeded'] > 0:
        print(f"\n✓ Successfully decrypted {stats['succeeded']} files!")
        print(f"📂 Output saved to: {os.path.abspath(output_directory)}")
    elif stats['processed'] == 0:
        print("\n⚠ No .bytes files found to decrypt.")
        print("Make sure your encrypted Lua files have the .bytes extension.")
    else:
        print(f"\n⚠ All {stats['processed']} files failed to decrypt.")
        print("The AES key or encryption method might be incorrect.")