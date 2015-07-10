#!/usr/bin/env python

import os
import sys

# Add CREAD path to system path
cread_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not cread_root in sys.path:
    sys.path = [cread_root] + sys.path

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cread.settings")
    execute_from_command_line(sys.argv)

