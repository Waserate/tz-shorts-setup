"""Every machine-specific path in one place.

The scripts were written on one PC with hard-coded paths (C:\\Users\\Admin\\..., N:\\...).
This module works them out for whoever runs it, so the same files run on any Windows
user account. Import it instead of writing a path into a script.
"""
import glob
import os

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(PIPELINE_DIR, "backup")
MODELS_DIR = os.path.join(PIPELINE_DIR, "models", "ct2")

_CAPCUT = os.path.join(os.environ["LOCALAPPDATA"], "CapCut")
CAPCUT_ROOT = os.path.join(_CAPCUT, "User Data", "Projects", "com.lveditor.draft")


def _capcut_app_dir():
    """Newest installed CapCut version that ships the system fonts we measure with."""
    found = glob.glob(os.path.join(_CAPCUT, "Apps", "*", "Resources", "Font", "SystemFont"))
    if not found:
        raise FileNotFoundError(
            f"CapCut fonts not found under {_CAPCUT}\\Apps - install CapCut and open it once")

    def ver(p):
        name = p.split(os.sep)[-4]
        return tuple(int(x) if x.isdigit() else 0 for x in name.split("."))

    return max(found, key=ver).rsplit(os.sep + "Resources", 1)[0]


CAPCUT_APP_DIR = _capcut_app_dir()
APP_VER = os.path.basename(CAPCUT_APP_DIR)
FONT_DIR = os.path.join(CAPCUT_APP_DIR, "Resources", "Font", "SystemFont")


def whisper_device():
    """('cuda', 'int8') on an NVIDIA card, else ('cpu', 'int8') - much slower but works."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "int8"
    except Exception:
        pass
    return "cpu", "int8"


os.makedirs(BACKUP_DIR, exist_ok=True)
