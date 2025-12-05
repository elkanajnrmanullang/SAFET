import os
import shutil
from datetime import datetime
from typing import Optional, Tuple

TEMP_VISION_DIR = "data/temp_vision"
os.makedirs(TEMP_VISION_DIR, exist_ok=True)


def _safe_save_image(src_path: str) -> Optional[str]:
    try:
        if not src_path:
            return None
        if not os.path.exists(src_path):
            return None

        base_name = os.path.basename(src_path)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        dest_name = f"{timestamp}_{base_name}"
        dest_path = os.path.join(TEMP_VISION_DIR, dest_name)
        shutil.copyfile(src_path, dest_path)
        return dest_path
    except Exception:
        return None


def accept_user_pattern(pattern_name: Optional[str], image_path: Optional[str] = None) -> dict:
    saved_path = _safe_save_image(image_path) if image_path else None

    chart_pattern = pattern_name.strip() if isinstance(pattern_name, str) and pattern_name.strip() else None
    candle_pattern = None

    return {
        "chart_pattern": chart_pattern,
        "candle_pattern": candle_pattern,
        "image_path": saved_path,
        "source": "user",
        "note": "User-provided pattern; automatic detection disabled."
    }


def detect_all_patterns(df, user_pattern_name: Optional[str] = None, user_image_path: Optional[str] = None) -> Tuple[str, str]:
    try:
        if user_pattern_name and isinstance(user_pattern_name, str) and user_pattern_name.strip():
            name = user_pattern_name.strip()
            chart_label = f"User: {name}"
            candle_label = f"User: {name} (not specified)"

            if user_image_path:
                saved = _safe_save_image(user_image_path)
                if saved:
                    chart_label += " [image_saved]"
            return chart_label, candle_label

        return "Not provided", "Not provided"
    except Exception:
        return "Not provided", "Not provided"


def clear_temp_image(path: str) -> bool:
    try:
        if not path:
            return False
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except Exception:
        return False


if __name__ == "__main__":
    demo = accept_user_pattern("Ascending Triangle", None)
    print("Demo accept_user_pattern:", demo)
    print("Demo detect_all_patterns (with name):", detect_all_patterns(None, user_pattern_name="Head and Shoulders"))
    print("Demo detect_all_patterns (none):", detect_all_patterns(None))
