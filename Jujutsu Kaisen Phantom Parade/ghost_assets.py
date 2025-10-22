from Crypto.Cipher import AES

#decrypts the asset files # method found in 
#Ghost.AssetSystem.AssetBundle.GhostCryptManager
class GhostAssets:
    # AES key for counter stream encryption
    AES_KEY = b"6154e00f9E9ce46dc9054E07173Aa546"
    
    @classmethod
    def can_decrypt(cls, data):

        if len(data) < 16:
            return False
        
        try:
            header_key = data[0:2]
            encrypted_signature = data[2:15]
            
            signature_bytes = bytearray(encrypted_signature)
            for i in range(13):
                signature_bytes[i] ^= header_key[i % 2]
            
            signature = signature_bytes.decode('utf-8')
            return signature == "_GhostAssets_"
        except:  # noqa: E722
            return False
    
    @classmethod
    def decrypt(cls, data):

        if len(data) < 16:
            raise ValueError("File too small")
        
        # Read and verify header
        header_key = data[0:2]
        encrypted_signature = data[2:15]
        encrypted_generation = data[15]
        
        # XOR decrypt signature
        signature_bytes = bytearray(encrypted_signature)
        for i in range(13):
            signature_bytes[i] ^= header_key[i % 2]
        
        signature = signature_bytes.decode('utf-8')
        if signature != "_GhostAssets_":
            raise ValueError(f"Invalid signature: {signature}")
        
        # XOR decrypt generation
        generation = encrypted_generation ^ (header_key[0] ^ header_key[1])
        if generation != 1:
            raise ValueError(f"Unsupported generation: {generation}")
        
        # Get encrypted data (skip 16-byte header)
        encrypted_data = data[0x10:]
        
        # Generate counter stream
        block_count = len(encrypted_data) // 0x10
        counter_stream = bytearray()
        value = 0
        
        for i in range(block_count + 1):
            if i % 0x40 == 0:
                value = 0x64 * ((i // 0x40) + 1)
            
            # Write as little-endian 64-bit + 8 zero bytes
            counter_stream.extend(value.to_bytes(8, 'little'))
            counter_stream.extend(b'\x00' * 8)
            value += 1
        
        # Encrypt counter stream with AES-256-ECB to generate XOR key
        cipher = AES.new(cls.AES_KEY, AES.MODE_ECB)
        xor_key = cipher.encrypt(bytes(counter_stream))
        
        # XOR decrypt the data
        decrypted = bytearray(encrypted_data)
        for i in range(len(decrypted)):
            decrypted[i] ^= xor_key[i]
        
        return bytes(decrypted)
    
    @classmethod
    def encrypt(cls, data, header_key=None):

        import os
        
        if header_key is None:
            header_key = os.urandom(2)
        elif len(header_key) != 2:
            raise ValueError("Header key must be 2 bytes")
        
        # Generate counter stream
        block_count = len(data) // 0x10
        counter_stream = bytearray()
        value = 0
        
        for i in range(block_count + 1):
            if i % 0x40 == 0:
                value = 0x64 * ((i // 0x40) + 1)
            
            counter_stream.extend(value.to_bytes(8, 'little'))
            counter_stream.extend(b'\x00' * 8)
            value += 1
        
        # Encrypt counter stream with AES-256-ECB
        cipher = AES.new(cls.AES_KEY, AES.MODE_ECB)
        xor_key = cipher.encrypt(bytes(counter_stream))
        
        # XOR encrypt the data
        encrypted_data = bytearray(data)
        for i in range(len(encrypted_data)):
            encrypted_data[i] ^= xor_key[i]
        
        # Build header
        signature = b"_GhostAssets_"
        generation = 1
        
        # XOR encrypt signature
        encrypted_signature = bytearray(signature)
        for i in range(13):
            encrypted_signature[i] ^= header_key[i % 2]
        
        # XOR encrypt generation
        encrypted_generation = generation ^ (header_key[0] ^ header_key[1])
        
        # Combine header + encrypted data
        result = bytearray()
        result.extend(header_key)
        result.extend(encrypted_signature)
        result.append(encrypted_generation)
        result.extend(encrypted_data)
        
        return bytes(result)