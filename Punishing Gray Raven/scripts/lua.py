import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

def convert_lua_bytes(src_path, dest_path):
    """Convert a single .lua.bytes file to .lua"""
    try:
        with open(src_path, "rb") as f:
            data = f.read()

        # Try UTF-8 first, fallback to other encodings if needed
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8-sig", errors="ignore")

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(text)

        return {
            'success': True,
            'status': 'PASS',
            'input_size': len(data),
            'output_size': len(text.encode('utf-8'))
        }

    except Exception as e:
        return {
            'success': False,
            'status': 'ERROR',
            'error': str(e),
            'input_size': os.path.getsize(src_path) if os.path.exists(src_path) else 0,
            'output_size': 0
        }

def main():
    if len(sys.argv) < 2:
        print("Usage: python lua.py <input_directory> [output_directory]")
        print("  input_directory: Directory containing .lua.bytes files")
        print("  output_directory: Base directory for output (default: './lua')")
        print("\nDirectory structure will be preserved from input to output")
        return
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./lua"
    
    # Find all .lua.bytes files
    print(f"Searching for .lua.bytes files in: {input_dir}")
    
    lua_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.lua.bytes'):
                full_path = os.path.join(root, file)
                lua_files.append(full_path)
    
    if not lua_files:
        print("No .lua.bytes files found!")
        return
    
    print(f"Found {len(lua_files)} .lua.bytes files")
    print(f"Output will preserve directory structure to: {os.path.abspath(output_dir)}\n")
    print("=" * 80)
    
    # Process all files
    results = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'input_directory': os.path.abspath(input_dir),
            'output_directory': os.path.abspath(output_dir),
            'total_files': len(lua_files)
        },
        'passed': [],
        'failed': []
    }
    
    passed_count = 0
    failed_count = 0
    
    for i, filepath in enumerate(lua_files, 1):
        filename = os.path.basename(filepath)
        relative_path = os.path.relpath(filepath, input_dir)
        relative_dir = os.path.dirname(relative_path)
        
        print(f"[{i}/{len(lua_files)}] {relative_path}...", end=" ", flush=True)
        
        # Calculate output path preserving directory structure
        output_filename = filename.replace('.lua.bytes', '.lua')
        output_subdir = os.path.join(output_dir, relative_dir)
        os.makedirs(output_subdir, exist_ok=True)
        output_path = os.path.join(output_subdir, output_filename)
        
        # Convert the file
        result = convert_lua_bytes(filepath, output_path)
        
        # Build result entry
        entry = {
            'filename': filename,
            'relative_path': relative_path,
            'input_path': filepath,
            'status': result['status'],
            'input_size': result['input_size'],
            'output_size': result['output_size']
        }
        
        if result['success']:
            entry['output_path'] = output_path
            results['passed'].append(entry)
            passed_count += 1
            print(f"✓ ({result['output_size']:,} bytes)")
        else:
            entry['error'] = result.get('error', 'Unknown error')
            results['failed'].append(entry)
            failed_count += 1
            print(f"✗ {result['status']}: {result.get('error', 'Unknown error')}")
    
    # Update metadata
    results['metadata']['passed_count'] = passed_count
    results['metadata']['failed_count'] = failed_count
    results['metadata']['success_rate'] = f"{passed_count/len(lua_files)*100:.1f}%"
    
    # Write results to JSON
    """json_output = os.path.join(output_dir, 'convert_results.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)"""
    
    # Print summary
    print("\n" + "=" * 80)
    print("\nSUMMARY:")
    print(f"  Total files: {len(lua_files)}")
    print(f"  Passed: {passed_count} ({passed_count/len(lua_files)*100:.1f}%)")
    print(f"  Failed: {failed_count} ({failed_count/len(lua_files)*100:.1f}%)")
    
    # Print failed files if any
    if failed_count > 0:
        print("\nFAILED FILES:")
        for entry in results['failed']:
            error_msg = entry.get('error', entry['status'])
            print(f"  - {entry['relative_path']}: {error_msg}")
    
    print("\nResults saved to:")
    print(f"  Lua files: {os.path.abspath(output_dir)}")
    #print(f"  JSON report: {json_output}")

if __name__ == "__main__":
    main()