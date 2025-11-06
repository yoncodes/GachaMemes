#!/usr/bin/env python3

import sys
import json
from pathlib import Path
import importlib.util

def load_generated_module(module_name, module_path):
    """Dynamically load a Python module."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None

def read_flatbuffer_correct(fb_path: str, container_class):
    """
    Read a FlatBuffer file correctly, handling large offset tables.
    """
    with open(fb_path, 'rb') as f:
        buf = f.read()
    
    # Don't use bytearray - use bytes directly
    # GetRootAs expects the buffer as-is
    container = container_class.GetRootAs(buf, 0)
    return container


def extract_string_safe(item, method_name):

    try:
        if not hasattr(item, method_name):
            return None
        
        method = getattr(item, method_name)
        result = method()
        
        if result is None:
            return None
        
        # Handle bytes
        if isinstance(result, bytes):
            try:
                decoded = result.decode('utf-8', errors='strict')
                
                # Validate the decoded string
                if not decoded:
                    return None
                
                # Check for null bytes (indicates binary/corrupted data)
                if '\x00' in decoded:
                    return None
                
                # Check if string is mostly printable
                printable_count = sum(1 for c in decoded if c.isprintable() or c in '\n\r\t ')
                if len(decoded) > 0 and printable_count / len(decoded) < 0.8:
                    return None
                
                return decoded
                
            except UnicodeDecodeError:
                return None
        
        # Handle string
        if isinstance(result, str):
            # Check for null bytes
            if '\x00' in result:
                return None
            
            # Check if empty
            if not result.strip():
                return None
            
            # Check if mostly printable
            printable_count = sum(1 for c in result if c.isprintable() or c in '\n\r\t ')
            if len(result) > 0 and printable_count / len(result) < 0.8:
                return None
            
            return result
        
        return None
        
    except Exception:
        return None

def extract_item_correct(item):
    """
    Extract item data using proper FlatBuffer field accessors.
    """
    data = {}
    
    # String fields
    string_fields = [
        'Description',
        'Label',
        'ConditionValueA',
        'ConditionValueB',
        'ConditionValueC',
        'ConditionValueD',
        'ReleaseLabel',
    ]
    
    for field_name in string_fields:
        value = extract_string_safe(item, field_name)
        if value is not None:  # Only add if valid
            data[field_name] = value
    
    # Numeric fields
    numeric_fields = {
        'MasterMissionId': 'int64',
        'UnlockingTriggerId': 'int64',
        'MasterRewardGroupId': 'int64',
        'SubscriptionMasterRewardGroupId': 'int64',
        'TransitionStateValue': 'int64',
        'EventId': 'int64',
        'MasterMissionGroupId': 'int64',
        'ConditionValueN': 'int32',
        'GreatSageExpBonus': 'int32',
        'SortOrder': 'int32',
        'MasterOgcMissionCategory': 'enum',
        'MasterOgcMissionType': 'enum',
        'MasterOgcMissionUnlockingType': 'enum',
        'MasterOgcMissionTransitionState': 'enum',
        'MasterOgcMissionDisplayType': 'enum',
    }
    
    for field_name in numeric_fields:
        try:
            if not hasattr(item, field_name):
                continue
            
            method = getattr(item, field_name)
            value = method()
            
            if value is not None:
                data[field_name] = value
                
        except Exception:
            continue
    
    return data

def extract_item_generic_safe(item):

    data = {}
    
    for attr_name in dir(item):
        if attr_name.startswith('_') or attr_name in ['Init', 'GetRootAs', 'GetRootAsType', 'ByteBuffer']:
            continue
        
        if 'Length' in attr_name or 'IsNone' in attr_name:
            continue
        
        try:
            attr = getattr(item, attr_name)
            if not callable(attr):
                continue
            
            try:
                value = attr()
                
                if value is None:
                    continue
                
                # Handle different types
                if isinstance(value, (int, float, bool)):
                    data[attr_name] = value
                elif isinstance(value, bytes):
                    try:
                        decoded = value.decode('utf-8', errors='strict')
                        if decoded:
                            data[attr_name] = decoded
                    except:  # noqa: E722
                        pass
                elif isinstance(value, str):
                    if value:
                        data[attr_name] = value
                        
            except (TypeError, AttributeError):
                pass
            except Exception:
                pass
                
        except Exception:
            pass
    
    return data

def convert_fb_to_json(fb_path: str, json_path: str, generated_dir: str):
    """Convert a single FB file to JSON."""
    try:
        filename = Path(fb_path).stem
        container_name = f"{filename}Container"
        
        module_path = Path(generated_dir) / f"{container_name}.py"
        
        if not module_path.exists():
            print("  ⊘ No module")
            return None
        
        module = load_generated_module(container_name, str(module_path))
        if module is None:
            return False
        
        container_class = getattr(module, container_name, None)
        if container_class is None:
            return False
        
        # Use correct reading method
        container = read_flatbuffer_correct(fb_path, container_class)
        
        items = []
        if hasattr(container, 'DataListLength'):
            count = container.DataListLength()
            
            if count > 100000:
                print(f"  ⊘ Too many ({count})")
                return None
            
            # Choose extractor
            if filename == "MasterOgcMission":
                extractor = extract_item_correct
            else:
                extractor = extract_item_generic_safe
            
            max_items = min(count, 100000)
            
            for i in range(max_items):
                if i > 0 and i % 5000 == 0:
                    print(".", end='', flush=True)
                
                try:
                    item = container.DataList(i)
                    item_data = extractor(item)
                    
                    if item_data:
                        items.append(item_data)
                        
                except KeyboardInterrupt:
                    raise
                except Exception:
                    continue
        
        if items:
            Path(json_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'source': filename,
                    'count': len(items),
                    'data': items
                }, f, indent=2, ensure_ascii=False)
            
            print(f"  ✓ {len(items)} items")
            return True
        else:
            print("  ⚠ No data")
            return None
            
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")
        return False

def process_all_flatbuffers(input_dir: str, output_dir: str, generated_dir: str):
    """Process all .fb files."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    fb_files = sorted(list(input_path.glob('**/*.fb')))
    
    print(f"Found {len(fb_files)} FlatBuffer files")
    print("="*60)
    
    success = 0
    failed = 0
    skipped = 0
    
    for idx, fb_file in enumerate(fb_files, 1):
        rel_path = fb_file.relative_to(input_path)
        json_file = output_path / rel_path.with_suffix('.json')
        
        print(f"[{idx}/{len(fb_files)}] {rel_path.name}...", end=' ', flush=True)
        
        try:
            result = convert_fb_to_json(str(fb_file), str(json_file), generated_dir)
            
            if result is True:
                success += 1
            elif result is None:
                skipped += 1
            else:
                failed += 1
                
        except KeyboardInterrupt:
            print("\n\n⚠ Interrupted")
            break
        except Exception:
            print("  ✗ Error")
            failed += 1
    
    print("\n" + "="*60)
    print(f"  ✓ Succeeded: {success}")
    print(f"  ✗ Failed: {failed}")
    print(f"  ⊘ Skipped: {skipped}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fb2json.py <input_dir> [output_dir] [generated_dir]")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "ExtractedJSON_Fixed")
    generated_dir = sys.argv[3] if len(sys.argv) > 3 else "./generated"
    
    try:
        process_all_flatbuffers(input_dir, output_dir, generated_dir)
    except KeyboardInterrupt:
        print("\n\n⚠ Stopped")