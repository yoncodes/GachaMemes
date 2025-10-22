import os
from hashlib import sha1
from Crypto.Cipher import AES
from Crypto.Util import Counter
import logging

log = logging.getLogger(__name__)

class Asset:
    def __init__(self):
        self.aes = AES
        self.count = Counter
        self.sha1 = sha1

    def getkey(self, password, salt, keylen, count):
        index, count = 1, count - 1
        hashval = self.sha1((password.encode('utf-8') if isinstance(password, str) else password) + salt).digest()
        for _ in range(count - 1):
            hashval = self.sha1(hashval).digest()
        hashder = self.sha1(hashval).digest()
        while len(hashder) < keylen:
            hashder += self.sha1(bytes([index + 48]) + hashval).digest()
            index += 1
        return hashder[:keylen]

    def decrypt(self, data, password, salt, keylen=16, count=100):
        return self.aes.new(
            self.getkey(password, salt, keylen, count),
            self.aes.MODE_CTR,
            counter=self.count.new(64, suffix=b'\x00' * 8, little_endian=True)
        ).decrypt(data)

    def batch_decode(self, base_path, out_dir="decrypted_bundles", stop_event=None):
        """
        Recursively decrypt .ab bundle files with optional stop_event cancellation.
        """
        count = 0

        if not os.path.isdir(out_dir):
            os.mkdir(out_dir)

        for root, _, files in os.walk(base_path):
            for name in files:

                # --- check for cancellation before processing each file ---
                if stop_event and stop_event.is_set():
                    log.warning("Bundle decryption aborted by user.")
                    log.info(f"Processed {count} files before stop request.")
                    return count

                # --- only decrypt .ab bundles ---
                if not name.lower().endswith(".ab"):
                    continue

                src_path = os.path.join(root, name)
                rel_path = os.path.relpath(src_path, base_path)
                dst_path = os.path.join(out_dir, rel_path)

                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                log.info(f"Decrypting {rel_path}...")

                try:
                    with open(src_path, "rb") as f:
                        file_content = f.read()

                    data = self.decrypt(
                        file_content,
                        "System.Byte[]",
                        name.replace(".ab", "").encode(),
                        32,
                        100,
                    )

                    with open(dst_path, "wb") as f:
                        f.write(data)

                    count += 1

                except Exception as e:
                    log.error(f"[!] Failed to decrypt {rel_path}: {e}")

        log.info(f"Finished decrypting {count} .ab files in {base_path}.")
        return count



