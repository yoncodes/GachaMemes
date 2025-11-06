import json
import traceback
import base64 
import gzip
import zlib
import logging
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA1

logger = logging.getLogger(__name__)

#decrypts the MasterData and ClientMasterData files
#Hook Ghost.Common.GhostCryptographyProcessor to get the keys
class SaveCrypto:
    PASSWORD = "hogehoge"
    SALT = "hogehoge"

    @classmethod
    def _generate_keys(cls):
        derived = PBKDF2(
            cls.PASSWORD.encode(),
            cls.SALT.encode(),
            dkLen=48,
            count=1000,
            hmac_hash_module=SHA1,
        )
        return derived[0:32], derived[32:48]

    @classmethod
    def decrypt(cls, data: bytes) -> bytes:
        key, iv = cls._generate_keys()
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(data), 16)

    @staticmethod
    def _try_decode_layers(data: bytes) -> bytes:
        """Try Base64 → gzip/deflate decoding automatically."""
        try:
            if all(32 <= b <= 126 for b in data[:64]):
                b64 = base64.b64decode(data, validate=True)
                try:
                    return gzip.decompress(b64)
                except OSError:
                    return zlib.decompress(b64)
        except Exception:
            pass
        if data[:2] == b"\x1f\x8b":
            try:
                return gzip.decompress(data)
            except Exception:
                pass
        return data

    @classmethod
    def batch_decrypt(cls, input_dir: str, output_dir: str):
        """Decrypt .data files; split only non-ResumeData JSONs with multiple top-level arrays."""
        in_path = Path(input_dir)
        out_path = Path(output_dir)

        if not in_path.exists():
            logger.error(f"✗ Input directory not found: {in_path}")
            return

        files = list(in_path.rglob("*.data"))
        logger.info(f"Found {len(files)} .data files to decrypt")
        logger.info("=" * 70)

        success = failed = split_count = 0

        for file_path in files:
            rel = file_path.relative_to(in_path)
            try:
                raw = file_path.read_bytes()
                dec = cls.decrypt(raw)
                dec = cls._try_decode_layers(dec)

                json_obj = None
                if dec[:1] in (b"{", b"["):
                    try:
                        json_obj = json.loads(dec.decode("utf-8"))
                    except Exception:
                        pass

                # Skip splitting for ResumeData
                if "ResumeData" in str(rel):
                    out_file = out_path / rel.with_suffix(".json")
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    if json_obj is not None:
                        out_file.write_text(
                            json.dumps(json_obj, indent=2, ensure_ascii=False),
                            encoding="utf-8"
                        )
                    else:
                        out_file.write_bytes(dec)
                    logger.info(f"✓ {rel} → {out_file.relative_to(out_path)}")
                    success += 1
                    continue

                # Normal path: split top-level arrays
                if isinstance(json_obj, dict):
                    local_splits = 0
                    for key, val in json_obj.items():
                        out_file = out_path / rel.parent / f"{key}.json"
                        out_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(out_file, "w", encoding="utf-8") as f:
                            json.dump(val, f, indent=2, ensure_ascii=False)
                        logger.info(f"✓ {rel} → {key}.json")
                        local_splits += 1
                    split_count += local_splits
                    success += 1
                else:
                    # fallback single file
                    out_file = out_path / rel.with_suffix(".json")
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_bytes(dec)
                    logger.info(f"✓ {rel} → {out_file.relative_to(out_path)}")
                    success += 1

            except Exception as e:
                failed += 1
                logger.error(f"✗ {rel} - {e}")
                logger.debug(traceback.format_exc(limit=1))

        logger.info("=" * 70)
        logger.info(f"Success: {success} | Failed: {failed} | Total: {len(files)} | Split files: {split_count}")
