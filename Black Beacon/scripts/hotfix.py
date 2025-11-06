from pathlib import Path


def is_valid_dll(data):

    if len(data) < 0x100:  # Minimum size for PE header
        return False
    
    # Check MZ signature (DOS header)
    if data[0:2] != b'MZ':
        return False
    
    try:
        pe_offset = int.from_bytes(data[0x3C:0x3E], byteorder='little')
    except:  # noqa: E722
        return False
    
    # Check if PE offset is within file bounds
    if pe_offset >= len(data) - 4:
        return False
    
    # Check PE signature
    if data[pe_offset:pe_offset+4] != b'PE\x00\x00':
        return False
    

    try:
        characteristics_offset = pe_offset + 0x16
        if characteristics_offset + 2 <= len(data):
            characteristics = int.from_bytes(
                data[characteristics_offset:characteristics_offset+2], 
                byteorder='little'
            )
            # 0x2000 is IMAGE_FILE_DLL flag
            is_dll = (characteristics & 0x2000) != 0
            return is_dll
    except:
        pass
    
    # If we can't check the DLL flag, consider it valid if PE header is present
    return True


def is_valid_pdb(data):
   
    if len(data) < 32:
        return False
    
    # Check for Portable PDB signature (BSJB - Blob Stream JIT Binary)
    # This is used by .NET/Mono/Unity
    if data[0:4] == b'BSJB':
        return True
    
    # Check for PDB 7.0 signature (Microsoft C/C++ MSF 7.00)
    if data[0:32] == b'Microsoft C/C++ MSF 7.00\r\n\x1a\x44\x53\x00\x00\x00':
        return True
    
    # Check for older PDB 2.0 signature
    if data[0:29] == b'Microsoft C/C++ program database 2.00\r\n\x1a\x44\x53':
        return True
    
    if b'Microsoft C/C++' in data[0:50]:
        return True
    
    # Some PDBs might have different headers, check for .pdb in filename and common patterns
    return False


def detect_file_type(data):

    if is_valid_dll(data):
        return 'dll'
    elif is_valid_pdb(data):
        return 'pdb'
    else:
        return 'unknown'


def convert_bytes_file(filepath, output_dir=None, remove_bytes=False, skip_validation=False):

    try:
        # Read the file
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Determine the original extension based on filename
        filename = filepath.name
        
        # Handle different naming patterns
        if filename.endswith('.dll.bytes'):
            # Validate as DLL
            if not is_valid_dll(data):
                return False, f"Invalid DLL format: {filename}"
            
            output_filename = filename.replace('.dll.bytes', '.dll')
            file_type = "DLL"
            
        elif filename.endswith('.pdb.bytes'):
            # For PDB files, use relaxed validation or skip if flag is set
            if not skip_validation and not is_valid_pdb(data):
                # If validation fails but skip_validation is True, convert anyway
                if skip_validation:
                    pass
                else:
                    # Try to detect if it's actually a valid file by checking size
                    if len(data) > 100:
                        # Probably a valid PDB with non-standard header, convert anyway
                        pass
                    else:
                        return False, f"Invalid PDB format: {filename}"
            
            output_filename = filename.replace('.pdb.bytes', '.pdb')
            file_type = "PDB"
            
        elif filename.endswith('.bytes'):
            # Handle files without double extension (e.g., Assembly-CSharp.bytes)
            # Try to detect the file type
            detected_type = detect_file_type(data)
            
            if detected_type == 'dll':
                output_filename = filename[:-6] + '.dll'  # Remove .bytes, add .dll
                file_type = "DLL (auto-detected)"
            elif detected_type == 'pdb' or skip_validation:
                # Assume it's a PDB if not a DLL
                output_filename = filename[:-6] + '.pdb'  # Remove .bytes, add .pdb
                file_type = "PDB (assumed)"
            else:
                # Can't determine type, just remove .bytes extension
                output_filename = filename[:-6]
                file_type = "Unknown (kept as-is)"
            
        else:
            return False, f"Not a .bytes file: {filename}"
        
        # Determine output path
        if output_dir:
            output_path = Path(output_dir) / output_filename
        else:
            output_path = filepath.parent / output_filename
        
        # Write the converted file
        with open(output_path, 'wb') as f:
            f.write(data)
        
        # Remove original .bytes file if requested
        if remove_bytes:
            try:
                filepath.unlink()
            except Exception as e:
                return True, f"Converted {file_type}: {filename} -> {output_path.name} (Warning: Could not remove source: {e})"
        
        return True, f"Converted {file_type}: {filename} -> {output_path}"
        
    except Exception as e:
        return False, f"Error converting {filepath.name}: {str(e)}"


def scan_and_convert(source_dir, output_dir=None, remove_bytes=False, recursive=False, skip_validation=False):

    source_path = Path(source_dir)
    
    if not source_path.exists():
        print(f"Error: Source directory '{source_dir}' does not exist")
        return None
    
    # Create output directory if it doesn't exist
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {output_path}")
    else:
        output_path = None
    
    # Find all .bytes files
    if recursive:
        bytes_files = list(source_path.rglob('*.bytes'))
    else:
        bytes_files = list(source_path.glob('*.bytes'))
    
    if not bytes_files:
        print(f"No .bytes files found in '{source_dir}'")
        return {'total': 0, 'success': 0, 'failed': 0}
    
    print(f"Found {len(bytes_files)} .bytes file(s) in '{source_dir}'")
    if skip_validation:
        print("Note: PDB validation is disabled - all files will be converted")
    print("-" * 80)
    
    stats = {'total': len(bytes_files), 'success': 0, 'failed': 0}
    
    for bytes_file in bytes_files:
        success, message = convert_bytes_file(bytes_file, output_path, remove_bytes, skip_validation)
        
        if success:
            print(f"✓ {message}")
            stats['success'] += 1
        else:
            print(f"✗ {message}")
            stats['failed'] += 1
    
    print("-" * 80)
    print(f"Conversion complete: {stats['success']} succeeded, {stats['failed']} failed")
    
    return stats


def main():
    """Main function to handle command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert .dll.bytes and .pdb.bytes files back to their original format'
    )
    parser.add_argument(
        'source_directory',
        help='Source directory to scan for .bytes files'
    )
    parser.add_argument(
        'output_directory',
        nargs='?',
        default=None,
        help='Output directory for converted files (default: same as source)'
    )
    parser.add_argument(
        '-r', '--remove',
        action='store_true',
        help='Remove .bytes files after successful conversion'
    )
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='Scan subdirectories recursively'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation for PDB files (convert all .pdb.bytes files)'
    )
    
    args = parser.parse_args()
    
    scan_and_convert(
        args.source_directory, 
        args.output_directory, 
        remove_bytes=args.remove,
        recursive=args.recursive,
        skip_validation=args.skip_validation
    )


if __name__ == '__main__':
    main()