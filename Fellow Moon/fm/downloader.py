import hashlib
import json
import time
from pathlib import Path, PurePosixPath
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.exceptions import RequestException
import logging
import os 

log = logging.getLogger(__name__)


URL = "https://nm-common-proxy-live.garena.com/jsonMsgCheckSign"

HEADERS = {
    "User-Agent": "UnityPlayer/2020.3.48f1c1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
    "Accept": "*/*",
    "Accept-Encoding": "deflate, gzip",
    "X-Tpf-App-Id": "20019",
    "X-Tpf-Signature": "fd70d59c613e1238c4ff971ed94648d9",
    "Content-Type": "application/json",
    "X-Unity-Version": "2020.3.48f1c1",
}

GET_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "*/*",
    "Accept-Encoding": "deflate, gzip",
    "X-Unity-Version": HEADERS["X-Unity-Version"],
    "Range": "bytes=0-",
}

PAYLOAD = {
    "srcService": "client-update-service",
    "msgId": "getUpdateVersion",
    "msgContent": json.dumps(
        [
            {
                "appid": "20019",
                "regionId": "nm-jp-game",
                "channelId": "55",
                "resVersion": "56",
                "appVersion": "1.1.41",
                "userId": "",
                "adid": "0",
            }
        ],
        separators=(",", ":"),
    ),
}

HOTFIX_URL_TEMPLATE = (
    "https://dl-fellowmoon.garenanow.com/hotfix/{app_id}/Android/patch/VersionIndex/{latest_pkg}/"
)
ASSET_URL_TEMPLATE = (
    "https://dl-fellowmoon.garenanow.com/hotfix/{app_id}/Android/patch/SYResRoot/{path}"
)

APP_ID = "20019"


