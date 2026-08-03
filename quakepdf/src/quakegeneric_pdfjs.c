/*
	quakegeneric_pdfjs.c -- QuakeGeneric backend for the JavaScript engine
	embedded in PDF readers (PDFium / Acrobat).

	There is no canvas, no WebGL, no audio, no DOM and no rAF in a PDF.
	Output goes to one AcroForm text field per scanline; input arrives
	from a text field's keystroke action and from pushbutton up/down
	actions. Main loop is app.setInterval().

	Modelled on ading2210/doompdf's doomgeneric_pdfjs.c.
*/

#include <emscripten.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#include "quakegeneric.h"

#ifndef QG_FIXED_STEP
#define QG_FIXED_STEP 0.05
#endif

static unsigned char qg_palette[768];
static unsigned char pal_shade[256];
static int pal_lum[256];
static int frame_count = 0;

#define LUMHIST_DECAY_SHIFT 1
#define RAMP_RECOMPUTE_FRAMES 15
#define RAMP_SAMPLE_STEP 4

static int lum_hist[256];
static int ramp_thresh[5] = { 23, 44, 66, 95, 139 };

static void rebuild_shade_table(void)
{
	int i;

	for (i = 0; i < 256; i++)
	{
		int y = pal_lum[i];
		if (y > ramp_thresh[4])      pal_shade[i] = 0;
		else if (y > ramp_thresh[3]) pal_shade[i] = 1;
		else if (y > ramp_thresh[2]) pal_shade[i] = 2;
		else if (y > ramp_thresh[1]) pal_shade[i] = 3;
		else if (y > ramp_thresh[0]) pal_shade[i] = 4;
		else                         pal_shade[i] = 5;
	}

	EM_ASM({ set_palette($0); }, pal_shade);
}

static void update_shade_ramp(void)
{
	int i, total = 0, run = 0, cut = 0;
	int next[5];

	for (i = 0; i < 256; i++)
		total += lum_hist[i];
	if (total < 256)
		return;

	for (i = 0; i < 256 && cut < 5; i++)
	{
		run += lum_hist[i];
		while (cut < 5 && (long)run * 6 >= (long)total * (cut + 1))
			next[cut++] = i;
	}
	while (cut < 5)
		next[cut++] = 255;

	for (i = 1; i < 5; i++)
		if (next[i] < next[i - 1])
			next[i] = next[i - 1];
	for (i = 0; i < 5; i++)
		ramp_thresh[i] = next[i];

	for (i = 0; i < 256; i++)
		lum_hist[i] >>= LUMHIST_DECAY_SHIFT;

	rebuild_shade_table();
}

void QG_SetPalette(unsigned char palette[768])
{
	int i;

	memcpy(qg_palette, palette, 768);

	for (i = 0; i < 256; i++)
	{
		int r = palette[i * 3 + 0];
		int g = palette[i * 3 + 1];
		int b = palette[i * 3 + 2];
		pal_lum[i] = (77 * r + 150 * g + 29 * b) >> 8;
	}

	rebuild_shade_table();
}

double get_time(void)
{
	return emscripten_get_now();
}

void QG_Init(void)
{
	EM_ASM({
		create_framebuffer($0, $1);
	}, QUAKEGENERIC_RES_X, QUAKEGENERIC_RES_Y);
}

void QG_DrawFrame(void *pixels)
{
	const unsigned char *p = (const unsigned char *)pixels;
	int x, y;

	for (y = 0; y < QUAKEGENERIC_RES_Y; y += RAMP_SAMPLE_STEP)
	{
		const unsigned char *row = p + y * QUAKEGENERIC_RES_X;
		for (x = 0; x < QUAKEGENERIC_RES_X; x += RAMP_SAMPLE_STEP)
			lum_hist[pal_lum[row[x]]]++;
	}

	if (frame_count % RAMP_RECOMPUTE_FRAMES == 0)
		update_shade_ramp();

	EM_ASM({
		update_framebuffer($0, $1, $2);
	}, pixels, QUAKEGENERIC_RES_X, QUAKEGENERIC_RES_Y);
}

EMSCRIPTEN_KEEPALIVE
int key_to_quakekey(int key)
{
	switch (key)
	{
		case 'w': case 'W': return K_UPARROW;
		case 's': case 'S': return K_DOWNARROW;
		case 'a': case 'A': return ',';
		case 'd': case 'D': return '.';
		case 'q': case 'Q': return K_LEFTARROW;
		case 'e': case 'E': return K_RIGHTARROW;
		case ' ':           return K_CTRL;
		case 'f': case 'F': return K_SPACE;
		case 'r': case 'R': return K_ENTER;
		case 'x': case 'X': return K_ESCAPE;
		case 'z': case 'Z': return K_TAB;
		case '\t':          return K_TAB;
		case '\r': case '\n': return K_ENTER;
		case 27:            return K_ESCAPE;
		case 8:             return K_BACKSPACE;
		default:
			if (key >= '0' && key <= '9') return key;
			if (key >= 'A' && key <= 'Z') return tolower(key);
			if (key >= 32 && key < 127)   return key;
			return -1;
	}
}

int QG_GetKey(int *down, int *key)
{
	int key_data = EM_ASM_INT({
		if (key_queue.length === 0)
			return 0;
		var kd = key_queue.shift();
		return (1 << 16) | (kd[1] << 8) | (kd[0] & 0xFF);
	});

	if (key_data == 0)
		return 0;

	*down = (key_data >> 8) & 0xFF;
	*key  = key_data & 0xFF;
	return 1;
}

void QG_GetMouseMove(int *x, int *y)
{
	*x = 0;
	*y = 0;
}

void QG_GetJoyAxes(float *axes)
{
	int i;
	for (i = 0; i < QUAKEGENERIC_JOY_MAX_AXES; i++)
		axes[i] = 0.0f;
}

void QG_Quit(void)
{
	EM_ASM({
		if (typeof quake_interval !== "undefined" && quake_interval !== null) {
			app.clearInterval(quake_interval);
			quake_interval = null;
		}
		print_msg("=== engine shut down ===");
	});
}

EMSCRIPTEN_KEEPALIVE
void quakejs_tick(void)
{
	double start, end;

	EM_ASM({
		for (var k in pressed_keys) {
			key_queue.push([k | 0, pressed_keys[k] ? 1 : 0]);
			if (pressed_keys[k] === 0)
				delete pressed_keys[k];
			if (pressed_keys[k] === 2)
				pressed_keys[k] = 0;
		}
	});

	start = get_time();
	QG_Tick(QG_FIXED_STEP);
	end = get_time();

	frame_count++;
	if (frame_count % 10 == 0)
	{
		int ms = (int)(end - start);
		printf("frame %i: %i ms engine", frame_count, ms);
		EM_ASM({
			print_msg("  (+ " + last_blit_ms + " ms blit)");
		});
	}
}

static char *qg_argv[8];

int main(void)
{
	int argc = 0;

	printf("quakepdf: %ix%i, fixed step %ims\n",
		QUAKEGENERIC_RES_X, QUAKEGENERIC_RES_Y, (int)(QG_FIXED_STEP * 1000));

	EM_ASM({
		install_game_files();
	});

	qg_argv[argc++] = "quake";
#ifdef QG_START_MAP
	qg_argv[argc++] = "+map";
	qg_argv[argc++] = QG_START_MAP;
#endif
	qg_argv[argc] = 0;

	QG_Create(argc, qg_argv);

	EM_ASM({
		print_msg("=== engine running ===");
		quake_interval = app.setInterval("_quakejs_tick()", 1);
	});

	return 0;
}
