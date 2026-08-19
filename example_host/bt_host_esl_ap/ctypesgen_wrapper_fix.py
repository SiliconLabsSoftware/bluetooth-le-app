#!/usr/bin/env python3

import os
import sys
import argparse
import re

SECTION_1_ORIG = r'(\w+) \= os\.path\.abspath\((\1)\)'
SECTION_1_REPL = ' = os.path.abspath(os.path.join(os.path.dirname(__file__), '

SECTION_2_ORIG = r'Generated with:\n.+'
SECTION_2_REPL = 'Generated with ctypesgen.'

SECTION_3_ORIG = '# No libraries'
SECTION_3_REPL = '# Begin libraries\n'\
                 '\n'\
                 'n = os.path.splitext(os.path.basename(__file__))[0]\n'\
                 'if n.endswith("_wrapper"):\n'\
                 '    n = n[:-len("_wrapper")]\n'\
                 'p = sys.platform\n'\
                 'if p == "darwin":\n'\
                 '    _libs["{:s}.dylib".format(n)] = load_library(n)\n'\
                 'elif (p == "cygwin" or p == "win32" or p == "msys"):\n'\
                 '    _libs["{:s}.dll".format(n)] = load_library(n)\n'\
                 '# Posix\n'\
                 'else:\n'\
                 '    _libs["{:s}.so".format(n)] = load_library(n)\n'\
                 '\n'\
                 '# End libraries'

def normalize_comment_path(comment_line):
    """ Normalize comment line containing an absolute path and line number."""
    # Match lines starting with '#' followed by a path to a .c or .h file and a line number
    match = re.match(r'#\s*(.+\.(?:c|h))\s*:\s*(\d+)\s*$', comment_line.strip())
    if not match:
        return comment_line  # Leave unchanged if it doesn't match

    abs_path = match.group(1)
    line_num = match.group(2)

    # Extract only the basename of the file path
    basename = os.path.basename(abs_path)

    # Return normalized comment line
    return f"# {basename}: {line_num}"

def main():
    parser = argparse.ArgumentParser(
        description="ctypesgen Python wrapper fix")
    parser.add_argument(
        "file",
        help="Path to Python wrapper file to fix")
    args = parser.parse_args()
    try:
        with open(args.file, "r") as f:
            c = f.read()
    except FileNotFoundError:
        print("Python wrapper file not found: {:s}".format(args.file))
        sys.exit(1)
    ret = re.search(SECTION_1_ORIG, c)
    if ret == None:
        print("'{:s}' not found".format(SECTION_1_ORIG))
        sys.exit(2)
    variable = ret.group(0).split()[0]
    cm = re.sub(SECTION_1_ORIG, variable + SECTION_1_REPL + variable + "))", c)
    if cm == c:
        print("'{:s}' could not change".format(SECTION_1_ORIG))
        sys.exit(2)
    c = cm
    cm = re.sub(SECTION_2_ORIG, SECTION_2_REPL, c)
    if cm == c:
        print("'{:s}' not found".format(SECTION_2_ORIG))
        sys.exit(3)
    c = cm
    cm = c.replace(SECTION_3_ORIG, SECTION_3_REPL, 1)
    if cm == c:
        print("'{:s}' not found".format(SECTION_3_ORIG))
        sys.exit(4)

    lines = cm.splitlines()
    filtered_lines = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            # Normalize full-line comment if it contains a path and line number
            line = normalize_comment_path(line)
        else:
            # Check for inline comment with path and line number
            inline_match = re.search(r'#\s*(.+\.(?:c|h))\s*:\s*(\d+)\s*$', line)
            if inline_match:
                # Extract and normalize the comment part
                comment = inline_match.group(0)
                normalized = normalize_comment_path(comment)
                # Replace original comment with normalized version
                line = re.sub(r'#\s*(.+\.(?:c|h))\s*:\s*(\d+)\s*$', normalized, line)
            else:
                # Remove inline comment if not preceded by space
                line = re.sub(r'(?<!\s)#.*', '', line)
        filtered_lines.append(line)

    cm = "\n".join(filtered_lines)

    with open(args.file, "w") as f:
        f.write(cm)

if __name__ == "__main__":
    main()
