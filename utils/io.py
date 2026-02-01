import base64
from typing import Dict, Any
from PIL import Image


def safe_open_image(file) -> Dict[str, Any]:
    try:
        image = Image.open(file)
        image.verify()
        file.seek(0)
        image = Image.open(file)
        file.seek(0)
        data = file.read()
        mime = "image/png" if (image.format or "").lower() == "png" else "image/jpeg"
        data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        return {
            "ok": True,
            "image": image,
            "meta": {
                "name": getattr(file, "name", "uploaded_image"),
                "size": image.size,
                "mode": image.mode,
            },
            "data_url": data_url,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
