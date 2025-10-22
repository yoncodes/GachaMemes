import json
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import os
import logging


from fm.extractor import PakExtractor
from fm.metadata import Metadata
from fm.unluac import UnluacBatch
from fm.downloader import Downloader
from fm.asset import Asset



default_message = (
        "Fellow Moon Asset Extractor\n"
        "───────────────────────────────────────────\n"
        "Use the buttons above to run tasks.\n"
        "Examples:\n"
        "  • Decrypt AB Bundles – Decrypts the ab files (run downloader first or change path in config)\n"
        "  • Extract Lua – Extracts Lua from the apk (make sure to set path in config)\n"
        "  • Decrypt Lua – Decrypts the lua files (run extract lua first)\n"
        "  • Decrypt Metadata – Decrypts and extracts the metadata from the apk\n"
        "  • Download Asset Files – latest game assets\n"
        "  • Download Proto File – latest proto file\n"
        "  • Extract Proto – Builds the .proto fies \n"
        "  • Stop Task – cancel running jobs\n"
       
)


# --------------------- GUI Log Handler ---------------------
class TkTextHandler(logging.Handler):
    """Custom logging handler that outputs to a Tkinter Text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self._append, msg, record.levelno)

    def _append(self, msg, level):
        if level >= logging.ERROR:
            tag = "error"
        elif level >= logging.WARNING:
            tag = "warn"
        else:
            tag = "info"

        self.text_widget.insert(tk.END, msg + "\n", tag)
        self.text_widget.see(tk.END)

class RightClickMenu:
    """Reusable right-click menu for Tkinter text/entry widgets."""

    @staticmethod
    def attach(widget):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: widget.event_generate("<<SelectAll>>"))

        # Add clear option for text/scrolledtext widgets
        if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
            menu.add_separator()
            menu.add_command(
                label="Clear Output",
                command=lambda: RightClickMenu._reset_log_output(widget)
            )

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)
        widget.bind("<Button-2>", show_menu)  # macOS

    @staticmethod
    def _reset_log_output(widget):
        """Clear the log output and restore default message."""
        try:
            widget.config(state=tk.NORMAL)
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, default_message, "info")
            widget.see(tk.END)
            widget.config(state=tk.NORMAL)  # keep editable for logging
        except Exception as e:
            print(f"Failed to clear text: {e}")


# --------------------- CONFIG LOADER ---------------------
def load_config(path: str = "config.json") -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path.resolve()}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------- PIPELINE TASKS ---------------------
logger = logging.getLogger("fellowmoon")

def run_lua(cfg, stop_event=None):
    try:
        lua_cfg = cfg.get("LUA_DECRYPT_CONFIG", {})
        lua_path = Path(lua_cfg.get("lua_path", ""))
        output_dir = lua_cfg.get("output", "")

        if not lua_path.exists() or not any(lua_path.rglob("*.luac")):
            logger.warning(f"Lua path {lua_path} missing or empty.")
            return

        logger.info("Running Unluac batch decompiler...")
        UnluacBatch().batch_decompile(lua_path, output_dir, stop_event=stop_event)
        logger.info("Lua decompilation complete.\n")
    except Exception as e:
        logger.exception(f"Lua decompiler failed: {e}")

def run_extractor(cfg, stop_event=None):
    try:
        if stop_event and stop_event.is_set():
            logger.warning("Task aborted before start.")
            return

        ex_cfg = cfg.get("EXTRACTOR_CONFIG", {})
        md_cfg = cfg.get("METADATA_CONFIG", {})
        logger.info("Running PakExtractor...")

        PakExtractor(md_cfg.get("xapk_path")).extract_all_from_index(
            search_dir=ex_cfg.get("search_dir", ""),
            index_path=ex_cfg.get("index_path", ""),
            base_output_dir=ex_cfg.get("output_path", ""),
            save_encrypted=ex_cfg.get("save_encrypted", False),
            stop_event=stop_event,              
        )

        if stop_event and stop_event.is_set():
            logger.warning("Extraction aborted by user.")
        else:
            logger.info("Extraction complete.\n")

    except Exception as e:
        logger.exception(f"Extractor failed: {e}")


def run_metadata(cfg, stop_event=None, xapk_path=None):
    try:
        if stop_event and stop_event.is_set():
            logger.warning("Task aborted before start.")
            return

        md_cfg = cfg.get("METADATA_CONFIG", {})
        logger.info("Running Metadata decryptor...")

       
        xapk = xapk_path or md_cfg.get("xapk_path", "")
        output_dir = md_cfg.get("decrypt_path", "")

        if not xapk or not os.path.exists(xapk):
            logger.error(f"XAPK file not found: {xapk}")
            return

        Metadata().extract_and_decrypt(
            xapk_path=xapk,
            output_dir=output_dir,
        )

        if stop_event and stop_event.is_set():
            logger.warning("Metadata decryption aborted by user.")
        else:
            logger.info("Metadata decryption complete.\n")

    except Exception as e:
        logger.exception(f"Metadata failed: {e}")



def run_downloader(cfg, stop_event=None, json_only=None):
    try:
        if stop_event and stop_event.is_set():
            logger.warning("Task aborted before start.")
            return

        dl_cfg = cfg.get("DOWNLOADER_CONFIG", {})
        if json_only is not None:
            dl_cfg["json_only"] = json_only 

        logger.info("Running Downloader...")

        Downloader().main(
            download=dl_cfg.get("download", True),
            workers=dl_cfg.get("workers", 8),
            filter_str=dl_cfg.get("filter", None),
            stop_event=stop_event,
            json_only=dl_cfg.get("json_only", False),
        )

        if stop_event and stop_event.is_set():
            logger.warning("Downloader aborted by user.")
        else:
            logger.info("Downloader complete.\n")

    except Exception as e:
        logger.exception(f"Downloader failed: {e}")

def run_proto(cfg, stop_event=None):
    try:
       
        proto_cfg = cfg.get("PROTO_CONFIG", {})
        logger.info("Running Proto download via Downloader...")
        Downloader().download_proto(file_path=proto_cfg.get("file_path"))

        logger.info("Proto download complete.")
    except Exception as e:
        logger.exception(f"Proto downloader failed: {e}")

def run_proto_extractor(cfg, stop_event=None):
    try:
        proto_cfg = cfg.get("PROTO_CONFIG", {})
        log = logging.getLogger("fellowmoon")
        log.info("Running ProtoExtractor...")

        from fm.extractor import ProtoExtractor
        ProtoExtractor(
            proto_dir=proto_cfg.get("proto_dir", ""),
            output_dir=proto_cfg.get("output_dir", "")
        ).extract_and_decode(stop_event=stop_event)

        if stop_event and stop_event.is_set():
            log.warning("Proto extraction aborted by user.")
        else:
            log.info("Proto extraction complete.\n")

    except Exception as e:
        log.exception(f"ProtoExtractor failed: {e}")


def run_bundles(cfg, stop_event=None):
    try:
        if stop_event and stop_event.is_set():
            logger.warning("Task aborted before start.")
            return

        asset_cfg = cfg.get("ASSET_CONFIG", {})
        base_path = asset_cfg.get("base_path", "")
        out_dir = asset_cfg.get("output_path", "decrypted_bundles")

        if not os.path.isdir(base_path):
            logger.warning(f"Bundle directory not found: {base_path}")
            return

        logger.info(f"Running Asset.batch_decode on: {base_path}")
        Asset().batch_decode(base_path=base_path, out_dir=out_dir, stop_event=stop_event)

        if stop_event and stop_event.is_set():
            logger.warning("Bundle decryption aborted by user.")
        else:
            logger.info("Bundle decryption complete.\n")

    except Exception as e:
        logger.exception(f"Bundle decryption failed: {e}")


# --------------------- GUI ---------------------
class FellowMoonGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fellow Moon Asset Extractor")
        self.root.geometry("900x600")
        self.root.resizable(False, False)

        self.cfg_path = tk.StringVar(value="config.json")
        
        self.filter_str = tk.StringVar(value="")
        self.worker_count = tk.IntVar(value=8)
        self.json_only = tk.BooleanVar(value=False)

        self.xapk_path = tk.StringVar(value="")

        self.current_thread = None
        self.stop_event = threading.Event()

        self.log_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=25)

        self._build_ui()
        self._setup_logger()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            cfg = load_config("config.json")
            dl_cfg = cfg.get("DOWNLOADER_CONFIG", {})
            if dl_cfg.get("json_only", False):
                self.json_only.set(True)

            meta_cfg = cfg.get("METADATA_CONFIG", {})
            default_xapk = meta_cfg.get("xapk_path", "")
            self.xapk_path.set(default_xapk)
        except Exception:
            pass


    def _build_ui(self):
        frm = tk.Frame(self.root)
        frm.pack(pady=10)

        tk.Label(frm, text="Config Path:").grid(row=0, column=0, padx=5)
        self.cfg_entry = tk.Entry(frm, textvariable=self.cfg_path, width=60)
        self.cfg_entry.grid(row=0, column=1)
        tk.Button(frm, text="Browse", command=self._browse_config).grid(row=0, column=2, padx=5)

        tk.Label(frm, text="XAPK File:").grid(row=1, column=0, padx=5, pady=3)
        self.xapk_entry = tk.Entry(frm, textvariable=self.xapk_path, width=60)
        self.xapk_entry.grid(row=1, column=1, padx=5, pady=3)
        tk.Button(frm, text="Browse", command=self._browse_xapk).grid(row=1, column=2, padx=5, pady=3)


       # --- Downloader options ---
        opt_frame = tk.LabelFrame(self.root, text="Downloader Options")
        opt_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(opt_frame, text="Filter:").grid(row=0, column=0, padx=5, pady=3, sticky="e")

        # Filter dropdown (Combobox)
        self.filter_combo = ttk.Combobox(opt_frame, textvariable=self.filter_str, width=30, state="readonly")
        self.filter_combo.grid(row=0, column=1, padx=5, pady=3)

        tk.Button(opt_frame, text="Download Package Lists", command=self._download_index_and_refresh).grid(row=0, column=2, padx=5)

        tk.Label(opt_frame, text="Workers:").grid(row=0, column=3, padx=5, pady=3, sticky="e")
        tk.Spinbox(opt_frame, from_=1, to=64, textvariable=self.worker_count, width=5).grid(row=0, column=4, padx=5, pady=3)
    

        # Initialize dropdown values
        self._refresh_filter_list()

        # --- Main action buttons ---
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)


        tk.Button(btn_frame, text="Extract Lua (1)", width=15, command=lambda: self._run_task(run_extractor)).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(btn_frame, text="Decrypt Lua (2)", width=15, command=lambda: self._run_task(run_lua)).grid(row=1, column=1, padx=5, pady=5)

        tk.Button(
            btn_frame,
            text="Decrypt & Extract Metadata",
            width=25,
            command=lambda: self._run_task(
                lambda cfg, stop_event=None: run_metadata(
                    cfg,
                    stop_event=stop_event,
                    xapk_path=self.xapk_path.get()
                ),
                name="run_metadata"
            )
        ).grid(row=0, column=2, padx=5, pady=5)


        tk.Button(btn_frame, text="Decrypt AB Bundles", width=15, command=lambda: self._run_task(run_bundles)).grid(row=0, column=0, padx=5, pady=5)
        
        tk.Button(btn_frame, text="Download Asset Files", width=18,
          command=lambda: self._run_task(lambda cfg, stop_event=None: run_downloader(cfg, stop_event, json_only=False))
            ).grid(row=0, column=3, padx=5, pady=5)
        tk.Button(btn_frame, text="Download Proto File", width=18,
          command=lambda: self._run_task(run_proto)
        ).grid(row=0, column=4, padx=5, pady=5)
        tk.Button(btn_frame, text="Extract Proto", width=15,
          command=lambda: self._run_task(run_proto_extractor)).grid(row=1, column=4, padx=5, pady=5)
        tk.Button(btn_frame, text="Stop Task", width=15, command=self._stop_task).grid(row=0, column=5, padx=5, pady=5)
        


        # Define fonts
        header_font = tkfont.Font(family="Arial", size=11, weight="bold")
        body_font   = tkfont.Font(family="Ariel", size=12, weight="bold")
        warn_font   = tkfont.Font(family="Arial", size=10, slant="italic")


        # --- Log text area ---
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_text.config(bg="#1E1E1E", fg="#E0E0E0", insertbackground="white")
        self.log_text.tag_config("info", foreground="#f5f4eb")
        self.log_text.tag_config("warn",  foreground="#FFA500", font=warn_font)
        self.log_text.tag_config("error", foreground="#FF3333", font=header_font)
        self.log_text.tag_config("header", foreground="#FFFFFF", font=header_font)

        self.log_text.config(font=body_font)

        RightClickMenu.attach(self.log_text)
        RightClickMenu.attach(self.filter_combo)
        RightClickMenu.attach(self.cfg_entry)

       # --- Default text ---
        self.log_text.config(state=tk.NORMAL)  # make editable for insertion
        self.log_text.delete("1.0", tk.END)

        self.log_text.insert(tk.END, default_message, "info")
        self.log_text.config(state=tk.NORMAL)


        

    def _setup_logger(self):
        """Attach a TkTextHandler to the root logger."""
        handler = TkTextHandler(self.log_text)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        handler.setFormatter(fmt)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Remove default handlers if any
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)

        root_logger.addHandler(handler)

    def _on_close(self):
        """Handle GUI close safely: stop threads and exit cleanly."""
        if self.current_thread and self.current_thread.is_alive():
            if messagebox.askyesno(
                "Exit",
                "A task is still running. Do you want to stop it and close?"
            ):
                self.stop_event.set()
            else:
                return  # cancel close
        try:
            # Avoid TkTextHandler calling a destroyed widget
            for handler in logging.getLogger().handlers[:]:
                if isinstance(handler, TkTextHandler):
                    logging.getLogger().removeHandler(handler)
            self.root.destroy()
        except Exception:
            os._exit(0)  # final failsafe if Tk crashes


    def _browse_config(self):
        path = filedialog.askopenfilename(title="Select config.json", filetypes=[("JSON files", "*.json")])
        if path:
            self.cfg_path.set(path)

    def _run_task(self, func, name=None):
        """Start a threaded task and keep reference for cancellation."""
        # Prevent launching multiple tasks simultaneously
        if self.current_thread and self.current_thread.is_alive():
            messagebox.showwarning("Busy", "A task is already running. Stop it before starting another.")
            return

        try:
            cfg = load_config(self.cfg_path.get())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Inject GUI overrides for downloader
        dl_cfg = cfg.setdefault("DOWNLOADER_CONFIG", {})
        selected_filter = self.filter_str.get().strip()

        # Treat "All" as empty string (no filter)
        if selected_filter.lower() == "all":
            selected_filter = ""

        dl_cfg["filter"] = selected_filter or None
        dl_cfg["workers"] = self.worker_count.get()
        dl_cfg["json_only"] = self.json_only.get()

        meta_cfg = cfg.get("METADATA_CONFIG", {})
        default_xapk = meta_cfg.get("xapk_path", "")
        self.xapk_path = tk.StringVar(value=default_xapk)

        # Save updated JSON-only setting persistently
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            logger.warning(f"Failed to save config: {e}")


        # Reset stop flag
        self.stop_event.clear()

        # Thread target
        def task_wrapper():
            label = name or func.__name__
            logger.info(f"=== Starting {label} ===")
            try:
                if func == run_downloader:
                    func(cfg, stop_event=self.stop_event, json_only=self.json_only.get())
                else:
                    func(cfg, stop_event=self.stop_event)
            except TypeError:
                func(cfg)
            except Exception as e:
                logger.exception(f"[✗] Error in {label}: {e}")
            finally:
                logger.info(f"=== Finished {label} ===\n")


        # Start thread
        self.current_thread = threading.Thread(target=task_wrapper, daemon=True)
        self.current_thread.start()

    def _stop_task(self):
        """Signal current thread to stop."""
        if self.current_thread and self.current_thread.is_alive():
            self.stop_event.set()
            logger.warning("User requested task stop...")
        else:
            messagebox.showinfo("Info", "No active task to stop.")

    def _refresh_filter_list(self):
        """Scan downloads/version_index/<latest_pkg> for JSON files and update dropdown."""
        try:
            base = Path("downloads/version_index")
            if not base.exists():
                self.filter_combo["values"] = ["All"]
                self.filter_combo.set("All")
                return

            # Find most recently modified subdirectory (latest package)
            dirs = [d for d in base.iterdir() if d.is_dir()]
            if not dirs:
                self.filter_combo["values"] = ["All"]
                self.filter_combo.set("All")
                return

            latest_dir = max(dirs, key=lambda d: d.stat().st_mtime)
            json_files = list(latest_dir.glob("*.json*"))

            filters = []
            for jf in json_files:
                name = jf.name
                if ".json" in name:
                    prefix = name.split(".json", 1)[0]
                    filters.append(prefix)

            filters = sorted(set(filters))
            filters.insert(0, "All")  # Add the "All" option at the top

            self.filter_combo["values"] = filters
            self.filter_combo.set("All -- Downloads everything")

            logger.info(f"Filter list updated ({len(filters) - 1} entries) from {latest_dir.name}")

        except Exception as e:
            logger.warning(f"Failed to refresh filter list: {e}")
            self.filter_combo["values"] = ["All"]
            self.filter_combo.set("All")


    def _download_index_and_refresh(self):
        """Download the latest JSON index files and update filter dropdown."""
        if self.current_thread and self.current_thread.is_alive():
            messagebox.showwarning("Busy", "A task is already running. Stop it before refreshing.")
            return

        try:
            cfg = load_config(self.cfg_path.get())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dl_cfg = cfg.setdefault("DOWNLOADER_CONFIG", {})
        dl_cfg["download"] = True
        dl_cfg["workers"] = 4
        dl_cfg["filter"] = None  # no filter
        dl_cfg["json_only"] = True  # force JSON-only mode

        # Reset stop flag
        self.stop_event.clear()

        def task_wrapper():
            logger.info("=== Refreshing Version Index (JSON only) ===")
            try:
                run_downloader(cfg, stop_event=self.stop_event, json_only=True)
                self._refresh_filter_list()
            except Exception as e:
                logger.exception(f"Error refreshing index: {e}")
            finally:
                logger.info("=== Index Refresh Complete ===\n")

        self.current_thread = threading.Thread(target=task_wrapper, daemon=True)
        self.current_thread.start()

    def _browse_xapk(self):
        """Browse for an XAPK file and update entry field."""
        file_path = filedialog.askopenfilename(
            title="Select XAPK File",
            filetypes=[("XAPK files", "*.xapk"), ("All files", "*.*")]
        )
        if file_path:
            self.xapk_path.set(file_path)
            logger.info(f"Selected XAPK: {file_path}")




# --------------------- ENTRY POINT ---------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = FellowMoonGUI(root)
    root.mainloop()
