"""Import this BEFORE ctranslate2/faster_whisper.

The pip nvidia-* wheels drop their DLLs inside site-packages, which is not on the
Windows DLL search path, so CTranslate2 fails with
`Library cublas64_12.dll is not found or cannot be loaded`.
"""
import os
import sys
import glob

_added = []


def enable():
    if _added:
        return _added
    roots = [os.path.join(p, "nvidia") for p in sys.path if p.endswith("site-packages")]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for binpath in glob.glob(os.path.join(root, "*", "bin")):
            if os.path.isdir(binpath):
                try:
                    os.add_dll_directory(binpath)
                    _added.append(binpath)
                except OSError:
                    pass
    # also make them resolvable to child processes / older loaders
    if _added:
        os.environ["PATH"] = os.pathsep.join(_added) + os.pathsep + os.environ.get("PATH", "")
    return _added


enable()