class Downloader:

    def __init__(self):
        pass

    # ---------------------------------------------------------------
    def post_payload(self) -> dict:
        body = json.dumps(PAYLOAD, separators=(",", ":"), ensure_ascii=False)
        resp = requests.post(URL, headers=HEADERS, data=body, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, resp_json: dict) -> dict:
        msg_content = resp_json.get("msgContent")
        try:
            inner = json.loads(msg_content) if isinstance(msg_content, str) else msg_content
            return inner or {}
        except Exception as e:
            log.info(f"[!] Failed to parse msgContent: {e}")
            return {}

    def build_hotfix_url(self, app_id: str, latest_pkg: str) -> str:
        return HOTFIX_URL_TEMPLATE.format(app_id=app_id, latest_pkg=latest_pkg)

    def build_asset_url(self, app_id: str, path: str) -> str:
        return ASSET_URL_TEMPLATE.format(app_id=app_id, path=path)

    def md5_of_file(self, path: Path, chunk_size=1 << 20) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()

    # ---------------------------------------------------------------
    def download_file(self, url: str, dest: Path, retries: int = 3, headers: dict | None = None, stop_event=None) -> bool:
        for attempt in range(1, retries + 1):
            if stop_event and stop_event.is_set():
                log.warning(f"[STOP] Aborting download of {dest.name}")
                return False
            try:
                with requests.get(url, stream=True, timeout=30, headers=headers or {}) as r:
                    r.raise_for_status()
                    tmp = dest.with_suffix(".part")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if stop_event and stop_event.is_set():
                                log.warning(f"[STOP] Interrupted during {dest.name}")
                                return False
                            if chunk:
                                f.write(chunk)
                    tmp.replace(dest)
                log.info(f"[OK] {dest.name}")
                return True
            except RequestException as e:
                log.error(f"[{attempt}/{retries}] failed: {dest.name} ({e})")
                time.sleep(attempt)
        return False


    def download_all(self, base_url: str, files: list[str], out_dir: Path, workers: int = 8):
        out_dir.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(self.download_file, base_url + name, out_dir / Path(name).name) for name in files]
            for fut in as_completed(futs):
                fut.result()

    # ---------------------------------------------------------------
    def main(self, download=True, workers=8, filter_str=None, stop_event=None, json_only=False):
        log.info("Posting update-check request...")

        if stop_event and stop_event.is_set():
            log.warning("Downloader aborted before start.")
            return

        resp_json = self.post_payload()
        mc = self.parse_response(resp_json)
        log.info("Response OK: %s  code: %s", resp_json.get("msg"), resp_json.get("code"))

        latest_pkg = mc.get("latestPackageName")
        subfiles = mc.get("subFiles") or []
        log.info(f"Latest package: {latest_pkg}")
        log.info(f"SubFiles count: {len(subfiles)}")

        if not latest_pkg or not subfiles:
            log.info("[!] No update info found, aborting.")
            return

        base_url = self.build_hotfix_url(APP_ID, latest_pkg)
        log.info(f"Using fixed HOTFIX URL:\n  {base_url}")

        version_dir = Path("downloads") / "version_index" / latest_pkg

        if filter_str:
            subfiles = [s for s in subfiles if filter_str in s]
            log.info(f"[Filter] Keeping {len(subfiles)} subfiles matching '{filter_str}'")

       # --- Subfile download phase ---
        if download:
            valid_subfiles = []

            for name in subfiles:
                if stop_event and stop_event.is_set():
                    log.warning("User requested stop — aborting subfile scan.")
                    break

                local_path = version_dir / Path(name).name

                # Extract md5 and size if embedded in name (..._md5_size)
                parts = name.split("_")
                md5_expect = None
                size_expect = None
                if len(parts) >= 3:
                    md5_expect = parts[-2]
                    try:
                        size_expect = int(parts[-1])
                    except ValueError:
                        pass

                # --- Check existing file ---
                if local_path.exists():
                    try:
                        if md5_expect:
                            got = self.md5_of_file(local_path)
                            if got.lower() == md5_expect.lower():
                                log.info(f"[SKIP] {local_path.name} (MD5 match)")
                                continue

                        if size_expect and local_path.stat().st_size == size_expect:
                            log.info(f"[SKIP] {local_path.name} (size match)")
                            continue
                    except Exception as e:
                        log.warning(f"[WARN] Could not verify {local_path.name}: {e}")

                valid_subfiles.append(name)

            if not valid_subfiles:
                log.info("All subfiles are up-to-date. Skipping download.")
            else:
                log.info(f"Downloading {len(valid_subfiles)} new or changed subfiles...")
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futs = [
                        ex.submit(
                            self.download_file,
                            base_url + name,
                            version_dir / Path(name).name,
                            3,
                            None,
                            stop_event,
                        )
                        for name in valid_subfiles
                    ]
                    for fut in as_completed(futs):
                        if stop_event and stop_event.is_set():
                            log.warning("User requested stop — cancelling pending subfile downloads.")
                            break
                        fut.result()
        else:
            log.info("Skipping subfile download (--download not used).")


        if json_only:
            log.info("JSON-only mode enabled — skipping asset downloads.")
            return

        if stop_event and stop_event.is_set():
            log.warning("Download aborted after subfile phase.")
            return

        # --- Parse JSONs ---
        asset_entries = []
        json_files = list(version_dir.glob("*.json*"))
        if filter_str:
            json_files = [f for f in json_files if filter_str in f.name]
            log.info(f"[Filter] Parsing only {len(json_files)} JSON files matching '{filter_str}'")

        for json_file in json_files:
            if stop_event and stop_event.is_set():
                log.warning("Aborted before JSON parse finished.")
                return
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    asset_entries.extend(data)
            except Exception as e:
                log.info(f"[WARN] Failed to parse {json_file}: {e}")

        if not asset_entries:
            log.info("[!] No asset entries found; maybe subfiles not downloaded yet.")
            return

        log.info(f"Found {len(asset_entries)} asset entries.")
        asset_root = Path("downloads") / "assets" / latest_pkg

        def download_and_verify(entry):
            if stop_event and stop_event.is_set():
                return False

            path = entry.get("filePath") or ""
            md5_expect = (entry.get("md5") or "").lower()
            size = entry.get("size")

            posix_path = path.replace("\\", "/")
            pp = PurePosixPath(posix_path)

            remote_rel = f"{pp.as_posix()}_{md5_expect}" if md5_expect else pp.as_posix()
            remote_url = self.build_asset_url(APP_ID, remote_rel)

            local_name = f"{pp.name}" if md5_expect else pp.name
            rel_path = Path(*pp.parts[:-1]) / local_name
            dest = asset_root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            for attempt in range(1, 4):
                if stop_event and stop_event.is_set():
                    return False

                ok = self.download_file(remote_url, dest, headers=GET_HEADERS, stop_event=stop_event)
                if not ok:
                    continue

                if md5_expect:
                    got = self.md5_of_file(dest)
                    if got.lower() != md5_expect:
                        log.warn(f"[MD5 mismatch] {rel_path} ({got} != {md5_expect})")
                        try:
                            dest.unlink()
                        except Exception:
                            pass
                        time.sleep(attempt)
                        continue

                if size and dest.exists() and dest.stat().st_size != int(size):
                    log.error(f"[SIZE mismatch] {rel_path} (expected {size}, got {dest.stat().st_size})")
                return True
            return False

        log.info("Downloading assets...")
        completed = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(download_and_verify, e) for e in asset_entries]
            for fut in as_completed(futs):
                if stop_event and stop_event.is_set():
                    log.warning("User requested stop — cancelling asset downloads.")
                    break
                fut.result()
                completed += 1
                if completed % 25 == 0:
                    log.info(f"Progress: {completed}/{len(asset_entries)}")

        if stop_event and stop_event.is_set():
            log.warning(f"Aborted early — downloaded {completed}/{len(asset_entries)} assets.")
            return

        log.info(f"All done! Assets stored under: {asset_root.resolve()}")


    def download_proto(
        self,
        file_path="AssetBundles/25/d_1890480325.ab",
        out_dir=Path("downloads/proto"),
        stop_event=None,
    ):

        try:
            # 1) Get latest package via the signed update flow you already use
            log.info("Posting update-check request for proto...")
            resp_json = self.post_payload()
            mc = self.parse_response(resp_json)

            latest_pkg = mc.get("latestPackageName")
            subfiles = mc.get("subFiles") or []  # list of strings
            if not latest_pkg or not subfiles:
                log.warning("No update info found; aborting proto download.")
                return

            base_url = self.build_hotfix_url(APP_ID, latest_pkg)
            version_dir = Path("downloads") / "version_index" / latest_pkg
            version_dir.mkdir(parents=True, exist_ok=True)

            # 2) Make sure VersionIndex JSONs are present locally
            #    If the directory is empty, download the subfiles (the JSON lists)
            existing_jsons = list(version_dir.glob("*.json*"))
            if not existing_jsons:
                log.info("Index JSONs not found locally — downloading index files...")
                if stop_event and stop_event.is_set():
                    log.warning("User aborted before index download.")
                    return

                # Download all subfiles (these are the index JSONs)
                self.download_all(base_url, subfiles, version_dir, workers=4)
                existing_jsons = list(version_dir.glob("*.json*"))

            if not existing_jsons:
                log.warning("No index JSONs available after download; aborting.")
                return

            # 3) Scan all index JSONs to find our proto entry (filePath == target)
            target = PurePosixPath(file_path).as_posix()  # normalize
            found = None
            for jf in existing_jsons:
                if stop_event and stop_event.is_set():
                    log.warning("User aborted during index scan.")
                    return
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        for entry in data:
                            # Expect dicts like {"filePath": "...", "md5": "...", "size": ...}
                            if isinstance(entry, dict) and entry.get("filePath") == target:
                                found = entry
                                break
                    # Some files may not be lists; just skip those
                except Exception as e:
                    log.info(f"[WARN] Failed to parse {jf.name}: {e}")
                if found:
                    break

            if not found:
                log.warning(f"Proto path not found in index JSONs: {target}")
                return

            md5_expect = (found.get("md5") or "").lower()
            size_expect = found.get("size")
            if not md5_expect:
                log.warning(f"Entry found but no MD5 present for {target}; aborting.")
                return

            # 4) Build the SYResRoot URL with MD5 suffix and download
            asset_rel = f"{target}_{md5_expect}"  # append md5
            asset_url = self.build_asset_url(APP_ID, asset_rel)  # uses ASSET_URL_TEMPLATE
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            dest = out_dir / os.path.basename(target)  # clean name without _md5 suffix

            # Skip if up-to-date
            if dest.exists():
                got = self.md5_of_file(dest)
                if got.lower() == md5_expect:
                    log.info(f"[SKIP] {dest.name} (MD5 match)")
                    return
                else:
                    log.info(f"[RE-DOWNLOAD] {dest.name} (MD5 {got} != {md5_expect})")

            log.info(f"Downloading proto → {dest}  (size={size_expect}, md5={md5_expect})")
            with requests.get(asset_url, headers=GET_HEADERS, stream=True, timeout=20) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if stop_event and stop_event.is_set():
                            log.warning("User aborted proto download.")
                            return
                        if chunk:
                            f.write(chunk)
                tmp.replace(dest)

            # 5) Verify MD5
            got = self.md5_of_file(dest)
            if got.lower() == md5_expect:
                log.info(f"[OK] Proto verified successfully: {dest.name}")
            else:
                log.warning(f"[MD5 mismatch] {dest.name} ({got} != {md5_expect})")

        except Exception as e:
            log.exception(f"Proto download failed: {e}")

