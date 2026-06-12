"""
title: Code Interpreter (Python + R)
author: local
version: 1.0.0
description: Execute Python or R code and return the output.
"""

import subprocess
import tempfile
import os


class Tools:
    def __init__(self):
        pass

    async def run_python(self, code: str) -> str:
        """
        Execute Python code and return stdout/stderr output.
        Use this when the user asks to run, calculate, or analyze something with Python.
        :param code: Python code to execute
        :return: execution output
        """
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        try:
            result = subprocess.run(
                ["python3", tmp],
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            return output.strip() or "(No output)"
        except subprocess.TimeoutExpired:
            return "Error: execution timed out (30 second limit)"
        finally:
            os.unlink(tmp)

    async def run_r(self, code: str) -> str:
        """
        Execute R code and return stdout/stderr output.
        Use this when the user asks to run statistical analysis, ggplot2 visualization, or any R code.
        :param code: R code to execute
        :return: execution output
        """
        with tempfile.NamedTemporaryFile(suffix=".R", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        try:
            result = subprocess.run(
                ["Rscript", tmp],
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            return output.strip() or "(No output)"
        except subprocess.TimeoutExpired:
            return "Error: execution timed out (60 second limit)"
        except FileNotFoundError:
            return "Error: Rscript not found. Please ensure R is installed."
        finally:
            os.unlink(tmp)
