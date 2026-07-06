"""Qt (PySide6) UI package.

This is the only package in the application that imports PySide6. Core
modules (engine, config, stt, tts, ...) must never import from here at
module level so that ``--smoke`` stays Qt-free.
"""
