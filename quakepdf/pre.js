var console = {
	log:   function (m) { Module.print(String(m)); },
	warn:  function (m) { Module.print(String(m)); },
	error: function (m) { Module.print(String(m)); },
	info:  function (m) { Module.print(String(m)); },
	debug: function () {},
	trace: function () {},
};

var Module = {};
var quake_interval = null;
var last_blit_ms = 0;
var __timeout_fns = [];

function __run_timeout(id) {
	var f = __timeout_fns[id];
	__timeout_fns[id] = null;
	if (f) f();
}

function setTimeout(fn, ms) {
	if (typeof fn === "string")
		return app.setTimeOut(fn, ms || 0);
	var id = __timeout_fns.length;
	__timeout_fns.push(fn);
	return app.setTimeOut("__run_timeout(" + id + ")", ms || 0);
}

var lines = [];
var CONSOLE_ROWS = 25;

function print_msg(msg) {
	lines.push(msg);
	if (lines.length > CONSOLE_ROWS)
		lines.shift();

	for (var i = 0; i < lines.length; i++) {
		globalThis.getField("console_" + (CONSOLE_ROWS - i - 1)).value = lines[i];
	}
}

Module.print = function (msg) {
	var max_len = 80;
	var num_lines = Math.ceil(msg.length / max_len) || 1;
	for (var i = 0, o = 0; i < num_lines; ++i, o += max_len)
		print_msg(msg.substr(o, max_len));
};
Module.printErr = Module.print;

var B64_LUT = null;

function b64_init() {
	B64_LUT = [];
	for (var i = 0; i < 128; i++)
		B64_LUT[i] = -1;
	var abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	for (var j = 0; j < 64; j++)
		B64_LUT[abc.charCodeAt(j)] = j;
}

function b64_decode(str) {
	if (B64_LUT === null)
		b64_init();

	var lut = B64_LUT;
	var len = str.length;
	while (len > 0 && str.charCodeAt(len - 1) === 61 /* '=' */)
		len--;

	var quads = (len / 4) | 0;
	var rem = len - quads * 4;
	var outlen = quads * 3 + (rem === 2 ? 1 : (rem === 3 ? 2 : 0));
	var out = new Uint8Array(outlen);

	var o = 0, i = 0, end = quads * 4;
	for (; i < end; i += 4) {
		var a = lut[str.charCodeAt(i)];
		var b = lut[str.charCodeAt(i + 1)];
		var c = lut[str.charCodeAt(i + 2)];
		var d = lut[str.charCodeAt(i + 3)];
		out[o++] = (a << 2) | (b >> 4);
		out[o++] = ((b & 15) << 4) | (c >> 2);
		out[o++] = ((c & 3) << 6) | d;
	}

	if (rem === 2) {
		out[o++] = (lut[str.charCodeAt(i)] << 2) | (lut[str.charCodeAt(i + 1)] >> 4);
	} else if (rem === 3) {
		var b2 = lut[str.charCodeAt(i + 1)];
		out[o++] = (lut[str.charCodeAt(i)] << 2) | (b2 >> 4);
		out[o++] = ((b2 & 15) << 4) | (lut[str.charCodeAt(i + 2)] >> 2);
	}

	return out;
}

function _fs() {
	return (typeof FS !== "undefined") ? FS : Module.FS;
}

function mkdir_p(path) {
	var fs = _fs();
	var parts = path.split("/");
	var cur = "";
	for (var i = 0; i < parts.length; i++) {
		if (parts[i] === "")
			continue;
		cur += "/" + parts[i];
		try { fs.mkdir(cur); } catch (e) { /* exists */ }
	}
}

function write_file(path, data) {
	var fs = _fs();
	var slash = path.lastIndexOf("/");
	if (slash > 0)
		mkdir_p(path.substring(0, slash));
	var stream = fs.open(path, "w+");
	fs.write(stream, data, 0, data.length, 0);
	fs.close(stream);
}

function install_game_files() {
	if (typeof embedded_files === "undefined" || embedded_files.length === 0)
		throw "Error: no game data embedded in this PDF.";

	for (var i = 0; i < embedded_files.length; i++) {
		var f = embedded_files[i];
		var t0 = Date.now();
		var bytes = b64_decode(f.b64);
		if (bytes.length < 64)
			throw "Error: embedded file " + f.name + " is empty.";
		write_file("/" + f.name, bytes);
		print_msg("loaded " + f.name + " (" + (bytes.length / 1048576).toFixed(1) +
			" MB in " + (Date.now() - t0) + " ms)");
		embedded_files[i].b64 = null;
	}
}

var SHADES = ["_", "::", "?", "//", "b", "#"];

var js_buffer = [];
var old_rows = [];
var pal_chars = null;
var fb_width = 0, fb_height = 0;

function create_framebuffer(width, height) {
	fb_width = width;
	fb_height = height;
	js_buffer = [];
	old_rows = [];
	for (var y = 0; y < height; y++) {
		var row = new Array(width);
		for (var x = 0; x < width; x++)
			row[x] = "_";
		js_buffer.push(row);
		old_rows.push(null);
	}
	pal_chars = new Array(256);
	for (var i = 0; i < 256; i++)
		pal_chars[i] = "_";
}

function set_palette(ptr) {
	var h = Module.HEAPU8;
	for (var i = 0; i < 256; i++)
		pal_chars[i] = SHADES[h[ptr + i]];
	for (var y = 0; y < old_rows.length; y++)
		old_rows[y] = null;
}

var fb_hist = null;

function update_framebuffer(ptr, width, height) {
	var t0 = Date.now();
	var fb = Module.HEAPU8;
	var pal = pal_chars;

	if (fb_hist !== null) {
		for (var hy = 0; hy < height; hy++) {
			var hb = ptr + hy * width;
			for (var hx = 0; hx < width; hx++)
				fb_hist[fb[hb + hx]]++;
		}
	}

	for (var y = 0; y < height; y++) {
		var row = js_buffer[y];
		var base = ptr + y * width;
		for (var x = 0; x < width; x++)
			row[x] = pal[fb[base + x]];

		var str = row.join("");
		if (str !== old_rows[y]) {
			old_rows[y] = str;
			globalThis.getField("field_" + (height - y - 1)).value = str;
		}
	}

	last_blit_ms = Date.now() - t0;
}

var pressed_keys = {};
var key_queue = [];

function key_pressed(key_str) {
	if (!key_str || key_str.length === 0)
		return;
	var qk = _key_to_quakekey(key_str.charCodeAt(0));
	if (qk === -1)
		return;
	pressed_keys[qk] = 2;
}

function key_down(key_str) {
	var qk = _key_to_quakekey(key_str.charCodeAt(0));
	if (qk === -1)
		return;
	pressed_keys[qk] = 1;
}

function key_up(key_str) {
	var qk = _key_to_quakekey(key_str.charCodeAt(0));
	if (qk === -1)
		return;
	pressed_keys[qk] = 0;
}

function reset_input_box() {
	globalThis.getField("key_input").value = "Click here, then type to play.";
}
app.setInterval("reset_input_box()", 1000);
