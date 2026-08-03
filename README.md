# QuakePDF

Quake's software renderer running entirely inside a PDF file.

This project leverages the JavaScript engine embedded in modern PDF readers to execute the game, utilizing a technique similar to [doompdf](https://github.com/ading2210/doompdf). The resulting `quake.pdf` is highly optimized, weighing in at just 9.7 MB, and requires a Chromium-based browser to run.


## Building from Source

To compile QuakePDF, you will need a copy of the shareware `pak0.pak` and Emscripten.

**Prerequisites:**

* `NODE_PATH` must be set to `/usr/share/nodejs` so the compiler can locate the acorn optimizer.


* Emscripten (version 3.1.6). Using another version will likely be a pain, but I put in some patches that _might_ work. Build from source with:

```bash
git clone https://github.com/emscripten-core/emsdk
cd emsdk && ./emsdk install 3.1.6 && ./emsdk activate 3.1.6 && source ./emsdk_env.sh
```


**Build Command:**

```bash
./build.sh path/to/pak0.pak

```

> **Note:** The build process utilizes a custom tool (`pak_tools.py`) to strip the PAK file of unusable files.
> 
> 

## Credits & Acknowledgements

* [erysdren/quakegeneric](https://github.com/erysdren/quakegeneric): The doomgeneric-style WinQuake port this builds upon.


* [ading2210/doompdf](https://github.com/ading2210/doompdf): Inspiration for the scanline text-field framebuffer and the equal-width character set.


* **id Software:** Creators of WinQuake.



## License

This repository is licensed under the GNU GPL v2.

```
nicolasrooney - Quake running inside a PDF file
Copyright (C) 2026 nicolasrooney

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
```
