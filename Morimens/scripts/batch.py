import sys
import subprocess
import re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Statistics
stats = {"total": 0, "success": 0, "failed": 0}

# Regex to match Lua strings
STRING_RE = re.compile(r'"(.*?)"', re.DOTALL)

def decode_lua_string(s: str) -> str:
    """Decode \230\142\168 style escapes to UTF-8"""
    out = bytearray()
    i = 0
    length = len(s)
    
    while i < length:
        c = s[i]
        
        if c == '\\' and i + 1 < length:
            i += 1
            
            # Decimal escape: \123
            if s[i].isdigit():
                num = 0
                count = 0
                while i < length and s[i].isdigit() and count < 3:
                    num = num * 10 + int(s[i])
                    i += 1
                    count += 1
                out.append(num & 0xFF)
                continue
            
            # Common escapes
            escapes = {'n': b'\n', 'r': b'\r', 't': b'\t', '"': b'"', '\\': b'\\'}
            if s[i] in escapes:
                out += escapes[s[i]]
            else:
                out.append(ord(s[i]))
            
            i += 1
        else:
            out.append(ord(c))
            i += 1
    
    return out.decode('utf-8', errors='replace')

def decode_chinese_strings(text: str) -> str:
    """Replace all strings in Lua code with decoded versions"""
    def fix_string(match):
        inner = match.group(1)
        decoded = decode_lua_string(inner)
        return f'"{decoded}"'
    
    return STRING_RE.sub(fix_string, text)

def process_file(input_path: Path, output_path: Path, file_num: int, verbose: bool = False) -> tuple:
    """Process a single file with unluac"""
    try:
        if verbose:
            print(f"\n[{file_num}] {input_path.name}")
            print("   → Decompiling with unluac...")
        
        # Run unluac with better error handling
        result = subprocess.run(
            ["java", "-jar", "unluac.jar", str(input_path)],
            capture_output=True,
            text=True,
            timeout=60,  
            encoding='utf-8',
            errors='replace'
        )
        
        # Check if output looks like valid Lua
        output = result.stdout.strip()
        
        if not output:
            if verbose:
                print("   ✗ No output from unluac")
                if result.stderr:
                    print(f"   Error: {result.stderr[:100]}")
            return (input_path.name, False, "No output")
        
        # Check for error indicators in output
        if output.startswith("Exception") or "error" in output[:100].lower():
            if verbose:
                print("   ✗ unluac error")
                print(f"   Output: {output[:200]}")
            return (input_path.name, False, "Decompilation error")
        
        # Check for minimum valid Lua output
        if len(output) < 10:
            if verbose:
                print(f"   ✗ Output too small ({len(output)} bytes)")
            return (input_path.name, False, "Output too small")
        
        if verbose:
            print("   → Decoding Chinese characters...")
        
        # Decode Chinese strings
        decoded = decode_chinese_strings(output)
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(decoded, encoding='utf-8')
        
        if verbose:
            print("   ✓ Success")
        
        return (input_path.name, True, None)
        
    except subprocess.TimeoutExpired:
        if verbose:
            print("   ✗ Timeout (>60s)")
        return (input_path.name, False, "Timeout")
    except Exception as e:
        if verbose:
            print(f"   ✗ Error: {e}")
        return (input_path.name, False, str(e))

def process_file_parallel(args):
    """Wrapper for parallel processing"""
    input_path, output_path, file_num = args
    return process_file(input_path, output_path, file_num, verbose=False)

def get_output_path(input_base: Path, input_file: Path, output_base: Path) -> Path:
    """Get output path maintaining directory structure"""
    relative = input_file.relative_to(input_base)
    output = output_base / relative
    
    # Change extension to .lua
    if output.suffix == '.bytes':
        output = output.with_suffix('')  # Remove .bytes
    if output.suffix == '.luac':
        output = output.with_suffix('.lua')
    elif not output.suffix == '.lua':
        output = output.with_suffix('.lua')
    
    return output

