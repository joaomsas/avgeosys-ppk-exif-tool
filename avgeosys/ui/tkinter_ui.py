"""
AVGeoSys Tkinter GUI — dark theme, thread-safe logging, progress bar.

Validation: manual execution only (per Constitution Principle III).
"""

import json
import logging
import logging.handlers
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, ttk
import tkinter as tk

# ---------------------------------------------------------------------------
# Paleta de cores — identidade visual da empresa
#   Verde: #22653b  |  Laranja: #d2801f
# ---------------------------------------------------------------------------
BG_DARK   = "#191c1a"   # fundo principal (verde escuríssimo neutro)
BG_PANEL  = "#222822"   # painéis e frames
BG_INPUT  = "#2c352d"   # campos de entrada
FG_TEXT   = "#e6ede8"   # texto principal
FG_DIM    = "#7a9080"   # texto secundário / dim

# Cores da empresa
ACCENT_GREEN  = "#22653b"   # verde corporativo
ACCENT_ORANGE = "#d2801f"   # laranja corporativo

# Botões de ação
ACCENT_PPK    = ACCENT_GREEN    # ▶ PPK
ACCENT_GEO    = ACCENT_ORANGE   # ▶ Geotag
ACCENT_CANCEL = "#b03020"       # ⏹ Cancelar

# Botões secundários
BTN_HOVER = "#354035"           # hover genérico

# Status bar
STATUS_OK  = "#3db36a"          # verde mais claro (legível sobre fundo escuro)
STATUS_RUN = ACCENT_ORANGE
STATUS_ERR = "#d94f3a"

FONT_UI    = ("Segoe UI", 10)
FONT_MONO  = ("Consolas", 9)
FONT_TITLE = ("Segoe UI", 10, "bold")

_ACCENT_PPK_DARK    = "#1a4d2c"
_ACCENT_GEO_DARK    = "#a8661a"
_ACCENT_CANCEL_DARK = "#8c2518"


