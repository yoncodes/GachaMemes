import os
from reader import Reader

class BinaryTable:
    """Parser for .tab.bytes binary table files"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = None
        
        # Header fields
        self.header_len = 0
        self.col_count = 0
        self.columns = []
        self.has_pk = False
        self.pk_idx = 0
        self.primary_key = None
        self.primary_key_len = 0
        self.row_trunk_len = 0
        self.row_count = 0
        self.content_trunk_len = 0
        self.magic = 0
        
        # String pool fields
        self.m_pool_column_size = -1
        self.m_column_map = {}
        self.m_pool_offset_info_array = []
        self.m_pool_content_start_pos = 0
        
        self.rows = []
        
    def load(self):
        """Load and parse the binary table file"""
        with open(self.filepath, 'rb') as f:
            self.data = f.read()
        
        # Check for special case: file is already a TSV
        if self.data.startswith(b'Name\t') or self.data.startswith(b'Name\x09'):
            # This is already a TSV file (like Sha1.tab.bytes)
            # Parse it as TSV to populate rows
            self._parse_existing_tsv()
            return self
        
        # Check for empty/zeroed files
        if len(self.data) > 100 and self.data[:100] == b'\x00' * 100:
            raise ValueError("File is empty or corrupted (all zeros)")
        
        self._parse_header()
        self._parse_content()
        
        return self

    def _parse_existing_tsv(self):
        """Parse a file that's already in TSV format"""
        import csv
        from io import StringIO
        
        # Decode as text
        text = self.data.decode('utf-8', errors='ignore')
        
        # Parse TSV
        reader = csv.reader(StringIO(text), delimiter='\t')
        lines = list(reader)
        
        if len(lines) < 1:
            self.columns = []
            self.rows = []
            return
        
        # First line is headers
        headers = lines[0]
        self.col_count = len(headers)
        
        # Create columns with unknown type (14 = int as default)
        self.columns = [(14, name) for name in headers]
        
        # Remaining lines are data
        self.rows = []
        for line in lines[1:]:
            row = {}
            for i, value in enumerate(line):
                if i < len(headers):
                    row[headers[i]] = value
            self.rows.append(row)
        
        # Set other fields
        self.has_pk = False
        self.pk_idx = 0
        self.row_count = len(self.rows)
        
    def _parse_header(self):
        """Parse the complete file header"""
        reader = Reader()
        reader.load_bytes(self.data)
        
        # Read header length (this is the ONLY fixed u32!)
        self.header_len = reader.read_u32_le()
        
        # Everything else in the header uses varints!
        self.col_count = reader.read_int()
        
        # Read columns
        for _ in range(self.col_count):
            col_type = reader.read_int()
            col_name = reader.read_string()
            self.columns.append((col_type, col_name))
        
        # Read primary key info
        self.has_pk = reader.read_bool()
        
        if self.has_pk:
            primary_key_index = reader.read_int() or 0
            if primary_key_index < len(self.columns):
                self.primary_key = self.columns[primary_key_index][1]
            self.primary_key_len = reader.read_int() or 0
        
        # Read row and content info
        self.row_trunk_len = reader.read_int() or 0
        self.row_count = reader.read_int() or 0
        self.content_trunk_len = reader.read_int() or 0
        
        #print(f"[DEBUG] Header: row_count={self.row_count}, content_len={self.content_trunk_len}")
        #print(f"[DEBUG] row_trunk_len={self.row_trunk_len}, pk_len={self.primary_key_len}")
        
        # Check where we are in the header
        header_end = 4 + self.header_len
        if reader.index < header_end:
                remaining = header_end - reader.index
                if remaining >= 4:
                    self.magic = reader.read_u32_le()
                    
        #print(f"[DEBUG] Header ends at byte {header_end}, currently at {reader.index}")
    
    def get_index_trunk_position(self):
        """Get position after header (where index trunk starts)"""
        return 4 + self.header_len
    
    def get_after_primary_key_trunk_position(self):
        """Get position after primary key index"""
        position = self.get_index_trunk_position()
        if self.has_pk:
            position += self.primary_key_len
        return position
    
    def get_content_trunk_position(self):
        """Get position where content starts"""
        return self.get_after_primary_key_trunk_position() + self.row_trunk_len
    
    def get_pool_offset_trunk_start_position(self):
        """Get position where string pool offset trunk starts"""
        return self.get_content_trunk_position() + self.content_trunk_len
    
    def get_pool_content_trunk_start_position(self):
        """Get position where string pool content starts"""
        return self.get_pool_offset_trunk_start_position() + self.m_pool_content_start_pos
    
    def _has_string_columns(self):
        """Check if table has any string columns"""
        for col_type, _ in self.columns:
            if col_type in [2, 4]:  # string or list<string>
                return True
        return False
    
    def _parse_content(self):
        """Parse the content section"""
        # Get content section
        content_start = self.get_content_trunk_position()
        content_end = content_start + self.content_trunk_len
        
        #print(f"[DEBUG] Content: bytes {content_start} to {content_end}")
        
        if content_end > len(self.data):
            print(f"[WARN] Content end ({content_end}) exceeds file size ({len(self.data)})")
            content_end = len(self.data)
        
        content = self.data[content_start:content_end]
        
        # Initialize string pool BEFORE parsing content
        self._read_pool_info_trunk()
        
        # Check if table has complex types OR uses string pool
        has_complex_types = self._has_complex_types()
        has_string_pool = self.m_pool_column_size > 0
        has_strings = self._has_string_columns()
        
        #print(f"[DEBUG] has_complex_types={has_complex_types}, has_string_pool={has_string_pool}")
        
        if has_complex_types or has_string_pool or has_strings:
            # Must use Reader for type-aware parsing
            #print("[DEBUG] Using Reader-based parsing")
            self._parse_with_reader(content)
        else:
            # Can use fast varint array method
            #print("[DEBUG] Using varint array parsing")
            self._parse_with_varints(content)
    
    def _read_pool_info_trunk(self):
        """Initialize string pool data structure"""
        try:
            position = self.get_pool_offset_trunk_start_position()
            
            if position >= len(self.data):
                #print("[DEBUG] No string pool (position exceeds file size)")
                self.m_pool_column_size = 0
                return
            
            #print(f"[DEBUG] Reading string pool at position {position} (file size: {len(self.data)})")
            
            reader = Reader()
            reader.load_bytes(self.data)
            reader.index = position
            
            # Read pool header length (fixed u32)
            pool_head_length = reader.read_u32_le()
            
            #print(f"[DEBUG] String pool header length: {pool_head_length}")
            
            if not pool_head_length or pool_head_length <= 0 or pool_head_length > 10000:
                #print(f"[DEBUG] Invalid pool_head_length: {pool_head_length}")
                self.m_pool_column_size = 0
                return
            
            # Read pool header fields (all varints)
            self.m_pool_column_size = reader.read_int() or 0
            
            if self.m_pool_column_size <= 0 or self.m_pool_column_size > 100:
                #print(f"[DEBUG] Invalid pool_column_size: {self.m_pool_column_size}")
                self.m_pool_column_size = 0
                return
            
            m_string_pool_size = reader.read_int() or 0
            m_pool_column_len = reader.read_int() or 0
            m_pool_offset_trunk_len = reader.read_int() or 0

                
            #print(f"[DEBUG] String pool: {self.m_pool_column_size} columns, {m_string_pool_size} strings")
            #print(f"[DEBUG] pool_column_len={m_pool_column_len}, pool_offset_len={m_pool_offset_trunk_len}")
            
            if m_string_pool_size > 100000 or m_pool_column_len > 10000 or m_pool_offset_trunk_len > 100000:
                print("[ERROR] String pool sizes look invalid, skipping")
                self.m_pool_column_size = 0
                return
            
            # Calculate positions
            pool_header_start = position + 4
            pool_header_end = pool_header_start + pool_head_length
            
            column_map_start = pool_header_end
            offset_array_start = column_map_start + m_pool_column_len
            
            self.m_pool_content_start_pos = 4 + pool_head_length + m_pool_column_len + m_pool_offset_trunk_len
            
            #print(f"[DEBUG] Reading column map from byte {column_map_start}")
            
            # Read column map
            self.m_column_map = {}
            reader.index = column_map_start
            
            for i in range(self.m_pool_column_size):
                if reader.index >= len(self.data):
                    print(f"[ERROR] Reached end of file reading column map at index {i}")
                    break
                column_index = reader.read_int() or 0
                self.m_column_map[column_index + 1] = True
                #print(f"[DEBUG]   String pool column {i}: index {column_index}")
            
            #print(f"[DEBUG] Reading offset array from byte {offset_array_start}")
            
            # Read offset array
            self.m_pool_offset_info_array = []
            reader.index = offset_array_start
            
            for i in range(m_string_pool_size):
                if reader.index >= len(self.data):
                    print(f"[ERROR] Reached end of file reading offset array at index {i}")
                    break
                offset = reader.read_int() or 0
                self.m_pool_offset_info_array.append(offset)
                if i < 5:
                    pass
                    #print(f"[DEBUG]   Offset {i}: {offset}")
            
            #print(f"[DEBUG] String pool initialized with {len(self.m_pool_offset_info_array)} offsets")
            
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to read string pool: {e}")
            traceback.print_exc()
            self.m_pool_column_size = 0
    
    def _has_complex_types(self):
        """Check if table has complex column types"""
        for col_type, _ in self.columns:
            if col_type in [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 19, 20, 21]:
                return True
        return False
    
    def _parse_with_reader(self, content):
        """Parse content using Reader (for tables with complex types)"""
        reader = Reader()
        reader.load_bytes(content)
        reader.set_binary_file_folder(self)
        
        col_types = [t for t, _ in self.columns]
        col_names = [n for _, n in self.columns]
        
        rows = []
        
        # Use explicit row count if available
        if self.row_count and self.row_count > 0 and self.row_count < 1_000_000:
            max_rows = self.row_count
            #print(f"[DEBUG] Using header row count: {max_rows}")
        else:
            max_rows = 100000
            #print(f"[DEBUG] No valid row count in header, using max: {max_rows}")
        
        consecutive_failures = 0
        
        # Detect columnar format
        is_columnar = self._detect_columnar_in_reader(reader, col_types)
        
        if is_columnar:
            #print("[DEBUG] Detected columnar format, skipping metadata")
            reader = self._skip_columnar_metadata(content, col_types)
        
        while reader.index < reader.len and len(rows) < max_rows:
            r = {}
            row_valid = True
            
            for col_idx, (ctype, cname) in enumerate(zip(col_types, col_names)):
                try:
                    reader.set_read_column(col_idx + 1)
                    value = reader.read(ctype)
                    
                    if cname in ("IsHiddenMode", "ShowTips", "IsHidden") and value == 0:
                        r[cname] = ""
                    else:
                        r[cname] = value
                        
                except Exception:
                    if len(rows) < 3:  # Show errors for first few rows
                        pass
                        #print(f"[DEBUG] Row {len(rows)} col {cname}: {e}")
                    row_valid = False
                    consecutive_failures += 1
                    break
            
            if not row_valid or consecutive_failures >= 3:
                #print(f"[DEBUG] Stopping at row {len(rows)} (consecutive failures: {consecutive_failures})")
                break
            
            if self.has_pk and 'Id' in col_names:
                if r.get('Id') is None and len(rows) >= 4:
                    #print(f"[DEBUG] Stopping at row {len(rows)} (None ID)")
                    break
            
            rows.append(r)
            consecutive_failures = 0
        
        self.rows = rows
    
    def _detect_columnar_in_reader(self, reader, col_types):
        """Check if data starts with columnar format"""
        start_pos = reader.index
        
        sample = []
        try:
            for _ in range(min(self.col_count, 10)):
                val = reader.read_uleb128()
                sample.append(val)
        except:  # noqa: E722
            pass
        
        reader.index = start_pos
        
        if len(sample) >= self.col_count:
            large_count = sum(1 for v in sample[:self.col_count] if v and v >= 10_000_000)
            return large_count >= self.col_count - 1
        
        return False
    
    def _skip_columnar_metadata(self, content, col_types):
        """Skip columnar metadata and return reader at row data start"""
        temp_reader = Reader()
        temp_reader.load_bytes(content)
        vals = temp_reader.read_all_uleb128()
        
        col_names = [n for _, n in self.columns]
        has_id = 'Id' in col_names
        
        for start in range(0, min(10000, len(vals) - self.col_count), self.col_count):
            row = vals[start:start + self.col_count]
            
            if has_id and row[0] is not None:
                id_val = row[0]
                if 1_000_000 <= id_val <= 4_000_000_000:
                    if len(row) > 1 and row[1] is not None and row[1] < 10_000_000:
                        new_reader = Reader()
                        new_reader.load_bytes(content)
                        new_reader.set_binary_file_folder(self)
                        
                        for _ in range(start):
                            new_reader.read_uleb128()
                        
                        return new_reader
        
        reader = Reader()
        reader.load_bytes(content)
        reader.set_binary_file_folder(self)
        return reader
    
    def _parse_with_varints(self, content):
        """Parse content using varint array (for simple types only)"""
        reader = Reader()
        reader.load_bytes(content)
        vals = reader.read_all_uleb128()
        
        #print(f"[DEBUG] Decoded {len(vals)} varints from content")
        #print(f"[DEBUG] Expected ~{self.row_count * self.col_count} varints for {self.row_count} rows × {self.col_count} cols")
        
        col_names = [name for _, name in self.columns]
        
        if self._is_columnar_format(vals):
            #print("[DEBUG] Detected columnar format")
            row_start = self._find_row_start(vals, col_names)
            #print(f"[DEBUG] Row data starts at varint index {row_start}")
            row_vals = vals[row_start:]
            #print(f"[DEBUG] Row values available: {len(row_vals)}")
            
            # Use header row count if available
            if self.row_count and self.row_count > 0:
                row_count = self.row_count
            else:
                row_count = len(row_vals) // self.col_count
            
            #print(f"[DEBUG] Will parse {row_count} rows")
            self.rows = self._parse_simple_rows(row_vals, row_count, col_names)
        else:
            #print("[DEBUG] Detected row format")
            # Use header row count if available
            if self.row_count and self.row_count > 0 and self.row_count < len(vals) // self.col_count:
                row_count = self.row_count
            else:
                row_count = self._find_valid_row_count(vals, col_names)
            
            #print(f"[DEBUG] Will parse {row_count} rows")
            self.rows = self._parse_simple_rows(vals, row_count, col_names)
        
        #print(f"[DEBUG] Actually parsed {len(self.rows)} rows")
    
    def _is_columnar_format(self, vals):
        """Check if data is in columnar format"""
        if len(vals) < self.col_count:
            return False
        
        first_row = vals[:self.col_count]
        large_count = sum(1 for v in first_row if v and v >= 10_000_000)
        
        return large_count >= self.col_count - 1
    
    def _find_row_start(self, vals, col_names):
        """Find where row data starts in columnar format"""
        has_id = 'Id' in col_names
        
        for start in range(0, min(10000, len(vals) - self.col_count), self.col_count):
            row = vals[start:start + self.col_count]
            
            if has_id and row[0] is not None:
                id_val = row[0]
                if not (1_000_000 <= id_val <= 4_000_000_000):
                    continue
                
                if len(row) > 1 and row[1] is not None:
                    if row[1] >= 10_000_000:
                        continue
            
            valid_streak = 0
            for i in range(min(10, (len(vals) - start) // self.col_count)):
                test_row = vals[start + i * self.col_count:start + (i + 1) * self.col_count]
                if len(test_row) != self.col_count:
                    break
                
                if test_row[0] is not None and 1_000_000 <= test_row[0] <= 4_000_000_000:
                    valid_streak += 1
                else:
                    break
            
            if valid_streak >= 10:
                return start
        
        return 0
    
    def _find_valid_row_count(self, vals, col_names):
        """Find valid row count for pure row format"""
        max_rows = len(vals) // self.col_count
        
        # If we have an explicit row count from the header and it's reasonable, use it
        if self.row_count and 0 < self.row_count <= max_rows:
            return self.row_count
        
        # Fallback: try to detect based on data patterns
        has_id = 'Id' in col_names and self.has_pk
        
        if has_id:
            # Only stop on None if we see it after many valid rows (likely garbage data)
            for row_idx in range(max_rows):
                start = row_idx * self.col_count
                if vals[start] is None and row_idx >= 10:  # Allow None in first 10 rows
                    # Check if most subsequent rows are also None (garbage data pattern)
                    none_count = 0
                    check_count = min(5, max_rows - row_idx)
                    for check_idx in range(row_idx, row_idx + check_count):
                        if vals[check_idx * self.col_count] is None:
                            none_count += 1
                    
                    if none_count >= 3:  # Multiple None IDs in a row = garbage
                        return row_idx
        
        return max_rows
    
    def _parse_simple_rows(self, vals, row_count, col_names):
        """Parse rows from varint array (simple types only)"""
        rows = []
        row_iter = iter(vals)
        
        for _ in range(row_count):
            r = {}
            for cname in col_names:
                v = next(row_iter, None)
                if cname in ("IsHiddenMode", "ShowTips", "IsHidden") and v == 0:
                    r[cname] = ""
                else:
                    r[cname] = v
            rows.append(r)
        
        return rows
    
    # String pool support methods
    def is_string_pool_column(self, column_index):
        """Check if column uses string pool"""
        if column_index < 0:
            return False
        if self.m_pool_column_size == -1:
            return False
        if self.m_pool_column_size <= 0:
            return False
        return self.m_column_map.get(column_index, False)
    
    def read_pool_string_by_index(self, index):
        """Read string from string pool by index"""
        if not self.m_pool_offset_info_array or len(self.m_pool_offset_info_array) == 0:
            return None
        
        lua_index = index + 1
        if lua_index > len(self.m_pool_offset_info_array):
            return None
        
        start_pos = 0 if index <= 0 else self.m_pool_offset_info_array[index - 1]
        end_pos = self.m_pool_offset_info_array[index]
        
        # Read string from pool content area
        pool_content_start = self.get_pool_content_trunk_start_position()
        string_start = pool_content_start + start_pos
        string_end = pool_content_start + end_pos
        
        if string_end > len(self.data):
            return None
        
        string_bytes = self.data[string_start:string_end]
        # Find null terminator
        null_pos = string_bytes.find(b'\x00')
        if null_pos >= 0:
            string_bytes = string_bytes[:null_pos]
        
        return string_bytes.decode('utf-8', errors='ignore')
    
    def get_column_names(self):
        return [name for _, name in self.columns]
    
    def get_rows(self):
        return self.rows
    
    def __repr__(self):
        return f"BinaryTable('{os.path.basename(self.filepath)}', cols={self.col_count}, rows={len(self.rows)})"