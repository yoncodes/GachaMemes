import os
import subprocess
import struct
from pathlib import Path
import logging

log = logging.getLogger(__name__)

class UnluacBatch:
    """batch decompile using unluac"""
    
    def __init__(self, unluac_jar_path='unluac.jar'):
        self.unluac_jar = unluac_jar_path
        
        # Check if jar exists
        if not os.path.exists(unluac_jar_path):
            raise FileNotFoundError(f"unluac jar not found: {unluac_jar_path}")
        
        # Check if java is available
        try:
            subprocess.run(['java', '-version'], capture_output=True, check=True)
        except Exception:
            raise RuntimeError("Java not found. Please install Java.")
    
    def has_4byte_prefix(self, data):
        """Check if luac file has 4-byte prefix"""
        if len(data) >= 8:
            if data[4] == 0x1B and data[5] == 0x4C:
                return True
        return False
    
    def strip_prefix(self, input_file, output_file):
        """Strip 4-byte prefix from luac file"""
        with open(input_file, 'rb') as f:
            data = f.read()
        
        if self.has_4byte_prefix(data):
            log.info("    Stripping 4-byte prefix...")
            prefix_value = struct.unpack('<I', data[:4])[0]
            log.info(f"    Prefix: 0x{prefix_value:08x}")
            with open(output_file, 'wb') as f:
                f.write(data[4:])
            return True
        else:
            with open(output_file, 'wb') as f:
                f.write(data)
            return False
        
    def decompile_file(self, luac_file, output_file, strip_prefix=True, stop_event=None):
        """
        Decompile a single .luac file using unluac
        """
        log.info(f"\nDecompiling: {luac_file}")

        # Read and check file
        with open(luac_file, 'rb') as f:
            data = f.read()

        log.info(f"  Size: {len(data)} bytes")
        log.info(f"  First bytes: {data[:20].hex()}")

        temp_file = luac_file

        if strip_prefix and self.has_4byte_prefix(data):
            temp_file = luac_file + '.tmp'
            self.strip_prefix(luac_file, temp_file)

        try:
            log.info("  Running unluac...")

            # Launch process non-blocking
            proc = subprocess.Popen(
                ['java', '-jar', self.unluac_jar, temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout_lines = []

            # Poll process periodically, allowing stop
            while True:
                if stop_event and stop_event.is_set():
                    log.warning("  User requested stop — terminating unluac process...")
                    proc.terminate()
                    proc.wait(timeout=2)
                    raise KeyboardInterrupt("Aborted by user")

                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    stdout_lines.append(line)

            stderr_output = proc.stderr.read()
            ret = proc.wait()

            if ret == 0:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, 'w', encoding='utf-8', errors='ignore') as f:
                    f.writelines(stdout_lines)

                log.info(f"  ✓ Success! Saved to {output_file}")
                for line in stdout_lines[:5]:
                    log.info(f"    {line.strip()}")
                return True
            else:
                log.error(f"  ✗ Failed with code {ret}")
                if stderr_output:
                    log.error(f"  Error: {stderr_output.strip()[:200]}")
                return False

        except KeyboardInterrupt:
            log.warning("  Lua decompile aborted mid-file.")
            return False

        except Exception as e:
            log.error(f"  ✗ Exception: {e}")
            return False

        finally:
            if temp_file != luac_file and os.path.exists(temp_file):
                os.remove(temp_file)

    
    def batch_decompile(self, input_dir, output_dir, stop_event=None):
        """
        Batch decompile all .luac files with optional stop_event for cancellation.
        """
        log.info(f"\n{'='*70}")
        log.info("BATCH DECOMPILATION")
        log.info(f"{'='*70}")

        input_path = Path(input_dir)
        output_path = Path(output_dir)
        luac_files = list(input_path.rglob('*.luac'))

        log.info(f"\nFound {len(luac_files)} .luac files")
        log.info(f"Output directory: {output_dir}\n")

        # nothing to do? exit gracefully
        if not luac_files:
            log.info("No .luac files found — skipping decompilation.\n")
            return {'success': 0, 'failed': 0}

        stats = {'success': 0, 'failed': 0}
        failed_files = []

        total = len(luac_files)
        for i, luac_file in enumerate(luac_files, 1):
            # Check stop request before each file
            if stop_event and stop_event.is_set():
                log.warning("Decompilation aborted by user.")
                break

            rel_path = luac_file.relative_to(input_path)
            output_file = output_path / rel_path.with_suffix('.lua')
            log.info(f"[{i}/{total}] {rel_path}")

            try:
                success = self.decompile_file(str(luac_file), str(output_file), stop_event=stop_event)
            except Exception as e:
                success = False
                log.error(f"[✗] Error decompiling {rel_path}: {e}")

            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                failed_files.append(str(rel_path))

        # --- final summary ---------------------------------------------------
        log.info(f"\n{'='*70}")
        log.info("FINAL SUMMARY")
        log.info(f"{'='*70}")
        log.info(f"Total files:  {len(luac_files)}")
        log.info(f"Success:      {stats['success']}")
        log.info(f"Failed:       {stats['failed']}")
        success_rate = stats['success'] / len(luac_files) * 100 if luac_files else 0.0
        log.info(f"Success rate: {success_rate:.1f}%")

        if failed_files:
            log.info(f"\nFailed files ({len(failed_files)}):")
            for f in failed_files[:20]:
                log.info(f"  - {f}")
            if len(failed_files) > 20:
                log.info(f"  ... and {len(failed_files) - 20} more")

        if stop_event and stop_event.is_set():
            log.warning(f"Task aborted early — processed {stats['success'] + stats['failed']} of {len(luac_files)} files.")

        return stats
