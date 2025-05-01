"""
Interface gráfica usando Tkinter.
"""

import logging
import sys
import json
import shutil
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from threading import Thread

import simplekml

from avgeosys.core.ppk import (
    find_base_files,
    process_single_folder,
)
from avgeosys.core.interpolator import (
    preprocess_and_read_mrk,
    load_pos_data,
    interpolate_positions,
)
from avgeosys.core.exif import (
    extract_exif_coordinates,
    update_exif,
)
from avgeosys.core.report import generate_report_and_kmz


class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.see(tk.END)


class AVGeoSysUI:
    def __init__(self):
        self.dark_bg = "#2e2e2e"
        self.dark_fg = "#ffffff"
        self.btn_bg = "#444444"
        self.btn_fg = "#ffffff"

        self.root = tk.Tk()
        self.root.title("AVGeoSys - PPK & EXIF Tool")

        base_dir = (
            Path(sys._MEIPASS)
            if hasattr(sys, "_MEIPASS")
            else Path(__file__).parent
        )
        ico = base_dir / "AVGeoSysIcon.ico"
        png = base_dir / "AVGeoSysIcon.png"
        try:
            self.root.iconbitmap(str(ico))
        except Exception:
            logging.warning("Não foi possível carregar ícone .ico")
        try:
            img = tk.PhotoImage(file=str(png))
            self.root.iconphoto(False, img)
        except Exception as e:
            logging.warning(f"Não foi possível carregar ícone .png: {e}")

        self.root.config(bg=self.dark_bg)
        self.directory_var = tk.StringVar()
        self._build_ui()
        self._setup_logging()

    def _build_ui(self):
        frame_dir = tk.Frame(self.root, bg=self.dark_bg)
        frame_dir.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            frame_dir,
            text="Diretório Raiz:",
            bg=self.dark_bg,
            fg=self.dark_fg,
        ).pack(side=tk.LEFT)

        tk.Entry(
            frame_dir,
            textvariable=self.directory_var,
            bg=self.dark_bg,
            fg=self.dark_fg,
            insertbackground=self.dark_fg,
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        tk.Button(
            frame_dir,
            text="Selecionar",
            command=self.select_directory,
            bg=self.btn_bg,
            fg=self.btn_fg,
        ).pack(side=tk.RIGHT)

        frame_btn = tk.Frame(self.root, bg=self.dark_bg)
        frame_btn.pack(fill=tk.X, padx=10, pady=5)

        self.btn_ppk = tk.Button(
            frame_btn,
            text="Processamento PPK",
            command=self.run_ppk,
            bg=self.btn_bg,
            fg=self.btn_fg,
        )
        self.btn_ppk.pack(side=tk.LEFT, padx=5)

        self.btn_geotag = tk.Button(
            frame_btn,
            text="Geotagging",
            command=self.run_geotagging,
            bg=self.btn_bg,
            fg=self.btn_fg,
        )
        self.btn_geotag.pack(side=tk.LEFT, padx=5)

        self.btn_upload = tk.Button(
            frame_btn,
            text="FieldUpload",
            command=self.run_field_upload,
            bg=self.btn_bg,
            fg=self.btn_fg,
        )
        self.btn_upload.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(
            self.root,
            orient="horizontal",
            mode="determinate",
        )
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 5))

        self.status = tk.Label(
            self.root,
            text="Pronto.",
            anchor="w",
            bg=self.dark_bg,
            fg="green",
        )
        self.status.pack(fill=tk.X, padx=10, pady=5)

        self.log_box = tk.Text(
            self.root,
            height=15,
            bg=self.dark_bg,
            fg=self.dark_fg,
            insertbackground=self.dark_fg,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _setup_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = TextHandler(self.log_box)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)

    def select_directory(self):
        folder = filedialog.askdirectory()
        if folder:
            logging.info(f"Diretório selecionado: {folder}")
            self.directory_var.set(folder)

    def _disable_buttons(self):
        for btn in (self.btn_ppk, self.btn_geotag, self.btn_upload):
            btn.config(state=tk.DISABLED)

    def _enable_buttons(self):
        for btn in (self.btn_ppk, self.btn_geotag, self.btn_upload):
            btn.config(state=tk.NORMAL)

    def _run_task(self, target, *args):
        def task():
            try:
                self.status.config(text="Processando...", fg="red")
                self._disable_buttons()
                target(*args)
                self.status.config(text="Pronto.", fg="green")
            except Exception as e:
                logging.error(f"Erro na tarefa: {e}")
                self.status.config(text="Erro.", fg="red")
            finally:
                self._enable_buttons()

        Thread(target=task, daemon=True).start()

    def run_ppk(self):
        root = Path(self.directory_var.get())
        if not root.is_dir():
            messagebox.showerror(
                "Erro", "Selecione um diretório válido."
            )
            return

        logging.info("Iniciando PPK...")

        def fluxo(folder: Path):
            base_obs, base_nav = find_base_files(folder)
            dirs = sorted(
                {p.parent for p in folder.rglob("*_Timestamp.MRK")}
            )
            total = len(dirs)
            self.progress.config(maximum=total, value=0)

            for idx, sub in enumerate(dirs, 1):
                pos_file = process_single_folder(
                    sub, base_obs, base_nav
                )
                mrk = next(sub.glob("*_Timestamp.MRK"))
                mrk_df = preprocess_and_read_mrk(mrk, sub)
                pos_df = load_pos_data(pos_file)
                if not mrk_df.empty and not pos_df.empty:
                    interp = interpolate_positions(pos_df, mrk_df)
                    out = sub / "interpolated_data.json"
                    out.write_text(
                        json.dumps(interp, indent=4)
                    )
                self.progress["value"] = idx

            generate_report_and_kmz(folder)
            self.progress["value"] = 0

        self._run_task(fluxo, root)

    def run_geotagging(self):
        root = Path(self.directory_var.get())
        if not root.is_dir():
            messagebox.showerror(
                "Erro", "Selecione um diretório válido."
            )
            return

        logging.info("Iniciando Geotagging...")

        def geo_flow(folder: Path):
            for res_dir in folder.rglob("PPK_Results"):
                data = json.loads(
                    (res_dir / "interpolated_data.json").read_text()
                )
                for entry in data:
                    photo = next(
                        res_dir.parent.glob(
                            f"*{entry['photo']}"
                        ),
                        None,
                    )
                    if photo:
                        update_exif(
                            photo,
                            entry["lat"],
                            entry["lon"],
                            entry["height"],
                        )

            pts = extract_exif_coordinates(folder)
            kmz = folder / "compilado_exif_data.kmz"
            kml = simplekml.Kml()
            for pt in pts:
                kml.newpoint(
                    coords=[(pt["lon"], pt["lat"])]
                )
            kml.savekmz(str(kmz))
            logging.info(
                f"KMZ de EXIF salvo em: {kmz.name}"
            )

        self._run_task(geo_flow, root)

    def run_field_upload(self):
        root = Path(self.directory_var.get())
        if not root.is_dir():
            messagebox.showerror(
                "Erro", "Selecione um diretório válido."
            )
            return

        logging.info("Iniciando FieldUpload...")

        def upload_flow(folder: Path):
            for res in folder.rglob("PPK_Results"):
                shutil.rmtree(res)
                logging.info(f"Removido: {res}")

            candidates = []
            for ext in ("B", "O", "P"):
                lst = list(folder.glob(f"*[0-9][0-9]{ext}"))
                if lst:
                    latest = max(
                        lst,
                        key=lambda p: int(p.suffix[1:3])
                    )
                    candidates.append(latest)

            root_sub = None
            for sub in sorted(folder.iterdir()):
                if sub.is_dir() and any(sub.glob("*.jpg")):
                    root_sub = sub
                    logging.info(
                        f"Primeira subpasta para upload: {sub}"
                    )
                    break

            if not root_sub:
                logging.error(
                    "Nenhuma subpasta com fotos processadas "
                    "encontrada."
                )
                return

            zip_path = root_sub / "base_rinex.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for bf in candidates:
                    zf.write(bf, bf.name)
                    logging.info(f"ZIP: {bf.name}")

            for bf in candidates:
                bf.unlink()

            for fn in (
                "compilado_exif_data.kmz",
                "relatorio_processamento.txt",
                "resultado_interpolado.kmz",
            ):
                fp = folder / fn
                if fp.exists():
                    fp.unlink()

            logging.info("FieldUpload concluído.")

        self._run_task(upload_flow, root)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    AVGeoSysUI().run()
