import sys
import csv
from binary_table import BinaryTable

def write_tsv(outpath, table):
    """Write table to TSV file"""
    with open(outpath, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(table.get_column_names())
        for row in table.get_rows():
            w.writerow([row.get(col, "") for col in table.get_column_names()])

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug.py <file.tab.bytes>")
        return
    
    input_path = sys.argv[1]
    
    # Parse the table
    print(f"Loading {input_path}...")
    table = BinaryTable(input_path).load()
    
    # Show info
    print(f"\n{table}")
    print(f"[header] has_pk={table.has_pk}, pk_idx={table.pk_idx}, magic=0x{table.magic:08X}")
    
    print("\n[columns]")
    type_names = {
        1: "bool", 2: "string", 3: "fix", 4: "list<string>",
        5: "list<bool>", 6: "list<int>", 7: "list<float>",
        8: "list<fix>", 9: "dic<str,str>", 10: "dic<int,int>",
        11: "dic<int,str>", 12: "dic<str,int>", 13: "dic<int,float>",
        14: "int", 15: "float", 16: "fix2", 17: "fix3",
        18: "fixquat", 19: "list<fix2>", 20: "list<fix3>",
        21: "list<fixquat>"
    }
    for col_type, col_name in table.columns:
        print(f"  {col_name} ({type_names.get(col_type, f'type{col_type}')})")
    
    print("\n[data] First 3 rows:")
    for i, row in enumerate(table.get_rows()[:3]):
        print(f"  {i}: {row}")
    
    if len(table.rows) > 3:
        print("\n[data] Last row:")
        print(f"  {len(table.rows)-1}: {table.rows[-1]}")
    
    # Write output
    base_name = input_path.replace('.tab.bytes', '')
    output_path = f"{base_name}.tsv"
    write_tsv(output_path, table)
    print(f"\n[output] Wrote {output_path}")

if __name__ == "__main__":
    main()