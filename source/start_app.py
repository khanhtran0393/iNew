#!/usr/bin/env python3
import sys
import os

# Add source directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.launcher import main

if __name__ == "__main__":
    main()
