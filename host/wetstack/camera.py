"""Camera capture, ROI calibration and absorbance features.

Webcam pixel values are gamma-encoded sRGB. Absorbance needs linear light,
so every ROI mean is linearized before taking -log10(I / I_white).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .sim import ALL_WELLS

ROI_FILE = Path("config/rois.json")


def srgb_to_linear(code: np.ndarray) -> np.ndarray:
    c = np.asarray(code, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


def rgb_to_absorbance(rgb: dict) -> dict:
    """rgb: {pos: [R,G,B] 8-bit means, 'WHITE': [R,G,B]} -> {pos: np.array(A_R, A_G, A_B)}"""
    white = np.maximum(srgb_to_linear(rgb["WHITE"]), 1e-6)
    out = {}
    for pos, val in rgb.items():
        if pos == "WHITE":
            continue
        lin = np.maximum(srgb_to_linear(val), 1e-6)
        out[pos] = -np.log10(lin / white)
    return out


class RealCamera:
    def __init__(self, index: int = 0, width: int = 1920, height: int = 1080, roi_radius: int | None = None):
        import cv2
        self.cv2 = cv2
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Camera {index} did not open. Set camera_index in config/lab.json (try 0, 1, 2).")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.rois = None
        self.roi_radius = roi_radius
        if ROI_FILE.exists():
            data = json.loads(ROI_FILE.read_text())
            self.rois = data["centers"]
            self.roi_radius = roi_radius or data["radius"]

    def lock(self, exposure: float = -6, wb_kelvin: int = 5000, focus: int = 0) -> dict:
        """Best effort: drivers differ. Returns what each setting reported back."""
        cv2, cap = self.cv2, self.cap
        report = {}
        attempts = [
            ("auto_exposure", cv2.CAP_PROP_AUTO_EXPOSURE, 0.25),   # V4L2 manual mode
            ("auto_exposure_win", cv2.CAP_PROP_AUTO_EXPOSURE, 0),   # DirectShow/MSMF manual
            ("exposure", cv2.CAP_PROP_EXPOSURE, exposure),
            ("auto_wb", cv2.CAP_PROP_AUTO_WB, 0),
            ("wb_temperature", cv2.CAP_PROP_WB_TEMPERATURE, wb_kelvin),
            ("autofocus", cv2.CAP_PROP_AUTOFOCUS, 0),
            ("focus", cv2.CAP_PROP_FOCUS, focus),
        ]
        for name, prop, value in attempts:
            ok = cap.set(prop, value)
            report[name] = {"requested": value, "accepted": bool(ok), "now": cap.get(prop)}
        for _ in range(10):
            cap.read()
        return report

    def frame(self, average: int = 5) -> np.ndarray:
        acc = None
        for _ in range(average):
            ok, img = self.cap.read()
            if not ok:
                raise RuntimeError("Camera read failed.")
            img = img.astype(float)
            acc = img if acc is None else acc + img
        return acc / average

    def read_rgb(self) -> dict:
        if not self.rois:
            raise RuntimeError("No ROIs. Run: python -m wetstack calibrate-rois")
        img = self.frame()
        h, w = img.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        out = {}
        for pos, (cx, cy) in self.rois.items():
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= self.roi_radius ** 2
            bgr = img[mask].mean(axis=0)
            out[pos] = bgr[::-1]
        return out

    def preview(self, seconds: float = 30.0) -> None:
        cv2 = self.cv2
        t0 = time.time()
        while time.time() - t0 < seconds:
            ok, img = self.cap.read()
            if not ok:
                break
            if self.rois:
                for pos, (cx, cy) in self.rois.items():
                    cv2.circle(img, (int(cx), int(cy)), int(self.roi_radius), (0, 255, 0), 1)
                    cv2.putText(img, pos, (int(cx) - 10, int(cy) - int(self.roi_radius) - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            sat = (img >= 254).mean() * 100
            cv2.putText(img, f"saturated px: {sat:.2f}%  (keep at 0)", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("WetStack camera (q to close)", img)
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break
        cv2.destroyAllWindows()

    def calibrate_rois(self, radius: int = 18) -> dict:
        """Click A1..D6 in reading order, then one click on bare light pad (WHITE)."""
        cv2 = self.cv2
        img = self.frame(average=3).astype(np.uint8)
        names = ALL_WELLS + ["WHITE"]
        centers: dict = {}
        shown = img.copy()

        def on_click(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN and len(centers) < len(names):
                name = names[len(centers)]
                centers[name] = [x, y]
                cv2.circle(shown, (x, y), radius, (0, 255, 0), 1)
                cv2.putText(shown, name, (x - 10, y - radius - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        win = "Click well centers A1..D6 in order, then bare light pad. Enter to save, Esc to cancel"
        cv2.namedWindow(win)
        cv2.setMouseCallback(win, on_click)
        while True:
            label = names[len(centers)] if len(centers) < len(names) else "done - press Enter"
            frame = shown.copy()
            cv2.putText(frame, f"next: {label}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow(win, frame)
            key = cv2.waitKey(30) & 0xFF
            if key == 27:
                cv2.destroyAllWindows()
                raise SystemExit("ROI calibration cancelled.")
            if key in (13, 10) and len(centers) == len(names):
                break
        cv2.destroyAllWindows()
        ROI_FILE.parent.mkdir(parents=True, exist_ok=True)
        ROI_FILE.write_text(json.dumps({"centers": centers, "radius": radius}, indent=1))
        self.rois, self.roi_radius = centers, radius
        return {"saved": str(ROI_FILE), "count": len(centers)}

    def close(self) -> None:
        self.cap.release()
