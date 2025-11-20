# batch_parse.py
import os
import sys
import csv
import json
import shutil
from datetime import datetime
from binary_table import BinaryTable

def write_tsv(outpath, table):
    """Write table to TSV file"""
    with open(outpath, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(table.get_column_names())
        for row in table.get_rows():
            w.writerow([row.get(col, "") for col in table.get_column_names()])

def parse_single_file(input_path, input_base_dir, output_base_dir, verbose=False):
    """Parse a single .tab.bytes file and return success status"""
    try:
        # Get file size before
        input_size = os.path.getsize(input_path)
        
        if verbose:
            print(f"\nProcessing: {input_path}")
            print(f"  Input size: {input_size:,} bytes")
        
        # Parse the table
        table = BinaryTable(input_path).load()
        
        # Calculate relative path from input base directory
        relative_path = os.path.relpath(input_path, input_base_dir)
        relative_dir = os.path.dirname(relative_path)
        
        # Generate output path preserving directory structure
        filename = os.path.basename(input_path)
        output_filename = filename.replace('.tab.bytes', '.tsv')
        output_dir = os.path.join(output_base_dir, relative_dir)
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        temp_output = output_filename
        
        # Check if input was already a TSV
        with open(input_path, 'rb') as f:
            first_bytes = f.read(10)
        
        is_already_tsv = first_bytes.startswith(b'Name\t') or first_bytes.startswith(b'Name\x09')
        
        if is_already_tsv:
            # Just copy the file directly
            final_output = os.path.join(output_dir, output_filename)
            shutil.copy2(input_path, final_output)
            
            return {
                'success': True,
                'status': 'PASS (already TSV)',
                'rows': table.row_count,
                'columns': table.col_count,
                'input_size': input_size,
                'output_size': input_size,
                'output_path': final_output,
                'relative_path': relative_path
            }
        
        # Write TSV
        write_tsv(temp_output, table)
        
        # Check output size
        output_size = os.path.getsize(temp_output)
        
        if verbose:
            print(f"  Output size: {output_size:,} bytes")
            print(f"  Rows parsed: {len(table.rows)}")
        
        # Determine success based on multiple criteria
        if len(table.rows) == 0 and table.row_count == 0:
            success = True
            status = "PASS (empty table)"
        elif output_size > input_size:
            success = True
            status = "PASS"
        elif table.row_count > 0 and len(table.rows) == table.row_count:
            success = True
            status = "PASS (complete)"
        elif len(table.rows) > 0 and output_size >= 50:
            success = True
            status = "PASS"
        else:
            success = False
            if len(table.rows) == 0:
                status = "FAIL - no rows parsed"
                error = "Failed to parse any rows from non-empty file"
            else:
                status = "FAIL - incomplete parse"
                error = f"Parsed {len(table.rows)}/{table.row_count} rows, output too small"
        
        if success:
            # Move to output directory
            final_output = os.path.join(output_dir, output_filename)
            shutil.move(temp_output, final_output)
            
            if verbose:
                print(f"  Status: ✓ {status}")
                print(f"  Moved to: {final_output}")
            
            return {
                'success': True,
                'status': status,
                'rows': len(table.rows),
                'columns': len(table.columns),
                'input_size': input_size,
                'output_size': output_size,
                'output_path': final_output,
                'relative_path': relative_path
            }
        else:
            # Remove failed output
            if os.path.exists(temp_output):
                os.remove(temp_output)
            
            if verbose:
                print(f"  Status: ✗ {status}")
            
            return {
                'success': False,
                'status': status,
                'rows': len(table.rows),
                'columns': len(table.columns),
                'input_size': input_size,
                'output_size': output_size,
                'error': error,
                'relative_path': relative_path
            }
            
    except Exception as e:
        status = f"ERROR: {str(e)}"
        if verbose:
            print(f"  Status: ✗ {status}")
        
        # Clean up temp file if it exists
        filename = os.path.basename(input_path)
        temp_output = filename.replace('.tab.bytes', '.tsv')
        if os.path.exists(temp_output):
            os.remove(temp_output)
        
        relative_path = os.path.relpath(input_path, input_base_dir)
        
        return {
            'success': False,
            'status': 'ERROR',
            'rows': 0,
            'columns': 0,
            'input_size': os.path.getsize(input_path) if os.path.exists(input_path) else 0,
            'output_size': 0,
            'error': str(e),
            'relative_path': relative_path
        }

def main():
    if len(sys.argv) < 2:
        print("Usage: python batch.py <input_directory> [output_directory]")
        print("  input_directory: Directory containing .tab.bytes files")
        print("  output_directory: Base directory for output (default: './parsed_tables')")
        print("\nDirectory structure will be preserved from input to output")
        return
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./parsed_tables"
    
    # Find all .tab.bytes files
    print(f"Searching for .tab.bytes files in: {input_dir}")
    
    tab_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.tab.bytes'):
                full_path = os.path.join(root, file)
                tab_files.append(full_path)
    
    if not tab_files:
        print("No .tab.bytes files found!")
        return
    
    print(f"Found {len(tab_files)} .tab.bytes files")
    print(f"Output will preserve directory structure to: {os.path.abspath(output_dir)}\n")
    print("=" * 80)
    
    # Process all files
    results = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'input_directory': os.path.abspath(input_dir),
            'output_directory': os.path.abspath(output_dir),
            'total_files': len(tab_files)
        },
        'passed': [],
        'failed': []
    }
    
    passed_count = 0
    failed_count = 0
    
    for i, filepath in enumerate(tab_files, 1):
        filename = os.path.basename(filepath)
        relative_path = os.path.relpath(filepath, input_dir)
        
        print(f"[{i}/{len(tab_files)}] {relative_path}...", end=" ", flush=True)
        
        result = parse_single_file(filepath, input_dir, output_dir, verbose=False)
        
        # Build result entry
        entry = {
            'filename': filename,
            'relative_path': result['relative_path'],
            'input_path': filepath,
            'status': result['status'],
            'rows': result['rows'],
            'columns': result['columns'],
            'input_size': result['input_size'],
            'output_size': result['output_size']
        }
        
        if result['success']:
            entry['output_path'] = result['output_path']
            results['passed'].append(entry)
            passed_count += 1
            print(f"✓ ({result['rows']} rows)")
        else:
            entry['error'] = result.get('error', 'Unknown error')
            results['failed'].append(entry)
            failed_count += 1
            print(f"✗ {result['status']}")
    
    # Update metadata
    results['metadata']['passed_count'] = passed_count
    results['metadata']['failed_count'] = failed_count
    results['metadata']['success_rate'] = f"{passed_count/len(tab_files)*100:.1f}%"
    
    # Write results to JSON
    json_output = os.path.join(output_dir, 'parse_results.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 80)
    print("\nSUMMARY:")
    print(f"  Total files: {len(tab_files)}")
    print(f"  Passed: {passed_count} ({passed_count/len(tab_files)*100:.1f}%)")
    print(f"  Failed: {failed_count} ({failed_count/len(tab_files)*100:.1f}%)")
    
    # Print failed files if any
    if failed_count > 0:
        print("\nFAILED FILES:")
        for entry in results['failed']:
            error_msg = entry.get('error', entry['status'])
            print(f"  - {entry['relative_path']}: {error_msg}")
    
    print("\nResults saved to:")
    print(f"  TSV files: {os.path.abspath(output_dir)}")
    print(f"  JSON report: {json_output}")

if __name__ == "__main__":
    main()