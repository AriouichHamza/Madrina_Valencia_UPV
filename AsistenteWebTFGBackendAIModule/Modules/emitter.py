from __future__ import annotations

import sys
from Modules.student import Alumno


"""
Emitter class for sending lightweight progress, completion, and student result
messages over stdout. Useful for reporting execution status and results from a
child process back to a parent process in a simple text-based protocol.
"""
"""Emit a progress update using the format: progress <progress> <state>."""
"""Emit a completion notification using the format: done <time_elapsed>."""
"""Emit a student record using the format: new-calificado <alumno.to_json()>."""


class Emitter:
    # Stdout is used as a lightweight protocol to report progress/results to the parent process.
    def emit_progress(self, progress, state):
        sys.stdout.write(f"progress {progress} {state}\n")
        
    def emit_done(self, time_elapsed):
        sys.stdout.write(f"done {time_elapsed}\n")
        
    def emit_student(self, alumno : Alumno):
        sys.stdout.write(f"new-calificado {alumno.to_json()}\n")

    def emit_error(self, message):
        clean_message = str(message).replace("\r", " ").replace("\n", " ").strip()
        sys.stdout.write(f"error {clean_message}\n")
