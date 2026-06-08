"""Detect whether a PlayerImage has a visible face.

Used by the Name the Pro picker so we don't ship trivia rounds where
the photo is a wide action shot you couldn't possibly identify a
player from. Result is stored on `PlayerImage.face_detected`:

    True   — at least one face of usable size was found.
    False  — nothing found (try the next photo).
    None   — not yet scanned.

We use OpenCV's YuNet detector (`cv2.FaceDetectorYN`). YuNet is a tiny
(~230KB) ONNX model that runs in milliseconds on CPU and is *far* more
robust than the classic Haar cascades for the cases that matter here:
caps, sunglasses, three-quarter angles, motion blur. The Haar default
cascade misses ~half of typical tennis photos because everyone is in
a visor.

The model file is checked in at `app/services/assets/`. Bundling
beats download-on-startup — the box has no outbound HTTP except to
sources we control, and the file is 230KB.

Definition of "usable":
  - YuNet score ≥ 0.6 (default threshold).
  - Face bounding box ≥ 90×90 px AND ≥ 6% of the shorter image side.

Smaller-than-that faces tend to be crowd shots or background figures
you couldn't identify the player from.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import httpx
import numpy as np
from PIL import Image, UnidentifiedImageError

log = logging.getLogger(__name__)


_MODEL_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "face_detection_yunet_2023mar.onnx"
)
_SCORE_THRESHOLD = 0.6
_NMS_THRESHOLD = 0.3
# Cap inference resolution. Tennis press photos commonly weigh in at
# 2000-4000px on the long edge; YuNet works fine on a downscaled copy
# and a fixed input keeps peak RSS predictable (the 2GB Lightsail box
# OOMs around ~1.5GB if we run inference at full res). 1280 is a
# reasonable balance — small enough to keep memory bounded, large
# enough to still detect a 90px face from the original.
_MAX_LONG_EDGE = 1280


_DETECTOR: cv2.FaceDetectorYN | None = None


def _detector(w: int, h: int) -> cv2.FaceDetectorYN:
    """Cached detector. Reuses one ONNX backend across calls and just
    flips the input size — rebuilding per call leaks memory in the
    OpenCV DNN runtime, which is what OOM'd a 2GB box earlier."""
    global _DETECTOR
    if _DETECTOR is None:
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(
                f"YuNet model missing at {_MODEL_PATH}. Re-deploy the "
                f"backend or fetch it from opencv_zoo."
            )
        _DETECTOR = cv2.FaceDetectorYN_create(
            str(_MODEL_PATH),
            "",
            (w, h),
            score_threshold=_SCORE_THRESHOLD,
            nms_threshold=_NMS_THRESHOLD,
            top_k=20,
        )
    else:
        _DETECTOR.setInputSize((w, h))
    return _DETECTOR


def _min_face_side(img_w: int, img_h: int) -> int:
    short_side = min(img_w, img_h)
    return max(90, int(short_side * 0.06))


@dataclass
class FaceCheck:
    detected: bool
    face_count: int
    # (x, y, w, h, score) for the highest-scoring face that passed the
    # size gate. None when no face survived filtering.
    best: tuple[int, int, int, int, float] | None
    error: str | None = None


def detect_face_in_bytes(data: bytes) -> FaceCheck:
    """Run YuNet on raw image bytes. Resilient: returns a FaceCheck
    with `error` set instead of raising on decode failures.

    Resizes the input so the long edge is ≤ _MAX_LONG_EDGE before
    inference. Detected boxes are scaled back to the original image's
    coords. Face-size gating uses the ORIGINAL dimensions so a tiny
    background face in a 4K shot still gets rejected the same way
    it would at full res.
    """
    try:
        with Image.open(BytesIO(data)) as pil:
            pil = pil.convert("RGB")
            orig_w, orig_h = pil.size
            long_edge = max(orig_w, orig_h)
            if long_edge > _MAX_LONG_EDGE:
                scale = _MAX_LONG_EDGE / long_edge
                small = pil.resize(
                    (max(1, int(orig_w * scale)), max(1, int(orig_h * scale))),
                    Image.BILINEAR,
                )
            else:
                scale = 1.0
                small = pil
            arr = np.array(small)
    except (UnidentifiedImageError, OSError) as exc:
        return FaceCheck(False, 0, None, error=f"decode failed: {exc}")

    inf_h, inf_w = arr.shape[:2]
    # OpenCV wants BGR. Reverse on axis 2 produces a view; .copy() to
    # force a contiguous C-order array for the ONNX call.
    bgr = np.ascontiguousarray(arr[:, :, ::-1])

    det = _detector(inf_w, inf_h)
    _, faces = det.detect(bgr)
    # Help the GC drop the big arrays before the next iteration —
    # without this, RSS climbs steadily across thousands of calls.
    del arr, bgr
    if faces is None or len(faces) == 0:
        return FaceCheck(False, 0, None)

    min_side = _min_face_side(orig_w, orig_h)
    inv = 1.0 / scale if scale != 0 else 1.0
    qualifying: list[tuple[int, int, int, int, float]] = []
    for f in faces:
        # Scale the inference-resolution box back to original coords.
        x = int(f[0] * inv)
        y = int(f[1] * inv)
        fw = int(f[2] * inv)
        fh = int(f[3] * inv)
        score = float(f[-1])
        if fw < min_side or fh < min_side:
            continue
        qualifying.append((x, y, fw, fh, score))

    if not qualifying:
        return FaceCheck(False, 0, None)
    best = max(qualifying, key=lambda t: t[4])
    return FaceCheck(detected=True, face_count=len(qualifying), best=best)


def detect_face_at_url(url: str, timeout_s: float = 15.0) -> FaceCheck:
    """Fetch an image URL and run face detection. Returns a FaceCheck
    with `error` set on network failures so the caller can decide
    whether to retry or mark as unscanned."""
    try:
        r = httpx.get(
            url,
            timeout=timeout_s,
            # Wikimedia rate-limits anonymous bot-like clients hard;
            # a polite UA + email matches our existing enricher style.
            headers={"User-Agent": "mob.tennis face-detect/0.1 (atli@gangverk.is)"},
            follow_redirects=True,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        return FaceCheck(False, 0, None, error=f"fetch failed: {exc}")
    return detect_face_in_bytes(r.content)
