
import struct
import gzip
import zlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class CustomDecryptor:
    """Handles the custom encryption format starting with 22 4A 67"""
    
    def __init__(self):
        self.mIV = bytes.fromhex('00000000000000000000000000000000')
        self.mRawKeys = bytes.fromhex('9964b1b06b038d7fb77db6a754908b73')
    
    @staticmethod
    def get_str_upper_hash(in_asset_name):
        if not in_asset_name:
            return 0
        
        hash_val = 0
        for char in in_asset_name:
            char_code = ord(char)
            if 97 <= char_code <= 122:
                char_code -= 32
            hash_val = (31 * hash_val + char_code) & 0xFFFFFFFF
        
        return hash_val
    
    def get_mixed_key(self, res_name):
        hash_val = self.get_str_upper_hash(res_name)
        mixed_key = bytearray(self.mRawKeys)
        hash_bytes = struct.pack('<I', hash_val)
        
        for i in range(len(mixed_key)):
            hash_byte_index = i % 4
            mixed_key[i] ^= hash_bytes[hash_byte_index]
        
        return bytes(mixed_key)
    
    def decrypt_custom_format(self, encrypted_data, resource_name):
        try:
            if len(encrypted_data) < 4:
                return None
            
            if encrypted_data[0] != 0x22 or encrypted_data[1] != 0x4A or encrypted_data[2] != 0x67:
                return None
            
            flag = encrypted_data[3]
            mixed_key = self.get_mixed_key(resource_name)
            cipher = AES.new(mixed_key, AES.MODE_CBC, self.mIV)
            decrypted = cipher.decrypt(encrypted_data[4:])
            
            try:
                decrypted = unpad(decrypted, AES.block_size)
            except:  # noqa: E722
                pass
            
            if len(decrypted) < 4:
                return None
            
            stored_hash = struct.unpack('<I', decrypted[0:4])[0]
            if stored_hash >= 0x80000000:
                stored_hash -= 0x100000000
            
            calculated_hash = self.get_hash_code(decrypted, 4, len(decrypted) - 4)
            
            if stored_hash != calculated_hash:
                result = decrypted
            else:
                result = decrypted[4:]
            
            if flag == self.mRawKeys[2]:
                result = self.uncompress_data(result)
            
            return result
            
        except Exception:
            return None
    
    @staticmethod
    def get_hash_code(in_data, in_pos, in_len):
        hash_val = 0
        for i in range(in_pos, min(in_pos + in_len, len(in_data))):
            hash_val = ((hash_val << 5) - hash_val + in_data[i]) & 0xFFFFFFFF
        
        if hash_val >= 0x80000000:
            hash_val -= 0x100000000
        
        return hash_val
    
    @staticmethod
    def uncompress_data(compressed_data):
        try:
            if len(compressed_data) >= 2 and compressed_data[0] == 31 and compressed_data[1] == 139:
                return gzip.decompress(compressed_data)
            else:
                decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                return decompressor.decompress(compressed_data)
        except:  # noqa: E722
            return compressed_data
