#!/usr/bin/env python3
"""Source patches needed to run WinQuake inside a PDF."""
import sys, os

src = sys.argv[1]

p = os.path.join(src, "sys_null.c")
s = open(p).read()
if "emscripten.h" not in s:
    s = s.replace('#include "quakedef.h"', '#include "quakedef.h"\n#include <emscripten.h>', 1)
    old = "double Sys_FloatTime (void)\n{\n\tstatic double t;\n\t\n\tt += 0.1;\n\t\n\treturn t;\n}"
    new = "double Sys_FloatTime (void)\n{\n\treturn emscripten_get_now() / 1000.0;\n}"
    assert old in s, "Sys_FloatTime pattern not found"
    open(p, "w").write(s.replace(old, new, 1))
    print("  patched sys_null.c: real clock")

p = os.path.join(src, "common.c")
s = open(p).read()
old = ('\t\tCon_Printf ("Playing shareware version.\\n");\n'
       '\t\tif (com_modified)\n'
       '\t\t\tSys_Error ("You must have the registered version to use modified games");\n')
new = ('\t\tCon_Printf ("Playing shareware version.\\n");\n'
       '\t\tif (com_modified)\n'
       '\t\t\tCon_Printf ("Note: repacked game data.\\n");\n')
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("  patched common.c: allow repacked PAK")
