#!/usr/bin/env python3
"""Atalho: python run.py [arquivo.wiff ...]"""
import sys

from openpeakview.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
