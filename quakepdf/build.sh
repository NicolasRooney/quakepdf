#!/bin/bash
# Build Quake into a PDF.
# Usage:  ./build.sh [path/to/pak0.pak]

set -e
set -x

RESX=${RESX:-320}
RESY=${RESY:-200}
START_MAP=${START_MAP:-start}
PAK=${1:-data/pak0.pak}
QG=${QG:-../quakegeneric/source}

export NODE_PATH=/usr/share/nodejs:/usr/lib/nodejs

mkdir -p src out build

if [ ! -f src/quakedef.h ]; then
  cp "$QG"/*.c "$QG"/*.h src/
  rm -f src/quakegeneric_sdl2.c src/quakegeneric_w32.c \
        src/quakegeneric_dos.c src/quakegeneric_null.c

  sed -i "s/^#define\tBASEWIDTH\t320/#define\tBASEWIDTH\tQUAKEGENERIC_RES_X/;
          s/^#define\tBASEHEIGHT\t240/#define\tBASEHEIGHT\tQUAKEGENERIC_RES_Y/" src/vid_null.c

  # let -D override the resolution
  sed -i "s/^#define QUAKEGENERIC_RES_X 320/#ifndef QUAKEGENERIC_RES_X\n#define QUAKEGENERIC_RES_X 320\n#endif/;
          s/^#define QUAKEGENERIC_RES_Y 240/#ifndef QUAKEGENERIC_RES_Y\n#define QUAKEGENERIC_RES_Y 240\n#endif/" src/quakegeneric.h

  python3 patches/apply.py src
fi

CFLAGS="-O3 -std=gnu99 -DQUAKEGENERIC_RES_X=$RESX -DQUAKEGENERIC_RES_Y=$RESY -DQG_START_MAP=\"\\\"$START_MAP\\\"\" -Isrc"

OBJS="cd_null chase cl_demo cl_input cl_main cl_parse cl_tent cmd common
console crc cvar d_edge d_fill d_init d_modech d_part d_polyse d_scan d_sky
d_sprite d_surf d_vars d_zpoint draw host_cmd host in_null keys mathlib menu
model net_loop net_main net_none net_vcr nonintel pr_cmds pr_edict pr_exec
r_aclip r_alias r_bsp r_draw r_edge r_efrag r_light r_main r_misc r_part
r_sky r_sprite r_surf r_vars sbar screen snd_null sv_main sv_move sv_phys
sv_user sys_null vid_null view wad world zone quakegeneric quakegeneric_pdfjs"

for o in $OBJS; do
  eval emcc -c $CFLAGS "src/$o.c" -o "build/$o.o"
done

emcc -O3 \
  -sWASM=0 -sSINGLE_FILE=1 -sLEGACY_VM_SUPPORT=1 --closure 0 \
  -sWASM_ASYNC_COMPILATION=0 -sDYNAMIC_EXECUTION=0 \
  -sINITIAL_MEMORY=67108864 -sALLOW_MEMORY_GROWTH=0 -sASSERTIONS=0 -sINVOKE_RUN=1 \
  "-sEXPORTED_FUNCTIONS=['_main','_quakejs_tick','_key_to_quakekey']" \
  "-sEXPORTED_RUNTIME_METHODS=['FS','HEAPU8']" \
  build/*.o -lm -o out/quakegeneric.js

python3 pak_tools.py strip "$PAK" out/pak_min.pak --only-maps "$START_MAP" e1m1
python3 pak_tools.py embed out/data.js "id1/pak0.pak=out/pak_min.pak"

cat pre.js out/data.js out/quakegeneric.js > out/compiled.js

node --stack-size=8000 test_pdfenv.js out/compiled.js 40
node --stack-size=8000 test_input.js  out/compiled.js

python3 generate.py out/compiled.js out/quake.pdf --width "$RESX" --height "$RESY"

set +x
echo
echo "built out/quake.pdf ($(du -h out/quake.pdf | cut -f1))"
echo "open it in a Chromium-based browser."
