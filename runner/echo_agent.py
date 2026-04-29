#!/usr/bin/env python3
"""Test fixture: an agent that prints a hardcoded answer regardless of input."""
import os
import sys

_ = sys.stdin.read()
scratch = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
assert os.path.isdir(scratch), f"scratch dir not found: {scratch}"

print("$5466.31")