def _darken(hex_color: str) -> str:
    """Return a ~15% darker version of hex_color."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    factor = 0.85
    return "#{:02x}{:02x}{:02x}".format(
        int(r * factor), int(g * factor), int(b * factor)
    )


class AVGeoSysUI:
    """Main application window."""

    def __init__(self) -> None:
        from avgeosys.core.settings import load as _load_settings
        self._settings = _load_settings()

        from avgeosys import __version__
        self.root = tk.Tk()
        self.root.title(f"AVGeoSys v{__version__} — PPK & Geotag Tool")
        self.root.minsize(720, 560)

        # Centre on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw - 720) // 2}+{(sh - 560) // 2}")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)  # log row expands

        # Application icon — usa sys._MEIPASS no bundle PyInstaller, fallback para dev
        try:
            import sys as _sys
            _base = Path(_sys._MEIPASS) if hasattr(_sys, "_MEIPASS") else Path(__file__).parent.parent.parent
            icon_path = _base / "AVGeoSysIcon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
            else:
                png_path = _base / "AVGeoSysIcon.png"
                if png_path.exists():
                    img = tk.PhotoImage(file=str(png_path))
                    self.root.iconphoto(True, img)
        except Exception:
            pass

        # Log queue + handler
        self._log_queue: queue.Queue = queue.Queue(maxsize=2000)
        self._qh = logging.handlers.QueueHandler(self._log_queue)
        self._qh.setLevel(logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(self._qh)

        # File handler for current task (set/cleared per task)
        self._file_handler: logging.FileHandler = None  # type: ignore[assignment]

        # Cancel event for graceful worker shutdown
        self._cancel_event = threading.Event()
        self._worker_thread: threading.Thread = None  # type: ignore[assignment]
        self._task_start_time: float = 0.0

        self._apply_dark_theme()
        self._build_project_panel()
        self._build_action_panel()
        self._build_progress_status()
        self._build_log_panel()

        self.root.after(100, self._poll_log_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Windows drag-and-drop
        self.root.after(200, self._setup_drag_drop)

        # Verificação de atualização em segundo plano (não bloqueia a UI)
        self._check_for_updates()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_dark_theme(self) -> None:
        self.root.configure(bg=BG_DARK)
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG_DARK, foreground=FG_TEXT, font=FONT_UI)
        style.configure(
            "TLabelframe",
            background=BG_DARK,
            foreground=FG_TEXT,
            bordercolor=BG_PANEL,
            font=FONT_UI,
        )
        style.configure(
            "TLabelframe.Label",
            background=BG_DARK,
            foreground=FG_TEXT,
            font=FONT_TITLE,
        )
        style.configure(
            "TCheckbutton",
            background=BG_DARK,
            foreground=FG_TEXT,
            selectcolor=BG_PANEL,
            font=FONT_UI,
        )
        style.map("TCheckbutton", background=[("active", BG_DARK)])
        style.configure(
            "TEntry",
            fieldbackground=BG_INPUT,
            foreground=FG_TEXT,
            insertcolor=FG_TEXT,
            bordercolor=BG_PANEL,
        )
        style.configure(
            "green.Horizontal.TProgressbar",
            troughcolor=BG_PANEL,
            background=ACCENT_PPK,
        )
        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            foreground=FG_TEXT,
            background=BG_PANEL,
        )

    # ------------------------------------------------------------------
    # Panels
    # ------------------------------------------------------------------

    def _build_project_panel(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Projeto", padding=(8, 4))
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Diretório:", font=FONT_UI).grid(
            row=0, column=0, sticky="w", padx=(0, 4)
        )

        self._path_var = tk.StringVar()
        entry = ttk.Entry(
            frame, textvariable=self._path_var, state="readonly", font=FONT_UI
        )
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))

        btn = tk.Button(
            frame,
            text="📁 Selecionar",
            command=self._browse_folder,
            bg=BG_PANEL,
            fg=FG_TEXT,
            activebackground=BTN_HOVER,
            activeforeground=FG_TEXT,
            relief="flat",
            font=FONT_UI,
            cursor="hand2",
        )
        btn.grid(row=0, column=2)
        btn.bind("<Enter>", lambda e: btn.configure(bg=BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BG_PANEL))

        # Recent projects button (triangle / dropdown)
        self._recent_btn = tk.Button(
            frame,
            text="▼",
            command=self._show_recent_menu,
            bg=BG_PANEL,
            fg=FG_TEXT,
            activebackground=BTN_HOVER,
            activeforeground=FG_TEXT,
            relief="flat",
            font=FONT_UI,
            cursor="hand2",
            padx=4,
        )
        self._recent_btn.grid(row=0, column=3, padx=(2, 0))
        self._recent_btn.bind("<Enter>", lambda e: self._recent_btn.configure(bg=BTN_HOVER))
        self._recent_btn.bind("<Leave>", lambda e: self._recent_btn.configure(bg=BG_PANEL))

        # Options row — valores carregados das configurações salvas
        self._skip_rover_nav_var = tk.BooleanVar(value=False)
        self._orthometric_var = tk.BooleanVar(value=self._settings.get("orthometric", False))
        self._solution_type_var = tk.StringVar(value=self._settings.get("solution_type", "forward"))
        self._backup_exif_var = tk.BooleanVar(value=self._settings.get("backup_exif", False))

        ttk.Checkbutton(
            frame,
            text="Usar NAV do Rover",
            variable=self._skip_rover_nav_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Checkbutton(
            frame,
            text="Altitude Ortométrica",
            variable=self._orthometric_var,
        ).grid(row=1, column=2, sticky="w", pady=(4, 0))

        ttk.Checkbutton(
            frame,
            text="Backup EXIF",
            variable=self._backup_exif_var,
        ).grid(row=1, column=3, sticky="w", pady=(4, 0))

        ttk.Label(frame, text="Solução PPK:", font=FONT_UI).grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        sol_combo = ttk.Combobox(
            frame,
            textvariable=self._solution_type_var,
            values=["forward", "backward", "combined"],
            state="readonly",
            width=12,
        )
        sol_combo.grid(row=2, column=1, sticky="w", pady=(4, 0), padx=(0, 4))

        # PPK parameter fields — valores carregados das configurações salvas
        from avgeosys import config as _cfg
        self._elev_mask_var = tk.StringVar(
            value=str(self._settings.get("elevation_mask", getattr(_cfg, "PPK_ELEVATION_MASK", 15)))
        )
        self._ar_threshold_var = tk.StringVar(
            value=str(self._settings.get("ar_threshold", getattr(_cfg, "PPK_AR_THRESHOLD", 3.0)))
        )
        self._nav_systems_var = tk.StringVar(
            value=str(self._settings.get("nav_systems", getattr(_cfg, "PPK_NAV_SYSTEMS", "G,R,E,C")))
        )

        ttk.Label(frame, text="Máscara elev. (°):", font=FONT_UI).grid(
            row=3, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Entry(frame, textvariable=self._elev_mask_var, width=6, font=FONT_UI).grid(
            row=3, column=1, sticky="w", pady=(4, 0), padx=(0, 8)
        )

        ttk.Label(frame, text="Threshold AR:", font=FONT_UI).grid(
            row=3, column=2, sticky="w", pady=(4, 0)
        )
        ttk.Entry(frame, textvariable=self._ar_threshold_var, width=6, font=FONT_UI).grid(
            row=3, column=3, sticky="w", pady=(4, 0)
        )

        ttk.Label(frame, text="Sistemas NAV:", font=FONT_UI).grid(
            row=4, column=0, sticky="w", pady=(2, 4)
        )
        ttk.Entry(frame, textvariable=self._nav_systems_var, width=14, font=FONT_UI).grid(
            row=4, column=1, sticky="w", pady=(2, 4), padx=(0, 4)
        )

        # Restaura último projeto
        last = self._settings.get("last_project", "")
        if last and Path(last).is_dir():
            self._path_var.set(last)

        self._project_widgets = [entry, btn]

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecionar diretório do projeto")
        if folder:
            self._set_project_path(folder)

    def _set_project_path(self, folder: str) -> None:
        """Set the active project path and update recent projects."""
        self._path_var.set(folder)
        self._add_to_recent_projects(folder)
        self._save_settings()

    def _add_to_recent_projects(self, folder: str) -> None:
        """Add *folder* to the recent projects list (max 5, most-recent first)."""
        recent: list = self._settings.get("recent_projects", [])
        folder = str(folder)
        if folder in recent:
            recent.remove(folder)
        recent.insert(0, folder)
        self._settings["recent_projects"] = recent[:5]

    def _show_recent_menu(self) -> None:
        """Show a popup menu with recent projects."""
        recent: list = self._settings.get("recent_projects", [])
        valid = [p for p in recent if Path(p).is_dir()]
        if not valid:
            return
        menu = tk.Menu(self.root, tearoff=0, bg=BG_PANEL, fg=FG_TEXT,
                       activebackground=BTN_HOVER, activeforeground=FG_TEXT,
                       font=FONT_UI)
        for p in valid:
            label = p if len(p) <= 55 else "..." + p[-52:]
            menu.add_command(
                label=label,
                command=lambda path=p: self._set_project_path(path),
            )
        try:
            x = self._recent_btn.winfo_rootx()
            y = self._recent_btn.winfo_rooty() + self._recent_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _build_action_panel(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Ações", padding=(8, 4))
        frame.grid(row=1, column=0, sticky="ew", padx=10, pady=4)

        self._btn_ppk = tk.Button(
            frame,
            text="▶ PPK",
            bg=ACCENT_PPK,
            fg="#ffffff",
            activebackground=_darken(ACCENT_PPK),
            activeforeground="#ffffff",
            font=FONT_TITLE,
            padx=20,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=lambda: self._run_task(self._pipeline_ppk_only),
        )
        self._btn_ppk.pack(side="left", padx=(0, 8))
        self._btn_ppk.bind("<Enter>", lambda e: self._btn_ppk.configure(bg=_darken(ACCENT_PPK)))
        self._btn_ppk.bind("<Leave>", lambda e: self._btn_ppk.configure(bg=ACCENT_PPK))

        self._btn_geotag = tk.Button(
            frame,
            text="▶ Geotag",
            bg=ACCENT_GEO,
            fg="#ffffff",
            activebackground=_darken(ACCENT_GEO),
            activeforeground="#ffffff",
            font=FONT_TITLE,
            padx=20,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=lambda: self._run_task(self._pipeline_geotag_only),
        )
        self._btn_geotag.pack(side="left", padx=(0, 8))
        self._btn_geotag.bind(
            "<Enter>", lambda e: self._btn_geotag.configure(bg=_darken(ACCENT_GEO))
        )
        self._btn_geotag.bind("<Leave>", lambda e: self._btn_geotag.configure(bg=ACCENT_GEO))

        self._btn_all = tk.Button(
            frame,
            text="▶ Tudo",
            bg="#1c5430",
            fg="#ffffff",
            activebackground="#164025",
            activeforeground="#ffffff",
            font=FONT_TITLE,
            padx=20,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=lambda: self._run_task(self._pipeline_all),
        )
        self._btn_all.pack(side="left", padx=(0, 8))
        self._btn_all.bind("<Enter>", lambda e: self._btn_all.configure(bg="#164025"))
        self._btn_all.bind("<Leave>", lambda e: self._btn_all.configure(bg="#1c5430"))

        # Separator visual
        tk.Frame(frame, bg=BG_PANEL, width=2, height=36).pack(side="left", padx=(0, 8))

        # Map button — shows quality scatter plot
        ACCENT_MAP = "#1a6e80"
        self._btn_map = tk.Button(
            frame,
            text="📊 Mapa",
            bg=ACCENT_MAP,
            fg="#ffffff",
            activebackground=_darken(ACCENT_MAP),
            activeforeground="#ffffff",
            font=FONT_TITLE,
            padx=16,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._open_quality_map,
        )
        self._btn_map.pack(side="left", padx=(0, 8))
        self._btn_map.bind("<Enter>", lambda e: self._btn_map.configure(bg=_darken(ACCENT_MAP)))
        self._btn_map.bind("<Leave>", lambda e: self._btn_map.configure(bg=ACCENT_MAP))

        # FieldUpload button
        ACCENT_UPLOAD = "#b5691a"
        self._btn_upload = tk.Button(
            frame,
            text="📦 FieldUpload",
            bg=ACCENT_UPLOAD,
            fg="#ffffff",
            activebackground=_darken(ACCENT_UPLOAD),
            activeforeground="#ffffff",
            font=FONT_TITLE,
            padx=16,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=lambda: self._run_task(self._pipeline_fieldupload),
        )
        self._btn_upload.pack(side="left")
        self._btn_upload.bind(
            "<Enter>", lambda e: self._btn_upload.configure(bg=_darken(ACCENT_UPLOAD))
        )
        self._btn_upload.bind(
            "<Leave>", lambda e: self._btn_upload.configure(bg=ACCENT_UPLOAD)
        )

        # Cancel button — visible only during processing
        self._btn_cancel = tk.Button(
            frame,
            text="⏹ Cancelar",
            bg=ACCENT_CANCEL,
            fg="#ffffff",
            activebackground=_darken(ACCENT_CANCEL),
            activeforeground="#ffffff",
            font=FONT_TITLE,
            padx=20,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._request_cancel,
        )
        # Not packed yet — shown only when running
        self._btn_cancel.bind(
            "<Enter>", lambda e: self._btn_cancel.configure(bg=_darken(ACCENT_CANCEL))
        )
        self._btn_cancel.bind(
            "<Leave>", lambda e: self._btn_cancel.configure(bg=ACCENT_CANCEL)
        )

        self._action_buttons = [
            self._btn_ppk, self._btn_geotag, self._btn_all,
            self._btn_map, self._btn_upload,
        ]

    def _build_progress_status(self) -> None:
        frame = tk.Frame(self.root, bg=BG_DARK)
        frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 0))
        frame.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(
            frame,
            style="green.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
            value=0,
        )
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self._status_var = tk.StringVar(value="● Pronto")
        self._status_label = tk.Label(
            frame,
            textvariable=self._status_var,
            bg=BG_DARK,
            fg=STATUS_OK,
            font=FONT_UI,
            anchor="w",
        )
        self._status_label.grid(row=1, column=0, sticky="w")

        # Banner de atualização — oculto por padrão, exibido quando há nova versão
        self._update_banner = tk.Label(
            frame,
            text="",
            bg=ACCENT_ORANGE,
            fg="#ffffff",
            font=FONT_UI,
            anchor="w",
            cursor="hand2",
            padx=6,
            pady=3,
        )
        # Não adicionado ao grid ainda; _show_update_banner o exibe quando necessário

    def _show_update_banner(self, info: dict) -> None:
        """Exibe o banner de atualização na UI (deve ser chamado via root.after)."""
        version = info.get("version", "?")
        channel = info.get("channel", "stable")
        channel_tag = " [beta]" if channel == "beta" else ""
        url = info.get("url", "")
        notes = info.get("notes", "")
        text = f"  Nova versão v{version}{channel_tag} disponível — clique aqui para baixar"
        if notes:
            text += f"  ({notes})"
        text += "  "
        self._update_banner.configure(text=text)
        self._update_banner.bind(
            "<Button-1>",
            lambda e, u=url: self._open_update_url(u),
        )
        self._update_banner.grid(row=2, column=0, sticky="ew", pady=(4, 0))

    def _open_update_url(self, url: str) -> None:
        """Abre a URL de download no navegador padrão."""
        import webbrowser
        if url:
            webbrowser.open(url)

    def _build_log_panel(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Log", padding=(4, 4))
        frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(4, 10))
        self.root.rowconfigure(3, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        clear_btn = tk.Button(
            frame,
            text="🗑 Limpar log",
            bg=BG_PANEL,
            fg=FG_DIM,
            activebackground=BTN_HOVER,
            activeforeground=FG_TEXT,
            font=FONT_UI,
            relief="flat",
            cursor="hand2",
            command=self._clear_log,
        )
        clear_btn.grid(row=0, column=1, sticky="ne", padx=(4, 0))

        self.log_box = tk.Text(
            frame,
            font=FONT_MONO,
            bg=BG_DARK,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            state="disabled",
            wrap="word",
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log_box.yview)
        scrollbar.grid(row=0, column=2, sticky="ns")
        self.log_box.configure(yscrollcommand=scrollbar.set)

        self.log_box.tag_config("INFO", foreground=FG_TEXT)
        self.log_box.tag_config("WARNING", foreground="#FFA500")
        self.log_box.tag_config("ERROR", foreground=STATUS_ERR)
        self.log_box.tag_config("DEBUG", foreground=FG_DIM)

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Thread-safe log polling (bounded — drains at most 50 records/poll)
    # ------------------------------------------------------------------

    def _poll_log_queue(self) -> None:
        for _ in range(50):
            try:
                record = self._log_queue.get_nowait()
            except queue.Empty:
                break
            msg = (
                self._qh.formatter.format(record)
                if self._qh.formatter
                else record.getMessage()
            )
            valid_tags = ("INFO", "WARNING", "ERROR", "DEBUG")
            tag = record.levelname if record.levelname in valid_tags else "INFO"
            self.log_box.configure(state="normal")
            self.log_box.insert(tk.END, msg + "\n", tag)
            self.log_box.see(tk.END)
            self.log_box.configure(state="disabled")
        self.root.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------
    # Task execution (background thread)
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str) -> None:
        self._status_var.set(text)
        self._status_label.configure(fg=color)

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in self._action_buttons:
            btn.configure(state=state)
        if enabled:
            self._btn_cancel.pack_forget()
        else:
            self._btn_cancel.pack(side="left", padx=(16, 0))

    def _set_progress(self, value: float) -> None:
        """Set progress bar to *value* (0–100). Updates ETA in status if task is running."""
        self.root.after(0, lambda v=value: self.progress.configure(value=v))
        if value > 2 and self._task_start_time > 0:
            elapsed = time.monotonic() - self._task_start_time
            if elapsed > 1.0 and value < 99:
                eta_sec = elapsed * (100.0 - value) / value
                eta_str = f"{eta_sec:.0f}s" if eta_sec < 60 else f"{eta_sec/60:.1f}min"
                # Thread-safe: schedule Tk operations on main thread only
                self.root.after(0, lambda e=eta_str: self._apply_eta(e))

    def _apply_eta(self, eta_str: str) -> None:
        """Apply ETA to status label — must be called in main thread via root.after."""
        try:
            cur = self._status_var.get()
            base = cur.split(" | ETA:")[0]
            self._status_var.set(f"{base} | ETA: {eta_str}")
            self._status_label.configure(fg=STATUS_RUN)
        except Exception:
            pass

    def _request_cancel(self) -> None:
        self._cancel_event.set()
        self._set_status("● Cancelando...", STATUS_ERR)
        logging.getLogger(__name__).warning("Cancelamento solicitado pelo usuário.")

    def _run_task(self, fn) -> None:
        project_str = self._path_var.get().strip()
        if not project_str:
            self._set_status("● Erro: selecione um diretório", STATUS_ERR)
            return

        if self._worker_thread is not None and self._worker_thread.is_alive():
            return  # already running

        self._cancel_event.clear()
        self._task_start_time = time.monotonic()
        self._set_controls_enabled(False)
        self._set_status("● Processando...", STATUS_RUN)
        self.progress.configure(value=0)

        def worker():
            # Configura log em arquivo para esta execução
            project_path = Path(project_str)
            self._start_file_log(project_path)
            try:
                fn(project_path)
                if self._cancel_event.is_set():
                    self.root.after(0, lambda: self._set_status("● Cancelado", STATUS_ERR))
                else:
                    self.root.after(0, lambda: self._set_status("● Pronto", STATUS_OK))
                    self.root.after(0, lambda: self.progress.configure(value=100))
            except Exception as exc:
                logging.getLogger(__name__).error("Erro no pipeline: %s", exc, exc_info=True)
                msg = f"● Erro: {exc}"
                self.root.after(0, lambda m=msg: self._set_status(m, STATUS_ERR))
            finally:
                self._task_start_time = 0.0
                self._stop_file_log()
                self.root.after(0, lambda: self._set_controls_enabled(True))

        self._worker_thread = threading.Thread(target=worker, daemon=False)
        self._worker_thread.start()

    def _start_file_log(self, project_path: Path) -> None:
        """Abre FileHandler gravando em <projeto>/PPK_Results/avgeosys_YYYYMMDD_HHMMSS.log."""
        import datetime
        self._current_log_path: Path = None   # type: ignore[assignment]
        self._current_project_path: Path = project_path
        try:
            log_dir = project_path / "PPK_Results"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = log_dir / f"avgeosys_{ts}.log"
            fh = logging.FileHandler(log_path, encoding="utf-8-sig")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            ))
            logging.getLogger().addHandler(fh)
            self._file_handler = fh
            self._current_log_path = log_path
        except Exception as exc:
            logging.getLogger(__name__).debug("Não foi possível criar log em arquivo: %s", exc)

    def _stop_file_log(self) -> None:
        """Fecha o FileHandler e envia o log para o Google Drive em segundo plano."""
        log_path = getattr(self, "_current_log_path", None)
        project_path = getattr(self, "_current_project_path", None)

        if self._file_handler is not None:
            try:
                logging.getLogger().removeHandler(self._file_handler)
                self._file_handler.close()
            except Exception:
                pass
            self._file_handler = None

        if log_path is None or not log_path.exists() or project_path is None:
            return

        from avgeosys.gdrive_log import upload_log_async
        project_label = project_path.name.replace(" ", "_")
        dest_name = f"{log_path.stem}__{project_label}.log"
        upload_log_async(log_path, dest_name)

    def _save_settings(self) -> None:
        """Persiste as configurações atuais da GUI em disco."""
        from avgeosys.core.settings import save as _save
        _save({
            "solution_type": self._solution_type_var.get(),
            "elevation_mask": self._elev_mask_var.get(),
            "ar_threshold": self._ar_threshold_var.get(),
            "nav_systems": self._nav_systems_var.get(),
            "orthometric": self._orthometric_var.get(),
            "last_project": self._path_var.get(),
            "update_channel": self._settings.get("update_channel", "stable"),
            "recent_projects": self._settings.get("recent_projects", []),
            "backup_exif": self._backup_exif_var.get(),
        })

    def _on_close(self) -> None:
        """Handle window close: save settings, request cancel, wait briefly for worker."""
        self._save_settings()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._cancel_event.set()
            self._worker_thread.join(timeout=3.0)
        self.root.destroy()

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def _check_for_updates(self) -> None:
        """Inicia verificação de atualização em segundo plano."""
        from avgeosys import __version__
        from avgeosys.updater import check_for_update_async

        channel = self._settings.get("update_channel", "stable")

        def _on_result(info) -> None:
            if info is not None:
                self.root.after(0, lambda: self._show_update_banner(info))

        check_for_update_async(__version__, channel=channel, callback=_on_result)

    # ------------------------------------------------------------------
    # Pipeline implementations
    # ------------------------------------------------------------------

    def _build_config_override(self) -> dict:
        """Build config_override dict from GUI PPK parameter fields."""
        override: dict = {}
        try:
            override["elevation_mask"] = int(self._elev_mask_var.get())
        except (ValueError, AttributeError):
            pass
        try:
            override["ar_threshold"] = float(self._ar_threshold_var.get())
        except (ValueError, AttributeError):
            pass
        nav = self._nav_systems_var.get().strip()
        if nav:
            override["nav_systems"] = nav
        return override

    def _pipeline_ppk_only(self, project_path: Path) -> None:
        """Roda PPK e, em seguida, interpolação (para deixar o Mapa disponível)."""
        from avgeosys.core.ppk import process_all_folders
        from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
        from avgeosys.core.interpolator import interpolate_positions, load_pos_data, preprocess_and_read_mrk
        from avgeosys.cli.cli import _flight_folders, _find_mrk_for_folder, _find_pos_for_folder
        from avgeosys import config as _cfg

        # --- PPK (0 → 75%) ---
        self._set_progress(2)
        self.root.after(0, lambda: self._set_status("● PPK em progresso...", STATUS_RUN))

        def _ppk_progress(done: int, total: int) -> None:
            self._set_progress(2 + done / total * 70 if total else 72)

        process_all_folders(
            project_path,
            self._build_config_override(),
            solution_type=self._solution_type_var.get(),
            progress_callback=_ppk_progress,
        )
        if self._cancel_event.is_set():
            return
        self._set_progress(75)

        # --- Interpolação (75 → 100%) — silenciosa se não houver MRK ---
        self.root.after(0, lambda: self._set_status("● Interpolando posições...", STATUS_RUN))
        orthometric = self._orthometric_var.get()
        folders = _flight_folders(project_path)

        def _interp_folder(folder):
            mrk_path = _find_mrk_for_folder(folder)
            pos_path = _find_pos_for_folder(folder)
            if not mrk_path or not pos_path:
                return []
            try:
                mrk_df = preprocess_and_read_mrk(mrk_path)
                pos_df = load_pos_data(pos_path)
                if pos_df.empty:
                    return []
                # 8. Validate photo count vs MRK
                jpg_count = sum(1 for f in folder.iterdir()
                                if f.suffix.upper() in (".JPG", ".JPEG"))
                if jpg_count > 0 and jpg_count != len(mrk_df):
                    logging.getLogger(__name__).warning(
                        "  %s: %d eventos no MRK vs %d fotos JPEG na pasta — "
                        "verifique se todas as fotos estão presentes.",
                        folder.name, len(mrk_df), jpg_count,
                    )
                records = interpolate_positions(mrk_df, pos_df, orthometric=orthometric)
                rel_folder = folder.relative_to(project_path).as_posix()
                for rec in records:
                    rec["folder"] = rel_folder
                return records
            except Exception as exc:
                logging.getLogger(__name__).warning("Interpolação ignorada para %s: %s", folder.name, exc)
                return []

        all_results = []
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as executor:
            futures = {executor.submit(_interp_folder, f): f for f in folders}
            done_interp = 0
            for future in _as_completed(futures):
                done_interp += 1
                recs = future.result()
                if recs:
                    all_results.extend(recs)
                self._set_progress(75 + done_interp / max(len(folders), 1) * 22)

        if all_results:
            import json as _json
            from avgeosys.core.interpolator import _write_csv
            output_dir = project_path / "PPK_Results"
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / "interpolated_data.json"
            with open(json_path, "w", encoding="utf-8") as fh:
                _json.dump(all_results, fh, indent=2, ensure_ascii=False)
            _write_csv(all_results, output_dir / "interpolated_data.csv")
            logging.getLogger(__name__).info(
                "Interpolação concluída: %d fotos — Mapa disponível.", len(all_results)
            )
            # 2. Per-folder stats popup
            self.root.after(0, lambda r=list(all_results): self._show_ppk_stats(r))
        self._set_progress(100)
        # 7. Auto-open quality map
        if all_results:
            self.root.after(500, self._open_quality_map)

    def _pipeline_geotag_only(self, project_path: Path) -> None:
        """Interpolate (if needed) then geotag all folders."""
        from avgeosys.core.exif import batch_update_exif

        output_dir = project_path / "PPK_Results"
        json_path = output_dir / "interpolated_data.json"

        if not json_path.exists():
            raise FileNotFoundError(
                "interpolated_data.json não encontrado. Execute PPK + Interpolação primeiro."
            )

        self.root.after(0, lambda: self._set_status("● Geotag em progresso...", STATUS_RUN))
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)

        # Agrupar por pasta para log detalhado por pasta
        by_folder: dict = {}
        for rec in data:
            by_folder.setdefault(rec.get("folder", ""), []).append(rec)

        _log = logging.getLogger(__name__)
        total_photos = len(data)
        _log.info("Iniciando Geotag: %d foto(s) em %d pasta(s)...", total_photos, len(by_folder))

        total_written = 0
        total_skipped = 0
        done_so_far = 0

        for folder_key, folder_records in by_folder.items():
            if self._cancel_event.is_set():
                break
            folder_label = folder_key if folder_key else "raiz do projeto"
            _log.info("  Pasta '%s': %d foto(s)...", folder_label, len(folder_records))

            def _progress(done: int, total_: int, _base: int = done_so_far) -> None:
                self._set_progress((_base + done) / total_photos * 100 if total_photos else 100)

            backup_dir = (project_path / "PPK_Backup") if self._backup_exif_var.get() else None
            w, s = batch_update_exif(
                folder_records,
                project_path,
                cancel_event=self._cancel_event,
                progress_callback=_progress,
                backup_dir=backup_dir,
            )
            total_written += w
            total_skipped += s
            done_so_far += len(folder_records)
            _log.info("  Pasta '%s' concluída: %d gravada(s), %d ignorada(s).", folder_label, w, s)

        _log.info("Geotag EXIF concluído: %d gravado(s), %d ignorado(s).", total_written, total_skipped)
        if total_written == 0 and total_skipped > 0:
            _log.warning(
                "Nenhuma imagem atualizada — verifique se as imagens estão em "
                "%s e se o caminho do projeto está correto.", project_path
            )
        status_msg = f"● Geotag: {total_written} gravado(s), {total_skipped} ignorado(s)"
        _status_color = STATUS_OK if total_written > 0 else STATUS_ERR
        self.root.after(0, lambda m=status_msg, c=_status_color: self._set_status(m, c))

    def _pipeline_all(self, project_path: Path) -> None:
        from avgeosys.core.exif import batch_update_exif
        from avgeosys.core.ppk import process_all_folders
        from avgeosys.core.report import generate_report_and_kmz

        # --- Step 1: PPK com progresso granular (~70% do tempo total) ---
        self.root.after(0, lambda: self._set_status("● PPK em progresso...", STATUS_RUN))
        self._set_progress(2)

        def _ppk_progress(done: int, total: int) -> None:
            self._set_progress(2 + done / total * 65 if total else 67)

        process_all_folders(
            project_path,
            self._build_config_override(),
            solution_type=self._solution_type_var.get(),
            progress_callback=_ppk_progress,
        )
        if self._cancel_event.is_set():
            return
        self._set_progress(70)

        # --- Step 2: Interpolação paralela (~10%) ---
        self.root.after(
            0, lambda: self._set_status("● Interpolando posições...", STATUS_RUN)
        )
        from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

        from avgeosys.core.interpolator import (
            interpolate_positions,
            load_pos_data,
            preprocess_and_read_mrk,
        )
        from avgeosys.cli.cli import _flight_folders, _find_mrk_for_folder, _find_pos_for_folder
        from avgeosys import config as _cfg

        folders = _flight_folders(project_path)
        orthometric = self._orthometric_var.get()

        def _interp_folder(folder):
            mrk_path = _find_mrk_for_folder(folder)
            pos_path = _find_pos_for_folder(folder)
            if not mrk_path or not pos_path:
                return []
            mrk_df = preprocess_and_read_mrk(mrk_path)
            pos_df = load_pos_data(pos_path)
            if pos_df.empty:
                return []
            # 8. Validate photo count vs MRK
            jpg_count = sum(1 for f in folder.iterdir()
                            if f.suffix.upper() in (".JPG", ".JPEG"))
            if jpg_count > 0 and jpg_count != len(mrk_df):
                logging.getLogger(__name__).warning(
                    "  %s: %d eventos no MRK vs %d fotos JPEG na pasta — "
                    "verifique se todas as fotos estão presentes.",
                    folder.name, len(mrk_df), jpg_count,
                )
            records = interpolate_positions(mrk_df, pos_df, orthometric=orthometric)
            rel_folder = folder.relative_to(project_path).as_posix()
            for rec in records:
                rec["folder"] = rel_folder
            return records

        all_results = []
        with ThreadPoolExecutor(max_workers=_cfg.MAX_WORKERS) as executor:
            futures = {executor.submit(_interp_folder, f): f for f in folders}
            for future in _as_completed(futures):
                if self._cancel_event.is_set():
                    break
                recs = future.result()
                if recs:
                    all_results.extend(recs)

        if not all_results:
            raise RuntimeError("Nenhum resultado de interpolação — verifique os arquivos PPK.")

        output_dir = project_path / "PPK_Results"
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "interpolated_data.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False)
        from avgeosys.core.interpolator import _write_csv
        _write_csv(all_results, output_dir / "interpolated_data.csv")

        self._set_progress(80)

        # --- Step 3: Geotag (~15%) ---
        self.root.after(0, lambda: self._set_status("● Geotag em progresso...", STATUS_RUN))
        _log_geo = logging.getLogger(__name__)
        _by_folder: dict = {}
        for _rec in all_results:
            _by_folder.setdefault(_rec.get("folder", ""), []).append(_rec)
        _geo_total = len(all_results)
        _log_geo.info("Iniciando Geotag: %d foto(s) em %d pasta(s)...", _geo_total, len(_by_folder))
        _geo_written = 0
        _geo_skipped = 0
        _geo_done = 0

        for _fk, _frecs in _by_folder.items():
            if self._cancel_event.is_set():
                break
            _flabel = _fk if _fk else "raiz do projeto"
            _log_geo.info("  Pasta '%s': %d foto(s)...", _flabel, len(_frecs))

            def _progress(done: int, total_: int, _b: int = _geo_done) -> None:
                base = 80.0
                span = 15.0
                pct = base + ((_b + done) / _geo_total * span) if _geo_total else base + span
                self._set_progress(pct)

            _backup_dir = (project_path / "PPK_Backup") if self._backup_exif_var.get() else None
            _w, _s = batch_update_exif(
                _frecs,
                project_path,
                cancel_event=self._cancel_event,
                progress_callback=_progress,
                backup_dir=_backup_dir,
            )
            _geo_written += _w
            _geo_skipped += _s
            _geo_done += len(_frecs)
            _log_geo.info("  Pasta '%s' concluída: %d gravada(s), %d ignorada(s).", _flabel, _w, _s)

        _log_geo.info("Geotag EXIF concluído: %d gravado(s), %d ignorado(s).", _geo_written, _geo_skipped)
        if self._cancel_event.is_set():
            return
        self._set_progress(95)

        # --- Step 4: Report (~5%) ---
        self.root.after(0, lambda: self._set_status("● Gerando relatório...", STATUS_RUN))
        report_txt, _kmz_interp, _kmz_exif = generate_report_and_kmz(all_results, output_dir)
        self._set_progress(100)

        # 2. Per-folder stats
        self.root.after(0, lambda r=list(all_results): self._show_ppk_stats(r))
        # 7. Auto-open report + map after Tudo
        import webbrowser as _wb
        self.root.after(500, lambda: _wb.open(report_txt.as_uri()))
        self.root.after(800, self._open_quality_map)

    # ------------------------------------------------------------------
    # Quality map
    # ------------------------------------------------------------------

    def _open_quality_map(self) -> None:
        """Abre mapa de qualidade PPK no navegador (folium) ou em janela (matplotlib)."""
        project_str = self._path_var.get().strip()
        if not project_str:
            self._set_status("● Erro: selecione um diretório", STATUS_ERR)
            return

        json_path = Path(project_str) / "PPK_Results" / "interpolated_data.json"
        if not json_path.exists():
            self._set_status(
                "● interpolated_data.json não encontrado — execute o pipeline primeiro",
                STATUS_ERR,
            )
            return

        import json as _json
        with open(json_path, encoding="utf-8") as fh:
            data = _json.load(fh)

        if not data:
            self._set_status("● Sem dados para exibir", STATUS_ERR)
            return

        # --- Tenta folium (mapa com basemap no navegador) ---
        try:
            import webbrowser
            import folium
            from folium.plugins import MarkerCluster

            quality_labels = {1: "Fixed", 2: "Float", 3: "SBAS", 4: "DGPS", 5: "Single", 6: "PPP"}
            quality_colors = {1: "green", 2: "orange", 3: "blue", 4: "purple", 5: "red", 6: "darkblue"}

            total = len(data)
            fixed_n  = sum(1 for r in data if r.get("quality") == 1)
            float_n  = sum(1 for r in data if r.get("quality") == 2)
            single_n = sum(1 for r in data if r.get("quality") == 5)
            other_n  = total - fixed_n - float_n - single_n
            fixed_pct = fixed_n / total * 100 if total else 0.0
            single_pct = single_n / total * 100 if total else 0.0

            center_lat = sum(r["latitude"] for r in data) / len(data)
            center_lon = sum(r["longitude"] for r in data) / len(data)

            m = folium.Map(location=[center_lat, center_lon], zoom_start=15)

            # Alerta vermelho se Single domina
            single_alert = ""
            if single_pct > 50:
                single_alert = (
                    f'<br><span style="color:#c0392b;font-weight:bold;font-size:12px;">'
                    f'⚠ {single_pct:.0f}% SINGLE — GPS autônomo sem correção PPK! '
                    f'Verifique sobreposição temporal com a base.</span>'
                )

            # Título flutuante no topo do mapa
            title_html = (
                '<div style="position:fixed;top:12px;left:50%;transform:translateX(-50%);'
                'z-index:9999;background:#fff;padding:8px 18px;border-radius:6px;'
                'box-shadow:2px 2px 8px rgba(0,0,0,0.35);font-family:Arial,sans-serif;'
                'text-align:center;">'
                '<span style="font-size:14px;font-weight:bold;color:#1a1a1a;">'
                'Posições PPK Processadas — AVGeoSys</span><br>'
                f'<span style="font-size:11px;color:#555;">'
                f'Total: {total} fotos &nbsp;|&nbsp; '
                f'<span style="color:#2a7a2a;font-weight:bold;">&#9679; Fixed: {fixed_n} ({fixed_pct:.1f}%)</span>'
                f' &nbsp;|&nbsp; '
                f'<span style="color:#d28010;">&#9679; Float: {float_n}</span>'
                f' &nbsp;|&nbsp; '
                f'<span style="color:#c0392b;">&#9679; Single: {single_n}</span>'
                + (f' &nbsp;|&nbsp; Outros: {other_n}' if other_n > 0 else '')
                + f'</span>'
                + single_alert
                + f'<br><span style="font-size:10px;color:#888;">'
                f'Coordenadas derivadas do processamento PPK (rnx2rtkp) — não são posições GPS brutas do MRK'
                f'</span>'
                '</div>'
            )
            m.get_root().html.add_child(folium.Element(title_html))

            # Layer por qualidade
            # Para missões grandes (>1000 pontos) usa MarkerCluster por layer —
            # 10-50× mais rápido no browser que CircleMarker individual por ponto.
            use_cluster = total > 1000
            for q, label in quality_labels.items():
                color = quality_colors[q]
                pts = [r for r in data if r.get("quality") == q]
                if not pts:
                    continue
                layer = folium.FeatureGroup(name=f"{label} ({len(pts)})")
                target = MarkerCluster().add_to(layer) if use_cluster else layer
                for r in pts:
                    folium.CircleMarker(
                        location=[r["latitude"], r["longitude"]],
                        radius=5,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.8,
                        popup=folium.Popup(
                            f"<b>{r['filename']}</b><br>"
                            f"<b>Posição PPK</b> — Qualidade: <b>{label}</b><br>"
                            f"Lat: {r['latitude']:.7f}<br>"
                            f"Lon: {r['longitude']:.7f}<br>"
                            f"Alt: {r['height']:.3f} m<br>"
                            f"Pasta: {r.get('folder','')}",
                            max_width=280,
                        ),
                        tooltip=f"{r['filename']} [{label}]",
                    ).add_to(target)
                layer.add_to(m)

            folium.LayerControl(collapsed=False).add_to(m)

            html_path = Path(project_str) / "PPK_Results" / "mapa_qualidade.html"
            m.save(str(html_path))
            webbrowser.open(html_path.as_uri())
            self._set_status("● Mapa aberto no navegador", STATUS_OK)
            return

        except ImportError:
            pass  # folium não disponível — usa matplotlib
        except Exception as exc:
            logging.getLogger(__name__).warning("Falha ao gerar mapa folium: %s", exc)

        # --- Fallback: matplotlib scatter integrado ---
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure

            quality_labels = {1: "Fixed", 2: "Float", 3: "SBAS", 4: "DGPS", 5: "Single", 6: "PPP"}

            win = tk.Toplevel(self.root)
            win.title("Distribuição de Qualidade PPK")
            win.configure(bg=BG_DARK)
            win.minsize(700, 520)

            fig = Figure(figsize=(8, 5.5), facecolor=BG_DARK, tight_layout=True)
            ax = fig.add_subplot(111, facecolor=BG_PANEL)

            for q in (1, 2, 3, 4, 5, 6):
                pts = [(r["longitude"], r["latitude"]) for r in data if r.get("quality") == q]
                if not pts:
                    continue
                color = {1: ACCENT_PPK, 2: "#FFA500", 3: "#2196F3", 4: "#9C27B0", 5: STATUS_ERR, 6: "#1565C0"}.get(q, "#888888")
                lons, lats = zip(*pts)
                ax.scatter(
                    lons, lats,
                    c=color,
                    label=f"{quality_labels[q]}  ({len(pts)})",
                    s=10,
                    alpha=0.85,
                    linewidths=0,
                )

            ax.set_xlabel("Longitude", color=FG_TEXT)
            ax.set_ylabel("Latitude", color=FG_TEXT)
            ax.set_title("Distribuição de Qualidade PPK", color=FG_TEXT, pad=8)
            ax.tick_params(colors=FG_TEXT, labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor(FG_DIM)
            ax.legend(facecolor=BG_PANEL, labelcolor=FG_TEXT, edgecolor=FG_DIM, markerscale=2)

            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.draw()
            toolbar = NavigationToolbar2Tk(canvas, win)
            toolbar.configure(bg=BG_DARK)
            toolbar.update()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 4))

        except Exception as exc:
            logging.getLogger(__name__).error("Erro ao abrir mapa: %s", exc, exc_info=True)
            self._set_status(f"● Erro ao abrir mapa: {exc}", STATUS_ERR)

    # ------------------------------------------------------------------
    # FieldUpload pipeline
    # ------------------------------------------------------------------

    def _pipeline_fieldupload(self, project_path: Path) -> None:
        import tkinter.messagebox as _mb
        from avgeosys.core.fieldupload import prepare_field_upload

        # Confirmação — operação destrutiva (remove arquivos .pos/.tmp e PPK_Results/)
        confirm = _mb.askokcancel(
            "Confirmar FieldUpload",
            "Esta operação irá:\n"
            "• Remover arquivos .pos e .tmp das pastas de voo\n"
            "• Remover a pasta PPK_Results/\n"
            "• Zipar a base RINEX na 1ª pasta de voo\n\n"
            "Os arquivos originais (imagens, .obs, .nav, .bin, .MRK) serão mantidos.\n\n"
            "Deseja continuar?",
        )
        if not confirm:
            self.root.after(0, lambda: self._set_status("● Cancelado", STATUS_ERR))
            return

        self.root.after(0, lambda: self._set_status("● Preparando FieldUpload...", STATUS_RUN))
        self._set_progress(5)

        def _progress(done: int, total: int) -> None:
            self._set_progress(5 + done / total * 90 if total else 95)

        folders, files_removed, base = prepare_field_upload(
            project_path,
            cancel_event=self._cancel_event,
            progress_callback=_progress,
        )
        self._set_progress(100)
        logging.getLogger(__name__).info(
            "FieldUpload: %d pasta(s) limpas, %d arquivo(s) removido(s), %d base zipado(s)",
            folders, files_removed, base,
        )

        # Abre o diretório do projeto no Explorer
        import subprocess as _sp, sys as _sys
        if _sys.platform == "win32":
            _sp.Popen(["explorer", str(project_path)])

    # ------------------------------------------------------------------
    # Per-folder stats popup (item 2)
    # ------------------------------------------------------------------

    def _show_ppk_stats(self, data: list) -> None:
        """Show per-folder quality stats in a small Toplevel after PPK."""
        if not data:
            return
        from collections import defaultdict
        QUALITY_LABELS = {1: "Fixed", 2: "Float", 3: "SBAS", 4: "DGPS", 5: "Single", 6: "PPP"}

        by_folder: dict = defaultdict(list)
        for rec in data:
            by_folder[rec.get("folder", "(raiz)")].append(rec)

        win = tk.Toplevel(self.root)
        win.title("Estatísticas PPK por Pasta")
        win.configure(bg=BG_DARK)
        win.resizable(False, False)

        # Header
        tk.Label(win, text="Qualidade PPK por pasta de voo", bg=BG_DARK,
                 fg=FG_TEXT, font=FONT_TITLE, pady=8).pack(fill="x", padx=12)

        frame = tk.Frame(win, bg=BG_PANEL)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Column headers
        headers = ["Pasta", "Fotos", "Fixed%", "Float%", "Single%"]
        col_widths = [30, 6, 8, 8, 8]
        for col, (h, w) in enumerate(zip(headers, col_widths)):
            tk.Label(frame, text=h, bg=BG_PANEL, fg=FG_DIM, font=FONT_MONO,
                     width=w, anchor="e").grid(row=0, column=col, padx=4, pady=(4, 2))

        for row_idx, (folder_name, recs) in enumerate(sorted(by_folder.items()), start=1):
            n = len(recs)
            fixed = sum(1 for r in recs if r.get("quality") == 1)
            float_ = sum(1 for r in recs if r.get("quality") == 2)
            single = sum(1 for r in recs if r.get("quality") == 5)
            single_pct = single / n * 100 if n else 0

            label = folder_name if len(folder_name) <= 28 else "..." + folder_name[-25:]
            color = STATUS_ERR if single_pct > 50 else FG_TEXT
            vals = [
                label,
                str(n),
                f"{fixed/n*100:.0f}%" if n else "-",
                f"{float_/n*100:.0f}%" if n else "-",
                f"{single_pct:.0f}%" if n else "-",
            ]
            for col, (v, w) in enumerate(zip(vals, col_widths)):
                tk.Label(frame, text=v, bg=BG_PANEL, fg=color, font=FONT_MONO,
                         width=w, anchor="e" if col > 0 else "w").grid(
                    row=row_idx, column=col, padx=4, pady=1)

        # Total row
        total = len(data)
        t_fixed = sum(1 for r in data if r.get("quality") == 1)
        t_float = sum(1 for r in data if r.get("quality") == 2)
        t_single = sum(1 for r in data if r.get("quality") == 5)
        last_row = len(by_folder) + 1
        tk.Frame(frame, bg=FG_DIM, height=1).grid(
            row=last_row, column=0, columnspan=5, sticky="ew", pady=4)
        vals_total = [
            "TOTAL", str(total),
            f"{t_fixed/total*100:.0f}%" if total else "-",
            f"{t_float/total*100:.0f}%" if total else "-",
            f"{t_single/total*100:.0f}%" if total else "-",
        ]
        for col, (v, w) in enumerate(zip(vals_total, col_widths)):
            tk.Label(frame, text=v, bg=BG_PANEL, fg=ACCENT_GREEN, font=FONT_TITLE,
                     width=w, anchor="e" if col > 0 else "w").grid(
                row=last_row + 1, column=col, padx=4, pady=(0, 6))

        tk.Button(win, text="Fechar", command=win.destroy,
                  bg=BG_PANEL, fg=FG_TEXT, font=FONT_UI, relief="flat",
                  cursor="hand2", padx=16, pady=4).pack(pady=(0, 10))

        win.update_idletasks()
        # Center on parent
        px = self.root.winfo_rootx() + self.root.winfo_width() // 2
        py = self.root.winfo_rooty() + self.root.winfo_height() // 2
        win.geometry(f"+{px - win.winfo_width()//2}+{py - win.winfo_height()//2}")

    # ------------------------------------------------------------------
    # Drag-and-drop (Windows HWND subclassing, item 6)
    # ------------------------------------------------------------------

    def _setup_drag_drop(self) -> None:
        """Enable folder drag-and-drop on the main window (Windows only)."""
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes

            WM_DROPFILES = 0x0233
            GWL_WNDPROC = -4

            shell32 = ctypes.windll.shell32
            user32 = ctypes.windll.user32

            # Set correct restype for 64-bit Windows (LRESULT = pointer-sized signed int)
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.CallWindowProcW.restype = ctypes.c_ssize_t

            hwnd = user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            if not hwnd:
                return

            shell32.DragAcceptFiles(hwnd, True)

            old_addr = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)
            if not old_addr:
                return  # Could not get old wndproc — skip subclassing

            # LRESULT must be c_ssize_t (64-bit) on x64 Windows, NOT c_long (32-bit)
            WNDPROC = ctypes.WINFUNCTYPE(
                ctypes.c_ssize_t,
                ctypes.wintypes.HWND,
                ctypes.c_uint,
                ctypes.wintypes.WPARAM,
                ctypes.wintypes.LPARAM,
            )

            @WNDPROC
            def _wndproc(hwnd_: int, msg: int, wp: int, lp: int) -> int:
                if msg == WM_DROPFILES:
                    try:
                        buf = ctypes.create_unicode_buffer(4096)
                        shell32.DragQueryFileW(wp, 0, buf, 4096)
                        path = buf.value
                        if path:
                            p = Path(path)
                            folder = p if p.is_dir() else p.parent
                            self.root.after(0, lambda f=str(folder): self._set_project_path(f))
                        shell32.DragFinish(wp)
                    except Exception:
                        pass
                    return 0
                return user32.CallWindowProcW(old_addr, hwnd_, msg, wp, lp)

            self._wndproc_ref = _wndproc  # prevent GC
            user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, _wndproc)
            logging.getLogger(__name__).debug("Drag-and-drop de pasta habilitado.")
        except Exception as exc:
            logging.getLogger(__name__).debug("Drag-and-drop não disponível: %s", exc)

    # ------------------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = AVGeoSysUI()
    app.run()


if __name__ == "__main__":
    main()
