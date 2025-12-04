# backend/vision_pattern.py
"""
Vision layer (REVISED)
----------------------
Versi ini **menghapus** deteksi otomatis pola chart/candlestick.
Sebagai gantinya, sistem menerima **input pola dari user** (nama pola dan opsional file gambar).
Fungsi-fungsi di sini memberikan interface minimal yang dipakai oleh pipeline
(seperti crypto_data.py atau pages) sehingga sisa kode tetap aman.

Function summary:
- accept_user_pattern(pattern_name, image_path=None)
    -> menyimpan (opsional) file image ke temp folder dan mengembalikan struktur dict.
- detect_all_patterns(df, user_pattern_name=None, user_image_path=None)
    -> API compatibility helper: mengembalikan tuple (chart_pattern, candle_pattern)
       berdasarkan input user. Jika tidak ada input user, mengembalikan ("Not provided", "Not provided").
- clear_temp_image(path)
    -> helper untuk menghapus file sementara jika dibuat.
"""

import os
import shutil
from datetime import datetime
from typing import Optional, Tuple

# Temp folder untuk menyimpan gambar user (jika ada)
TEMP_VISION_DIR = "data/temp_vision"
os.makedirs(TEMP_VISION_DIR, exist_ok=True)


def _safe_save_image(src_path: str) -> Optional[str]:
    """
    Jika user memberikan path ke image, salin ke folder temp dengan nama unik dan kembalikan path baru.
    Jika tidak ada atau file tidak valid, return None.
    """
    try:
        if not src_path:
            return None
        if not os.path.exists(src_path):
            # Bisa jadi input berupa bytes/stream, tapi page saat ini memberikan file path -> cek validitas
            return None
        # Nama unik berdasarkan timestamp
        base_name = os.path.basename(src_path)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        dest_name = f"{timestamp}_{base_name}"
        dest_path = os.path.join(TEMP_VISION_DIR, dest_name)
        shutil.copyfile(src_path, dest_path)
        return dest_path
    except Exception:
        return None


def accept_user_pattern(pattern_name: Optional[str], image_path: Optional[str] = None) -> dict:
    """
    Menerima input pola dari user.
    - pattern_name: nama pola chart/candlestick (string) atau None.
    - image_path: path lokal file gambar yang diupload user (opsional).
    Mengembalikan dict ringkas yang menyimpan sumber dan lokasi file (jika ada).

    Example return:
    {
      "chart_pattern": "Ascending Triangle",
      "candle_pattern": None,
      "image_path": "data/temp_vision/2025....png",
      "source": "user",
      "note": "User-provided pattern; automatic detection disabled."
    }
    """
    saved_path = _safe_save_image(image_path) if image_path else None

    # Jika user menyertakan satu nama pattern, kita masukkan ke chart_pattern by default.
    chart_pattern = pattern_name.strip() if isinstance(pattern_name, str) and pattern_name.strip() else None
    candle_pattern = None  # kita tidak melakukan deteksi candle otomatis

    return {
        "chart_pattern": chart_pattern,
        "candle_pattern": candle_pattern,
        "image_path": saved_path,
        "source": "user",
        "note": "User-provided pattern; automatic detection disabled."
    }


def detect_all_patterns(df, user_pattern_name: Optional[str] = None, user_image_path: Optional[str] = None) -> Tuple[str, str]:
    """
    Backwards-compatible API used in older code paths.

    - Jika user_pattern_name disediakan, kembalikan (chart_pattern, candle_pattern)
      dimana chart_pattern = "User: <name>" dan candle_pattern = "User: <name> (not specified)".
    - Jika tidak ada input user, kembalikan ("Not provided", "Not provided").

    NOTE: df parameter diterima untuk kompatibilitas tapi tidak dipakai (no auto detection).
    """
    try:
        if user_pattern_name and isinstance(user_pattern_name, str) and user_pattern_name.strip():
            name = user_pattern_name.strip()
            chart_label = f"User: {name}"
            candle_label = f"User: {name} (not specified)"
            # Optionally save the image if provided
            if user_image_path:
                saved = _safe_save_image(user_image_path)
                # We do not perform detection; only store image for audit if saved
                if saved:
                    chart_label += " [image_saved]"
            return chart_label, candle_label

        # No user input => explicitly return Not provided
        return "Not provided", "Not provided"
    except Exception:
        return "Not provided", "Not provided"


def clear_temp_image(path: str) -> bool:
    """
    Hapus file sementara yang dibuat oleh _safe_save_image.
    Return True jika sukses, False jika gagal / tidak ditemukan.
    """
    try:
        if not path:
            return False
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except Exception:
        return False


# --- backward compatibility alias (some modules might import detect_all_patterns directly) ---
# keep symbol name stable for imports like: from backend.vision_pattern import detect_all_patterns
# (already implemented above)

if __name__ == "__main__":
    # simple self-test
    demo = accept_user_pattern("Ascending Triangle", None)
    print("Demo accept_user_pattern:", demo)
    print("Demo detect_all_patterns (with name):", detect_all_patterns(None, user_pattern_name="Head and Shoulders"))
    print("Demo detect_all_patterns (none):", detect_all_patterns(None))
