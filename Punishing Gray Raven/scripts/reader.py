import struct
from typing import Optional, List, Dict, Any

class Reader:
    def __init__(self):
        self.bytes: Optional[bytes] = None
        self.len: int = 0
        self.index: int = 0
        self.m_is_using_string_pool: bool = False
        self.m_binary_file_folder = None
        
        self.MAX_INT32 = 2147483647
        
        # Type dispatch table
        self.read_by_type = {
            1: self.read_bool,
            2: self.read_string,
            3: self.read_fix,
            4: self.read_list_string,
            5: self.read_list_bool,
            6: self.read_list_int,
            7: self.read_list_float,
            8: self.read_list_fix,
            9: self.read_dic_string_string,
            10: self.read_dic_int_int,
            11: self.read_dic_int_string,
            12: self.read_dic_string_int,
            13: self.read_dic_int_float,
            14: self.read_int,
            15: self.read_float,
            16: self.read_fix2,
            17: self.read_fix3,
            18: self.read_fix_quaternion,
            19: self.read_list_fix2,
            20: self.read_list_fix3,
            21: self.read_list_fix_quaternion,
        }
    
    def reset(self, length: int, index: int = 0):
        self.len = length
        self.index = index
    
    def load_bytes(self, data: bytes, length: int = None, index: int = 0):
        self.bytes = data
        self.reset(length or len(data), index)
    
    def set_read_column(self, column):
        if self.m_binary_file_folder:
            self.m_is_using_string_pool = self.m_binary_file_folder.is_string_pool_column(column)
    
    def set_binary_file_folder(self, folder):
        self.m_binary_file_folder = folder
    
    def close(self):
        self.m_is_using_string_pool = False
        self.m_binary_file_folder = None
        self.bytes = None
    
    def read(self, type_id: int) -> Any:
        """Dispatch to appropriate reader based on type ID"""
        return self.read_by_type[type_id]()  # Call the bound method
    
    def set_index(self, value: int):
        self.index = value
    
    def get_index(self) -> int:
        return self.index

    def read_u8(self) -> Optional[int]:
        """Read unsigned byte"""
        if self.index >= self.len:
            return None
        val = self.bytes[self.index]
        self.index += 1
        return val
    
    def read_u32_le(self) -> Optional[int]:
        """Read 4-byte little-endian unsigned int"""
        if self.index + 4 > self.len:
            return None
        val = struct.unpack_from("<I", self.bytes, self.index)[0]
        self.index += 4
        return val
    
    def read_cstr(self) -> Optional[str]:
        """Read null-terminated C string"""
        if self.index >= self.len:
            return None
        
        start = self.index
        while self.index < self.len and self.bytes[self.index] != 0:
            self.index += 1
        
        if self.index >= self.len:
            return None
        
        result = self.bytes[start:self.index].decode('utf-8', errors='ignore')
        self.index += 1  # Skip null terminator
        return result
    

    
    def read_uleb128(self) -> Optional[int]:
        """Read a single unsigned LEB128 integer, return None if value is 0"""
        if self.index >= self.len:
            return None
        
        value = 0
        shift = 0
        
        while self.index < self.len:
            b = self.bytes[self.index]
            self.index += 1
            
            value |= (b & 0x7F) << shift
            
            if (b >> 7) == 0:
                break
            
            shift += 7
        
        return None if value == 0 else value
    
    def read_all_uleb128(self) -> List[Optional[int]]:
        """Read all remaining varints from current position"""
        vals = []
        while self.index < self.len:
            v = self.read_uleb128()
            vals.append(v)
        return vals
    
    def read_sleb128(self) -> Optional[int]:
        """Read a signed LEB128 integer (with sign handling)"""
        value = self.read_uleb128()
        
        if value is None:
            return None
        
        # Handle negative numbers (original Lua logic)
        if value > self.MAX_INT32:
            value = -(((~value) & self.MAX_INT32) + 1)
        
        return value
    
    def read_int64_variant(self) -> Optional[int]:
        """Read 64-bit unsigned LEB128 (no negative handling)"""
        if self.index >= self.len:
            return None
        
        value = 0
        shift = 0
        
        while self.index < self.len:
            b = self.bytes[self.index]
            self.index += 1
            
            value |= (b & 0x7F) << shift
            
            if (b >> 7) == 0:
                break
            
            shift += 7
        
        return None if value == 0 else value
    
    def read_int(self) -> Optional[int]:
        """Read signed variant integer"""
        return self.read_sleb128()
    
    def read_int32_variant(self) -> Optional[int]:
        """Alias for read_int"""
        return self.read_sleb128()
    
    def read_uint32_variant(self) -> Optional[int]:
        """Read unsigned variant integer"""
        return self.read_sleb128()
    

    
    def read_float(self) -> Optional[float]:
        """Read float encoded as int / 10000"""
        num = self.read_int()
        if num is None:
            return None
        
        num = num / 10000.0
        
        # Remove trailing zeros from decimal
        if num == int(num):
            num = float(int(num))
        
        return num
    
    def read_bool(self) -> Optional[bool]:
        if self.index >= self.len:
            return None
        
        value = self.bytes[self.index]
        self.index += 1
        return True if value == 1 else None
    
    def read_string(self) -> Optional[str]:
        """Read null-terminated string or string pool reference"""
        if self.m_is_using_string_pool:
            # Read index into string pool
            index = self.read_int() or 0
            if self.m_binary_file_folder:
                return self.m_binary_file_folder.read_pool_string_by_index(index)
            return None
        
        position = self.index
        
        if position >= self.len:
            return None
        
        # Find null terminator
        try:
            null_pos = self.bytes.index(b'\x00', position)
        except ValueError:
            return None
        
        if null_pos == position:
            self.index += 1
            return None
        
        value = self.bytes[position:null_pos].decode('utf-8', errors='ignore')
        self.index = null_pos + 1
        
        return value
    
    def read_int_fix(self) -> int:
        """Fixed 4-byte integer (little-endian)"""
        if self.index + 4 > self.len:
            return 0
        
        b1, b2, b3, b4 = self.bytes[self.index:self.index+4]
        self.index += 4
        return b1 | (b2 << 8) | (b3 << 16) | (b4 << 24)
    

    
    def read_list_string(self) -> Optional[List[str]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_string() for _ in range(length)]
    
    def read_list_bool(self) -> Optional[List[bool]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_bool() for _ in range(length)]
    
    def read_list_int(self) -> Optional[List[int]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_int() or 0 for _ in range(length)]
    
    def read_list_float(self) -> Optional[List[float]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_float() or 0.0 for _ in range(length)]
    
    
    def read_dic_string_string(self) -> Optional[Dict[str, str]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        result = {}
        for _ in range(length):
            key = self.read_string()
            value = self.read_string()
            result[key] = value
        
        return result
    
    def read_dic_int_int(self) -> Optional[Dict[int, int]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        result = {}
        for _ in range(length):
            key = self.read_int() or 0
            value = self.read_int() or 0
            result[key] = value
        
        return result
    
    def read_dic_int_string(self) -> Optional[Dict[int, str]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        result = {}
        for _ in range(length):
            key = self.read_int() or 0
            value = self.read_string()
            result[key] = value
        
        return result
    
    def read_dic_string_int(self) -> Optional[Dict[str, int]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        result = {}
        for _ in range(length):
            key = self.read_string()
            value = self.read_int()
            result[key] = value
        
        return result
    
    def read_dic_int_float(self) -> Optional[Dict[int, float]]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        result = {}
        for _ in range(length):
            key = self.read_int() or 0
            value = self.read_float()
            result[key] = value
        
        return result
    
    
    def read_fix(self) -> Optional[Any]:
        """Read fixed-point number"""
        value = self.read_int64_variant() or 0
        exp = 0
        
        if value != 0:
            if self.index >= self.len:
                return None
            
            combined_byte = self.bytes[self.index]
            self.index += 1
            exp = combined_byte & 0x7F
            negative = combined_byte >> 7
            
            if negative == 1:
                value = -value
        
        return self.fix_parse_ex(value, exp)
    
    def fix_parse_ex(self, value: int, exp: int) -> Any:
        """Fixed-point parsing logic"""
        return value / (10 ** exp) if exp > 0 else value
    
    def read_list_fix(self) -> Optional[List]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_fix() for _ in range(length)]
    
    def read_fix2(self) -> Optional[Dict]:
        """Read 2D fixed-point vector"""
        return {
            'x': self.read_fix(),
            'y': self.read_fix()
        }
    
    def read_list_fix2(self) -> Optional[List]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_fix2() for _ in range(length)]
    
    def read_fix3(self) -> Optional[Dict]:
        """Read 3D fixed-point vector"""
        return {
            'x': self.read_fix(),
            'y': self.read_fix(),
            'z': self.read_fix()
        }
    
    def read_list_fix3(self) -> Optional[List]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_fix3() for _ in range(length)]
    
    def read_fix_quaternion(self) -> Optional[Dict]:
        """Read quaternion with fixed-point components"""
        return {
            'x': self.read_fix() or 0,
            'y': self.read_fix() or 0,
            'z': self.read_fix() or 0,
            'w': self.read_fix() or 0
        }
    
    def read_list_fix_quaternion(self) -> Optional[List]:
        length = self.read_int()
        if not length or length <= 0:
            return None
        
        return [self.read_fix_quaternion() for _ in range(length)]