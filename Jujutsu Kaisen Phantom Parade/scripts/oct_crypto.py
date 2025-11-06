import json
import importlib.util
import hashlib
import logging
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

logger = logging.getLogger("jjk")

#decrypts the octocacheevai file
class OctoCacheFile:

    KEY_STRING = "0cq59tmfo3y0hjnf"
    IV_STRING = "LvAUtf+tnz"
    KEY = hashlib.md5(KEY_STRING.encode()).digest()
    IV = hashlib.md5(IV_STRING.encode()).digest()

    @classmethod
    def _load_proto(cls):

        possible_paths = [
            Path(__file__).parent.parent / "JJK_pb2.py",
            Path.cwd() / "JJK_pb2.py",
        ]

        for path in possible_paths:
            if path.exists():
                spec = importlib.util.spec_from_file_location("JJK_pb2", path)
                jjk_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(jjk_mod)
                return jjk_mod, None

        return None, f"JJK_pb2.py not found in {possible_paths}"

    @classmethod
    def decrypt_file(cls, input_path, output_dir="octocache"):

        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        data = input_path.read_bytes()
        if not data or data[0] != 0x01:
            raise ValueError(f"Invalid OctoCache header in {input_path.name}")

        cipher = AES.new(cls.KEY, AES.MODE_CBC, cls.IV)
        decrypted = unpad(cipher.decrypt(data[1:]), 16)[16:]  # skip checksum header

        raw_out_path = output_dir / f"{input_path.stem}_dec"
        raw_out_path.write_bytes(decrypted)
        logger.info(f"✓ Saved raw decrypted data → {raw_out_path}")

        try:
            jjk_mod, err = cls._load_proto()
            if not jjk_mod:
                raise FileNotFoundError(err)

            from google.protobuf.json_format import MessageToDict

            db = jjk_mod.Database()
            db.ParseFromString(decrypted)
            data_dict = MessageToDict(db, preserving_proto_field_name=True)

            # Decide output name
            if len(db.assetBundleList) > 0:
                filename = "Database.json"
            else:
                filename = "AssetManifest.json"

            out_path = output_dir / filename
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ Parsed protobuf successfully → {out_path}")
            logger.info(f"Revision: {db.revision}")
            logger.info(f"Assets: {len(db.assetBundleList)} | Resources: {len(db.resourceList)}")
            logger.info(f"URL: {db.urlFormat}")

        except Exception as e:
            logger.warning(f"Protobuf parse failed ({e}) — JSON not saved.")

        return raw_out_path
