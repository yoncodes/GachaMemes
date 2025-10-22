import json
import base64
from typing import Tuple
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Can be found in Ghost.Api.WebRequestHelper class
# Static AES-256 key (32 bytes)
key = bytes([
    34, 172, 175, 193, 121, 131, 83, 33,
    34, 54, 167, 156, 137, 63, 244, 195,
    54, 64, 92, 75, 145, 41, 11, 164,
    65, 216, 163, 192, 136, 20, 31, 80
])

def decrypt_json_wrapped(json_str: str) -> Tuple[str, str]:
    """
    Decrypts a base64-wrapped JSON object containing {"iv": "...", "value": "..."}
    """
    obj = json.loads(json_str)
    iv = base64.b64decode(obj["iv"])
    ciphertext = base64.b64decode(obj["value"])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")
    return plaintext, iv.hex()

def decrypt_embedded_iv(raw: bytes) -> Tuple[str, str]:
    """
    Decrypts data where the first 16 bytes are the IV and the rest is ciphertext.
    """
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")
    return plaintext, iv.hex()

def decrypt_any(base64_input: str) -> Tuple[str, str]:
    """
    Detects and decrypts input as either JSON-wrapped or embedded-IV format.
    """
    raw = base64.b64decode(base64_input)
    print("Raw first 32 bytes (hex):", " ".join(f"{b:02x}" for b in raw[:32]))
    print("Raw length:", len(raw))

    # Attempt to decode as JSON-wrapped format
    try:
        json_str = raw.decode("utf-8")
        if json_str.strip().startswith("{"):
            plaintext, iv_hex = decrypt_json_wrapped(json_str)
            print(f"[✓] Decrypted JSON-wrapped data with IV: {iv_hex}")
            return plaintext, iv_hex
    except Exception as e:
        print(f"[!] Not JSON-wrapped: {e}")

    # Fallback to embedded-IV format
    plaintext, iv_hex = decrypt_embedded_iv(raw)
    print(f"[✓] Decrypted embedded-IV format with IV: {iv_hex}")
    return plaintext, iv_hex

if __name__ == "__main__":
    input_str = ""

    try:
        plaintext, iv_hex = decrypt_any(input_str)
        print(f"\n[✓] IV: {iv_hex}")
        print("[✓] Decrypted output:\n")
        print(plaintext)
    except Exception as e:
        print(f"\n× Decryption failed: {e}")


