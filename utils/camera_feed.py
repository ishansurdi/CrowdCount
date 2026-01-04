
"""
camera_feed.py

Contains camera-related helpers:
- open_camera(source)
- get_camera_frame(cap)
- release_camera(cap)
- simple helper to probe available indices
"""

import cv2


def open_camera(source=0, width=None, height=None):
    """Open a camera or video source.

    Args:
        source: camera index (0,1,...) or URL string
        width: optional target width
        height: optional target height

    Returns:
        cap: cv2.VideoCapture object
    """
    cap = cv2.VideoCapture(source)
    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    return cap


def get_camera_frame(cap):
    """Read a single frame from the capture object.

    Returns:
        ret (bool), frame (BGR image or None)
    """
    if cap is None:
        return False, None
    ret, frame = cap.read()
    return ret, frame


def release_camera(cap):
    """Release the camera safely."""
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass


def probe_camera_indices(max_index=5):
    """Quick helper to test which local camera indices open.

    Use for debugging on different machines.
    """
    available = []
    for i in range(max_index + 1):
        c = cv2.VideoCapture(i)
        ok = c.isOpened()
        c.release()
        if ok:
            available.append(i)
    return available