def collect_files(input_dir: Path) -> list:
    """Collect all .luac and .lua.bytes files"""
    files = []
    for ext in ['*.luac', '*.bytes']:
        files.extend(input_dir.rglob(ext))
    return sorted(files)

def batch_process_serial(input_dir: Path, output_dir: Path):
    """Process files one by one (shows progress)"""
    files = collect_files(input_dir)
    
    if not files:
        print("No .luac or .lua.bytes files found")
        return
    
    print(f"Found {len(files)} files to process\n")
    
    failed_files = []
    
    for i, input_path in enumerate(files, 1):
        output_path = get_output_path(input_dir, input_path, output_dir)
        filename, success, error = process_file(input_path, output_path, i, verbose=True)
        
        stats["total"] += 1
        if success:
            stats["success"] += 1
        else:
            stats["failed"] += 1
            failed_files.append((filename, error))
    
    # Print failed files summary
    if failed_files:
        print("\n" + "=" * 40)
        print("FAILED FILES:")
        print("=" * 40)
        for filename, error in failed_files:
            print(f"  {filename}: {error}")

def batch_process_parallel(input_dir: Path, output_dir: Path, workers: int = 4):
    """Process files in parallel (faster)"""
    files = collect_files(input_dir)
    
    if not files:
        print("No .luac or .lua.bytes files found")
        return
    
    print(f"Found {len(files)} files to process")
    print(f"Using {workers} parallel workers")
    print("Processing...\n")
    
    # Prepare work items
    work_items = []
    for i, input_path in enumerate(files, 1):
        output_path = get_output_path(input_dir, input_path, output_dir)
        work_items.append((input_path, output_path, i))
    
    failed_files = []
    completed = 0
    
    # Process in parallel
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file_parallel, item): item for item in work_items}
        
        for future in as_completed(futures):
            filename, success, error = future.result()
            stats["total"] += 1
            completed += 1
            
            if success:
                stats["success"] += 1
                status = "✓"
            else:
                stats["failed"] += 1
                failed_files.append((filename, error))
                status = "✗"
            
            # Progress indicator
            print(f"[{completed}/{len(files)}] {status} {filename}")
    
    # Print failed files summary
    if failed_files:
        print("\n" + "=" * 40)
        print("FAILED FILES:")
        print("=" * 40)
        for filename, error in failed_files:
            print(f"  {filename}: {error}")

def print_statistics():
    """Print final statistics"""
    print("\n" + "=" * 40)
    print("BATCH DECOMPILATION COMPLETE")
    print("=" * 40)
    print(f"Total files:      {stats['total']}")
    if stats['total'] > 0:
        print(f"Successful:       {stats['success']} ({100.0 * stats['success'] / stats['total']:.1f}%)")
        print(f"Failed:           {stats['failed']} ({100.0 * stats['failed'] / stats['total']:.1f}%)")
    print()

def main():
    if len(sys.argv) < 3:
        print("Usage: python batch.py <input_dir> <output_dir> [--parallel N]")
        print()
        print("  --parallel N    Use N parallel workers (default: serial)")
        print()
        print("Examples:")
        print("  python batch.py lua/ lua_dec/")
        print("  python batch.py lua/ lua_dec/ --parallel 4")
        sys.exit(1)
    
    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    
    # Check for parallel mode
    parallel = False
    workers = 8
    if len(sys.argv) >= 4 and sys.argv[3] == '--parallel':
        parallel = True
        if len(sys.argv) >= 5:
            workers = int(sys.argv[4])
    
    # Check if unluac.jar exists
    if not Path("unluac.jar").exists():
        print("Error: unluac.jar not found in current directory")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory")
        sys.exit(1)
    
    print("Batch decompilation with unluac")
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print("-" * 40)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if parallel:
        batch_process_parallel(input_dir, output_dir, workers)
    else:
        batch_process_serial(input_dir, output_dir)
    
    print_statistics()
    
    return 0 if stats['failed'] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())