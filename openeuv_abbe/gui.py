#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tk desktop interface for OpenEUV Abbe."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402

from . import backend  # noqa: E402


APP_DIR = Path(__file__).resolve().parent


class OpenEUVAbbeGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenEUV Abbe - Strict-field EUV aerial imaging")
        self.geometry("1480x900")
        self.minsize(1200, 760)

        self.msg_queue: queue.Queue = queue.Queue()
        self.last_result: backend.SimulationResult | None = None
        self.last_params: backend.SimulationParams | None = None
        self.last_compare: dict | None = None

        self._build_variables()
        self._build_layout()
        self.after(100, self._poll_queue)

    def _build_variables(self) -> None:
        p = backend.SimulationParams()

        self.mask_path_var = tk.StringVar(value="")
        self.ideal_focus_var = tk.BooleanVar(value=True)
        self.cutline_axis_var = tk.StringVar(value="x")
        self.cutline_index_var = tk.StringVar(value="")

        self.vars: dict[str, tk.Variable] = {
            "wavelength_nm": tk.DoubleVar(value=p.wavelength_nm),
            "na": tk.DoubleVar(value=p.na),
            "magnification_x": tk.IntVar(value=p.magnification_x),
            "magnification_y": tk.IntVar(value=p.magnification_y),
            "central_obscuration": tk.DoubleVar(value=p.central_obscuration),
            "incidence_angle_deg": tk.DoubleVar(value=p.incidence_angle_deg),
            "azimuthal_angle_deg": tk.DoubleVar(value=p.azimuthal_angle_deg),
            "defocus_nm": tk.DoubleVar(value=p.defocus_nm),
            "illumination": tk.StringVar(value=p.illumination),
            "sigma_in": tk.DoubleVar(value=p.sigma_in),
            "sigma_out": tk.DoubleVar(value=p.sigma_out),
            "pole_open_angle_deg": tk.DoubleVar(value=p.pole_open_angle_deg),
            "source_mesh_deg": tk.DoubleVar(value=p.source_mesh_deg),
            "polarization": tk.StringVar(value=p.polarization),
            "pol_angle_deg": tk.DoubleVar(value=p.pol_angle_deg),
            "mask_width_nm": tk.IntVar(value=p.mask_width_nm),
            "mask_height_nm": tk.IntVar(value=p.mask_height_nm),
            "mask_threshold": tk.DoubleVar(value=p.mask_threshold),
            "invert_mask": tk.BooleanVar(value=p.invert_mask),
            "absorber_thickness_nm": tk.DoubleVar(value=p.absorber_thickness_nm),
            "absorber_n": tk.DoubleVar(value=p.absorber_n),
            "absorber_k": tk.DoubleVar(value=p.absorber_k),
            "multilayer_periods": tk.IntVar(value=p.multilayer_periods),
            "mo_thickness_nm": tk.DoubleVar(value=p.mo_thickness_nm),
            "mo_n": tk.DoubleVar(value=p.mo_n),
            "mo_k": tk.DoubleVar(value=p.mo_k),
            "si_thickness_nm": tk.DoubleVar(value=p.si_thickness_nm),
            "si_n": tk.DoubleVar(value=p.si_n),
            "si_k": tk.DoubleVar(value=p.si_k),
            "cutoff_factor": tk.DoubleVar(value=p.cutoff_factor),
        }

        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="Ready")
        self.timing_var = tk.StringVar(value="Not run yet")

        self.compare_project_var = tk.StringVar(value="")
        self.compare_project_blank_var = tk.StringVar(value="")
        self.compare_other_var = tk.StringVar(value="")
        self.compare_other_blank_var = tk.StringVar(value="")
        self.compare_rotate_project_var = tk.IntVar(value=0)
        self.compare_rotate_other_var = tk.IntVar(value=0)
        self.compare_cutline_axis_var = tk.StringVar(value="x")
        self.compare_cutline_index_var = tk.StringVar(value="")
        self.compare_metric_var = tk.StringVar(value="No comparison yet")

    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.sim_tab = ttk.Frame(notebook)
        self.source_tab = ttk.Frame(notebook)
        self.compare_tab = ttk.Frame(notebook)
        notebook.add(self.sim_tab, text="Simulation")
        notebook.add(self.source_tab, text="Source View")
        notebook.add(self.compare_tab, text="Comparison")

        self._build_simulation_tab()
        self._build_source_tab()
        self._build_compare_tab()

    def _row_entry(self, parent, row: int, label: str, var: tk.Variable, width: int = 14, values=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        if values is None:
            widget = ttk.Entry(parent, textvariable=var, width=width)
        else:
            widget = ttk.Combobox(parent, textvariable=var, values=values, width=width - 2, state="readonly")
        widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
        return widget

    def _build_param_pages(self, parent) -> None:
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        optical = ttk.Frame(nb)
        source = ttk.Frame(nb)
        stack = ttk.Frame(nb)
        numerics = ttk.Frame(nb)
        nb.add(optical, text="Optics")
        nb.add(source, text="Source/Polarization")
        nb.add(stack, text="Mask/Stack")
        nb.add(numerics, text="Numerics/Output")

        for frame in (optical, source, stack, numerics):
            frame.columnconfigure(1, weight=1)

        entries = [
            ("wavelength_nm", "Wavelength lambda [nm]"),
            ("na", "NA"),
            ("magnification_x", "Magnification X"),
            ("magnification_y", "Magnification Y"),
            ("central_obscuration", "Central obscuration"),
            ("incidence_angle_deg", "Incidence angle [deg]"),
            ("azimuthal_angle_deg", "Azimuthal angle [deg]"),
            ("defocus_nm", "Defocus [nm]"),
        ]
        for i, (key, label) in enumerate(entries):
            self._row_entry(optical, i, label, self.vars[key])
        ttk.Checkbutton(
            optical,
            text="Ideal focal plane (defocus = 0 nm)",
            variable=self.ideal_focus_var,
        ).grid(row=len(entries), column=0, columnspan=2, sticky="w", padx=6, pady=4)

        self._row_entry(source, 0, "Illumination type", self.vars["illumination"], values=["quadrupole", "annular", "circular"])
        self._row_entry(source, 1, "sigma in", self.vars["sigma_in"])
        self._row_entry(source, 2, "sigma out", self.vars["sigma_out"])
        self._row_entry(source, 3, "pole opening [deg]", self.vars["pole_open_angle_deg"])
        self._row_entry(source, 4, "Source mesh [deg]", self.vars["source_mesh_deg"])
        self._row_entry(source, 5, "Polarization", self.vars["polarization"], values=["unpolarized", "linear", "x", "y"])
        self._row_entry(source, 6, "Linear polarization angle [deg]", self.vars["pol_angle_deg"])

        self._row_entry(stack, 0, "mask width [nm]", self.vars["mask_width_nm"])
        self._row_entry(stack, 1, "mask height [nm]", self.vars["mask_height_nm"])
        self._row_entry(stack, 2, "Mask threshold", self.vars["mask_threshold"])
        ttk.Checkbutton(stack, text="Invert mask", variable=self.vars["invert_mask"]).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=6, pady=4
        )
        self._row_entry(stack, 4, "Absorber thickness [nm]", self.vars["absorber_thickness_nm"])
        self._row_entry(stack, 5, "Absorber n", self.vars["absorber_n"])
        self._row_entry(stack, 6, "Absorber k", self.vars["absorber_k"])
        ttk.Separator(stack).grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        self._row_entry(stack, 8, "Mo/Si periods", self.vars["multilayer_periods"])
        self._row_entry(stack, 9, "Mo thickness [nm]", self.vars["mo_thickness_nm"])
        self._row_entry(stack, 10, "Mo n", self.vars["mo_n"])
        self._row_entry(stack, 11, "Mo k", self.vars["mo_k"])
        self._row_entry(stack, 12, "Si thickness [nm]", self.vars["si_thickness_nm"])
        self._row_entry(stack, 13, "Si n", self.vars["si_n"])
        self._row_entry(stack, 14, "Si k", self.vars["si_k"])
        ttk.Label(stack, text="Multilayer model: periodic Mo/Si. Thickness and complex refractive index n+ik are editable.", foreground="#444", wraplength=320).grid(
            row=15, column=0, columnspan=2, sticky="w", padx=6, pady=8
        )

        self._row_entry(numerics, 0, "cutoff factor", self.vars["cutoff_factor"])
        self._row_entry(numerics, 1, "Cutline axis", self.cutline_axis_var, values=["x", "y"])
        self._row_entry(numerics, 2, "Cutline index (blank=center)", self.cutline_index_var)
        ttk.Label(numerics, text="The imaging model is fixed to Abbe. Strict electromagnetic fields are solved by EUVlitho/ELitho.", foreground="#444", wraplength=320).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=6, pady=8
        )

    def _build_simulation_tab(self) -> None:
        paned = ttk.PanedWindow(self.sim_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left = ttk.Frame(paned, width=430)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        file_box = ttk.LabelFrame(left, text="Input And Abbe Imaging")
        file_box.pack(fill=tk.X, padx=4, pady=4)
        file_box.columnconfigure(1, weight=1)

        ttk.Label(file_box, text="Mask file").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(file_box, textvariable=self.mask_path_var, width=34).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(file_box, text="Browse", command=self._browse_mask).grid(row=0, column=2, padx=6, pady=4)
        ttk.Label(file_box, text="Example: examples/masks/center_rectangle_128.png", foreground="#555").grid(
            row=1, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 4)
        )
        ttk.Label(file_box, text="Imaging method").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(file_box, text="Abbe (strict vector electromagnetic field)").grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Button(file_box, text="Run Simulation", command=self._start_simulation).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=8
        )

        param_box = ttk.LabelFrame(left, text="Physical And Numerical Parameters")
        param_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._build_param_pages(param_box)

        progress_box = ttk.LabelFrame(left, text="Progress And Timing")
        progress_box.pack(fill=tk.X, padx=4, pady=4)
        ttk.Progressbar(progress_box, variable=self.progress_var, maximum=100).pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(progress_box, textvariable=self.status_var, wraplength=390).pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(progress_box, textvariable=self.timing_var, justify=tk.LEFT, wraplength=390).pack(fill=tk.X, padx=8, pady=6)

        export_box = ttk.LabelFrame(left, text="Export")
        export_box.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(export_box, text="Export PNG", command=self._export_png).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=6)
        ttk.Button(export_box, text="Export DAT", command=self._export_dat).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=6)
        ttk.Button(export_box, text="Export JSON", command=self._export_json).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=6)

        self.sim_fig = plt.Figure(figsize=(9.2, 6.2), dpi=100)
        self.sim_canvas = FigureCanvasTkAgg(self.sim_fig, master=right)
        self.sim_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_empty_sim()

    def _build_source_tab(self) -> None:
        paned = ttk.PanedWindow(self.source_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        left = ttk.Frame(paned, width=380)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        info = ttk.LabelFrame(left, text="Source Plot")
        info.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(
            info,
            text=(
                "This page plots the actual discrete source points from the current Simulation parameters.\n"
                "Coordinates are normalized pupil/sigma coordinates. The green circle is NA=1; "
                "dashed circles show sigma in/out."
            ),
            wraplength=330,
            justify=tk.LEFT,
        ).pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(info, text="Refresh Source Plot From Current Parameters", command=self._draw_source_from_params).pack(
            fill=tk.X, padx=8, pady=8
        )

        self.source_info_var = tk.StringVar(value="Not plotted yet")
        ttk.Label(info, textvariable=self.source_info_var, justify=tk.LEFT, wraplength=330).pack(
            fill=tk.X, padx=8, pady=8
        )

        shortcut = ttk.LabelFrame(left, text="Common Source Parameters")
        shortcut.pack(fill=tk.X, padx=4, pady=4)
        shortcut.columnconfigure(1, weight=1)
        self._row_entry(shortcut, 0, "Illumination type", self.vars["illumination"], values=["quadrupole", "annular", "circular"])
        self._row_entry(shortcut, 1, "sigma in", self.vars["sigma_in"])
        self._row_entry(shortcut, 2, "sigma out", self.vars["sigma_out"])
        self._row_entry(shortcut, 3, "opening [deg]", self.vars["pole_open_angle_deg"])
        self._row_entry(shortcut, 4, "mesh [deg]", self.vars["source_mesh_deg"])

        self.source_fig = plt.Figure(figsize=(8.4, 7.2), dpi=100)
        self.source_canvas = FigureCanvasTkAgg(self.source_fig, master=right)
        self.source_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_empty_source()

    def _build_compare_tab(self) -> None:
        paned = ttk.PanedWindow(self.compare_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        left = ttk.Frame(paned, width=430)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        box = ttk.LabelFrame(left, text="Load Results And Compare")
        box.pack(fill=tk.X, padx=4, pady=4)
        box.columnconfigure(1, weight=1)

        ttk.Label(box, text="This project result").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(box, textvariable=self.compare_project_var, width=34).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(box, text="Browse", command=lambda: self._browse_compare(self.compare_project_var)).grid(row=0, column=2, padx=6, pady=4)

        ttk.Label(box, text="This project blank-mask result").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(box, textvariable=self.compare_project_blank_var, width=34).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(box, text="Browse", command=lambda: self._browse_compare(self.compare_project_blank_var)).grid(row=1, column=2, padx=6, pady=4)

        ttk.Label(box, text="Other algorithm result").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(box, textvariable=self.compare_other_var, width=34).grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(box, text="Browse", command=lambda: self._browse_compare(self.compare_other_var)).grid(row=2, column=2, padx=6, pady=4)

        ttk.Label(box, text="Other algorithm blank-mask result").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(box, textvariable=self.compare_other_blank_var, width=34).grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(box, text="Browse", command=lambda: self._browse_compare(self.compare_other_blank_var)).grid(row=3, column=2, padx=6, pady=4)

        self._row_entry(box, 4, "This project image/blank rot90 count", self.compare_rotate_project_var)
        self._row_entry(box, 5, "Other algorithm image/blank rot90 count", self.compare_rotate_other_var)
        self._row_entry(box, 6, "Cutline axis", self.compare_cutline_axis_var, values=["x", "y"])
        self._row_entry(box, 7, "Cutline index (blank=center)", self.compare_cutline_index_var)
        ttk.Button(box, text="Start Comparison", command=self._start_compare).grid(row=8, column=0, columnspan=3, sticky="ew", padx=6, pady=8)

        metric_box = ttk.LabelFrame(left, text="Error Metrics")
        metric_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        ttk.Label(metric_box, textvariable=self.compare_metric_var, justify=tk.LEFT, wraplength=390).pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Button(metric_box, text="Export Difference PNG", command=self._export_compare_diff_png).pack(fill=tk.X, padx=8, pady=5)
        ttk.Button(metric_box, text="Export Difference DAT", command=self._export_compare_diff_dat).pack(fill=tk.X, padx=8, pady=5)

        self.compare_fig = plt.Figure(figsize=(9.2, 6.2), dpi=100)
        self.compare_canvas = FigureCanvasTkAgg(self.compare_fig, master=right)
        self.compare_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_empty_compare()

    def _browse_mask(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Mask File",
            filetypes=[("Mask/image/data", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.dat *.txt *.npy *.npz"), ("All files", "*.*")],
        )
        if path:
            self.mask_path_var.set(path)

    def _browse_compare(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Select Result File",
            filetypes=[("Result/image/data", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.dat *.txt *.npy *.npz"), ("All files", "*.*")],
        )
        if path:
            var.set(path)

    def _params_from_gui(self) -> backend.SimulationParams:
        values = {}
        for key, var in self.vars.items():
            values[key] = var.get()
        if self.ideal_focus_var.get():
            values["defocus_nm"] = 0.0
        return backend.SimulationParams(**values)

    @staticmethod
    def _parse_optional_index(value: str):
        text = value.strip()
        return None if not text else int(text)

    def _start_simulation(self) -> None:
        mask_text = self.mask_path_var.get().strip()
        if not mask_text:
            messagebox.showerror("No Mask Selected", "Please select a mask file first.")
            return
        mask_path = Path(mask_text)
        if not mask_path.exists():
            messagebox.showerror("File Not Found", f"Mask file was not found:\n{mask_path}")
            return
        try:
            params = self._params_from_gui()
            cut_idx = self._parse_optional_index(self.cutline_index_var.get())
        except Exception as exc:
            messagebox.showerror("Parameter Error", str(exc))
            return

        self.progress_var.set(0)
        self.status_var.set("Starting simulation...")
        self.timing_var.set("Running...")
        self.last_result = None
        self.last_params = params

        def worker():
            try:
                result = backend.run_simulation(
                    mask_path=mask_path,
                    params=params,
                    cutline_axis=self.cutline_axis_var.get(),
                    cutline_index=cut_idx,
                    progress=lambda pct, msg: self.msg_queue.put(("progress", pct, msg)),
                )
                self.msg_queue.put(("sim_done", result))
            except Exception as exc:  # noqa: BLE001
                self.msg_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _start_compare(self) -> None:
        project = Path(self.compare_project_var.get())
        project_blank = Path(self.compare_project_blank_var.get())
        other = Path(self.compare_other_var.get())
        other_blank = Path(self.compare_other_blank_var.get())
        missing = [p for p in (project, project_blank, other, other_blank) if not p.exists()]
        if missing:
            messagebox.showerror("File Not Found", "Please check these input files:\n" + "\n".join(str(p) for p in missing))
            return
        try:
            cut_idx = self._parse_optional_index(self.compare_cutline_index_var.get())
        except Exception as exc:
            messagebox.showerror("Parameter Error", str(exc))
            return
        self.compare_metric_var.set("Comparing...")

        def worker():
            try:
                result = backend.compare_result_images(
                    project_path=project,
                    other_path=other,
                    project_blank_path=project_blank,
                    other_blank_path=other_blank,
                    rotate_project_k=int(self.compare_rotate_project_var.get()),
                    rotate_other_k=int(self.compare_rotate_other_var.get()),
                    cutline_axis=self.compare_cutline_axis_var.get(),
                    cutline_index=cut_idx,
                )
                self.msg_queue.put(("compare_done", result))
            except Exception as exc:  # noqa: BLE001
                self.msg_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.msg_queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    self.progress_var.set(float(item[1]))
                    self.status_var.set(str(item[2]))
                elif kind == "sim_done":
                    self.last_result = item[1]
                    self.progress_var.set(100)
                    self.status_var.set("Complete")
                    self._show_sim_result(item[1])
                elif kind == "compare_done":
                    self.last_compare = item[1]
                    self.progress_var.set(100)
                    self.status_var.set("Comparison complete")
                    self._show_compare_result(item[1])
                elif kind == "error":
                    self.status_var.set("Error")
                    self.compare_metric_var.set("Error")
                    messagebox.showerror("Run Error", item[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _draw_empty_sim(self) -> None:
        self.sim_fig.clear()
        ax = self.sim_fig.add_subplot(111)
        ax.text(0.5, 0.5, "Select a mask and click Run Simulation", ha="center", va="center", fontsize=14)
        ax.axis("off")
        self.sim_canvas.draw_idle()

    def _draw_empty_source(self) -> None:
        self.source_fig.clear()
        ax = self.source_fig.add_subplot(111)
        ax.text(0.5, 0.5, "Click Refresh Source Plot From Current Parameters", ha="center", va="center", fontsize=14)
        ax.axis("off")
        self.source_canvas.draw_idle()

    def _draw_source_from_params(self) -> None:
        try:
            params = self._params_from_gui()
            data = backend.source_preview(params)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Source Plot Error", str(exc))
            return

        self.source_fig.clear()
        ax = self.source_fig.add_subplot(111)
        ax.set_aspect("equal", adjustable="box")
        theta = [i * 2.0 * 3.141592653589793 / 720 for i in range(721)]
        for radius, style, color, label in [
            (1.0, "-", "#00aa00", "NA pupil"),
            (float(data["sigma_out"]), "--", "#cc6600", "sigma out"),
            (float(data["sigma_in"]), "--", "#0077cc", "sigma in"),
        ]:
            xs = [radius * math.cos(t) for t in theta]
            ys = [radius * math.sin(t) for t in theta]
            ax.plot(xs, ys, linestyle=style, color=color, lw=1.2, label=label)

        families = sorted(set(data["family"].tolist())) if len(data["family"]) else []
        colors = {
            "dipole_x": "tab:red",
            "dipole_y": "tab:blue",
            "annular": "tab:purple",
            "circular": "tab:green",
        }
        for fam in families:
            mask = data["family"] == fam
            ax.scatter(
                data["u"][mask],
                data["v"][mask],
                s=38,
                color=colors.get(fam, "black"),
                edgecolor="white",
                linewidth=0.5,
                label=f"{fam} points={int(mask.sum())}",
            )

        ax.axhline(0, color="0.35", lw=0.8)
        ax.axvline(0, color="0.35", lw=0.8)
        lim = max(1.05, float(data["sigma_out"]) * 1.18)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_xlabel(r"$\sigma_x = k_x/(k\,NA)$")
        ax.set_ylabel(r"$\sigma_y = k_y/(k\,NA)$")
        ax.set_title(
            f"Source pupil: {data['illumination']}, mesh={data['source_mesh_deg']} deg, "
            f"total points={data['total_points']}"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right", fontsize=9)
        self.source_fig.tight_layout()
        self.source_canvas.draw_idle()

        counts = ", ".join(f"{k}: {v}" for k, v in data["counts"].items())
        self.source_info_var.set(
            "\n".join(
                [
                    f"Illumination type: {data['illumination']}",
                    f"sigma in/out: {data['sigma_in']} / {data['sigma_out']}",
                    f"opening: {data['pole_open_angle_deg']} deg",
                    f"mesh: {data['source_mesh_deg']} deg",
                    f"total source points: {data['total_points']}",
                    f"components: {counts}",
                ]
            )
        )

    def _draw_empty_compare(self) -> None:
        self.compare_fig.clear()
        ax = self.compare_fig.add_subplot(111)
        ax.text(0.5, 0.5, "Load four result files and click Start Comparison", ha="center", va="center", fontsize=14)
        ax.axis("off")
        self.compare_canvas.draw_idle()

    def _show_sim_result(self, result: backend.SimulationResult) -> None:
        self.sim_fig.clear()
        ax_img = self.sim_fig.add_subplot(1, 2, 1)
        ax_cut = self.sim_fig.add_subplot(1, 2, 2)
        im = ax_img.imshow(result.image, cmap="jet", origin="lower")
        ax_img.set_title(f"{result.method} aerial image")
        ax_img.set_xlabel("x pixel")
        ax_img.set_ylabel("y pixel")
        self.sim_fig.colorbar(im, ax=ax_img, fraction=0.046, pad=0.04)

        ax_cut.plot(result.x_nm, result.cutline, color="tab:blue", lw=1.6)
        axis_name = "horizontal y" if result.cutline_axis == "x" else "vertical x"
        ax_cut.set_title(f"Cutline: {axis_name} index={result.cutline_index}")
        ax_cut.set_xlabel("position [nm-equivalent]")
        ax_cut.set_ylabel("intensity")
        ax_cut.grid(True, alpha=0.25)
        self.sim_fig.tight_layout()
        self.sim_canvas.draw_idle()

        t = result.timings_s
        text = [
            f"Total time: {t.get('total_s', 0):.3f} s",
            f"Abbe intensity assembly: {t.get('abbe_imaging_s', 0):.3f} s",
            f"Strict-field spectrum rows: {result.summary.get('frequency_response_shape', ['?'])[0]}",
            f"Source points: {result.summary.get('total_source_points', '?')}",
        ]
        self.timing_var.set("\n".join(text))

    def _show_compare_result(self, result: dict) -> None:
        self.compare_fig.clear()
        ax1 = self.compare_fig.add_subplot(2, 2, 1)
        ax2 = self.compare_fig.add_subplot(2, 2, 2)
        ax3 = self.compare_fig.add_subplot(2, 2, 3)
        ax4 = self.compare_fig.add_subplot(2, 2, 4)
        im1 = ax1.imshow(result["project_norm"], cmap="jet", origin="lower")
        ax1.set_title("OpenEUV Abbe / blank")
        self.compare_fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        im2 = ax2.imshow(result["other_norm"], cmap="jet", origin="lower")
        ax2.set_title("Other algorithm / blank")
        self.compare_fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
        im3 = ax3.imshow(result["diff"], cmap="jet", origin="lower")
        ax3.set_title("Difference: project - other algorithm")
        self.compare_fig.colorbar(im3, ax=ax3, fraction=0.046, pad=0.04)
        ax4.plot(result["coord_nm"], result["other_cutline"], color="black", lw=1.5, label="Other algorithm")
        ax4.plot(result["coord_nm"], result["project_cutline"], color="tab:blue", lw=1.2, ls="--", label="OpenEUV Abbe")
        ax4.set_title(f"Cutline index={result['cutline_index']}")
        ax4.set_xlabel("sample coordinate [pixel]")
        ax4.set_ylabel("intensity")
        ax4.grid(True, alpha=0.25)
        ax4.legend()
        self.compare_fig.tight_layout()
        self.compare_canvas.draw_idle()

        m = result["metrics"]
        self.compare_metric_var.set(
            "\n".join(
                [
                    f"NRMSE: {m['nrmse_percent']:.4f} %",
                    f"RMSE: {m['rmse']:.6g}",
                    f"MAE: {m['mae']:.6g}",
                    f"Max abs: {m['max_abs']:.6g}",
                    f"Corr: {m['corr']:.6f}",
                    "Normalization: each result / its blank-mask mean",
                    f"Project blank mean: {m['project_blank_mean']:.6g}",
                    f"Other-algorithm blank mean: {m['other_blank_mean']:.6g}",
                    f"Project blank CV: {m['project_blank_cv_percent']:.3g} %",
                    f"Other-algorithm blank CV: {m['other_blank_cv_percent']:.3g} %",
                    f"Shape: {m['shape']}",
                ]
            )
        )

    def _export_png(self) -> None:
        if self.last_result is None:
            messagebox.showinfo("No Result", "Run a simulation first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export PNG",
            defaultextension=".png",
            initialdir=str(APP_DIR / "exports"),
            filetypes=[("PNG", "*.png")],
        )
        if path:
            backend.save_png(Path(path), self.last_result.image)

    def _export_dat(self) -> None:
        if self.last_result is None:
            messagebox.showinfo("No Result", "Run a simulation first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export DAT",
            defaultextension=".dat",
            initialdir=str(APP_DIR / "exports"),
            filetypes=[("DAT", "*.dat")],
        )
        if path:
            p = self.last_params or backend.SimulationParams()
            pixel_size_nm = (p.mask_width_nm / p.magnification_x) / self.last_result.image.shape[1]
            backend.save_dat(Path(path), self.last_result.image, pixel_size_nm=pixel_size_nm)

    def _export_json(self) -> None:
        if self.last_result is None:
            messagebox.showinfo("No Result", "Run a simulation first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export JSON",
            defaultextension=".json",
            initialdir=str(APP_DIR / "exports"),
            filetypes=[("JSON", "*.json")],
        )
        if path:
            backend.save_summary(Path(path), self.last_result)

    def _export_compare_diff_png(self) -> None:
        if self.last_compare is None:
            messagebox.showinfo("No Comparison Result", "Run a comparison first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Difference PNG",
            defaultextension=".png",
            initialdir=str(APP_DIR / "exports"),
            filetypes=[("PNG", "*.png")],
        )
        if path:
            backend.save_png(Path(path), self.last_compare["diff"])

    def _export_compare_diff_dat(self) -> None:
        if self.last_compare is None:
            messagebox.showinfo("No Comparison Result", "Run a comparison first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Difference DAT",
            defaultextension=".dat",
            initialdir=str(APP_DIR / "exports"),
            filetypes=[("DAT", "*.dat")],
        )
        if path:
            backend.save_dat(Path(path), self.last_compare["diff"], pixel_size_nm=1.0)


def main() -> None:
    app = OpenEUVAbbeGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
