/*
	test_pdfenv.js -- run the compiled bundle in an environment that
	mimics a PDF reader's JavaScript engine.

	The environment deliberately provides ONLY what PDFium provides:
	  - no WebAssembly (deleted from the global object)
	  - no DOM, no window, no document, no canvas, no fetch, no atob
	  - no console
	  - an `app` object with setInterval / clearInterval / alert
	  - a `getField(name)` returning an object with a `.value` property

  NOTE: Patch to add if you are using a different Emscripten:
  
  console: {
	  println: function () {}, clear: function () {},
	  show: function () {},    hide: function () {},
  },

	Usage: node test_pdfenv.js <compiled.js> [frames] [--dump out.txt]
*/

const fs = require("fs");
const vm = require("vm");

const bundle = process.argv[2] || "out/compiled.js";
const FRAMES = parseInt(process.argv[3] || "60", 10);
const dumpIdx = process.argv.indexOf("--dump");
const dumpPath = dumpIdx > -1 ? process.argv[dumpIdx + 1] : null;

const fields = new Map();
let fieldWrites = 0;

function getField(name) {
	if (!fields.has(name)) {
		fields.set(name, { _v: "" });
		Object.defineProperty(fields.get(name), "value", {
			get() { return this._v; },
			set(v) { this._v = String(v); fieldWrites++; },
		});
	}
	return fields.get(name);
}

const intervals = [];
const app = {
	setInterval(code, ms) { const h = { code, ms }; intervals.push(h); return h; },
	clearInterval(h) { const i = intervals.indexOf(h); if (i > -1) intervals.splice(i, 1); },
	alert(msg) { process.stdout.write("[app.alert] " + msg + "\n"); },
};

const sandbox = {
	app,
	getField,
	Date, Math, JSON, Array, Object, String, Number, Boolean, Error, RegExp,
	Uint8Array, Int8Array, Uint16Array, Int16Array, Uint32Array, Int32Array,
	Float32Array, Float64Array, ArrayBuffer, DataView, Function, isNaN, parseInt,
	parseFloat, undefined: undefined, NaN, Infinity,
};
sandbox.globalThis = sandbox;

vm.createContext(sandbox);

if (typeof sandbox.WebAssembly !== "undefined") {
	console.log("FATAL: WebAssembly leaked into the sandbox");
	process.exit(1);
}

const code = fs.readFileSync(bundle, "utf8");
console.log(`bundle: ${(code.length / 1048576).toFixed(2)} MB of JavaScript`);
console.log("sandbox: no WebAssembly, no DOM, no console, no atob\n");

let t0 = Date.now();
try {
	vm.runInContext(code, sandbox, { filename: bundle, timeout: 600000 });
} catch (e) {
	console.log("BOOT FAILED: " + String(e && e.message ? e.message : e));
	if (e && e.stack) console.log(e.stack.split("\n").slice(1, 6).map(function(l){return "   " + l.trim().slice(0, 120);}).join("\n"));
	dumpConsole();
	process.exit(1);
}
const bootMs = Date.now() - t0;

function dumpConsole() {
	console.log("\n--- in-PDF console (last 25 lines) ---");
	for (let i = 24; i >= 0; i--) {
		const f = fields.get("console_" + i);
		if (f && f._v) console.log("  | " + f._v);
	}
}

dumpConsole();
console.log(`\nboot: ${bootMs} ms, ${fieldWrites} field writes so far`);

if (intervals.length === 0) {
	console.log("\nNo interval registered - engine never reached its main loop.");
	process.exit(1);
}

const tickHandle = intervals.find((h) => h.code.indexOf("_quakejs_tick") > -1);
if (!tickHandle) {
	console.log("\nNo tick interval found. Registered: " +
		intervals.map((h) => h.code).join(", "));
	process.exit(1);
}

if (process.argv.indexOf("--hist") > -1) {
	vm.runInContext("fb_hist = new Array(256); for (var i=0;i<256;i++) fb_hist[i]=0;", sandbox);
}

console.log(`\nrunning ${FRAMES} frames...`);
const times = [];
for (let i = 0; i < FRAMES; i++) {
	fieldWrites = 0;
	const s = process.hrtime.bigint();
	try {
		vm.runInContext(tickHandle.code, sandbox, { timeout: 600000 });
	} catch (e) {
		console.log(`frame ${i} threw: ` + (e && e.stack ? e.stack : e));
		break;
	}
	times.push(Number(process.hrtime.bigint() - s) / 1e6);
}

if (times.length) {
	const sorted = [...times].sort((a, b) => a - b);
	const sum = times.reduce((a, b) => a + b, 0);
	console.log(`  frames run : ${times.length}`);
	console.log(`  first frame: ${times[0].toFixed(1)} ms`);
	console.log(`  mean       : ${(sum / times.length).toFixed(1)} ms`);
	console.log(`  median     : ${sorted[sorted.length >> 1].toFixed(1)} ms`);
	console.log(`  best       : ${sorted[0].toFixed(1)} ms`);
	console.log(`  last 10 avg: ${(times.slice(-10).reduce((a, b) => a + b, 0) / Math.min(10, times.length)).toFixed(1)} ms`);
}

const rows = [];
for (let i = 0; ; i++) {
	const f = fields.get("field_" + i);
	if (!f) break;
	rows.push(f._v);
}
console.log(`\nscanline fields populated: ${rows.length}`);
const nonEmpty = rows.filter((r) => r && r.length > 0).length;
console.log(`non-empty scanlines      : ${nonEmpty}`);

if (rows.length) {
	const widths = new Set(rows.filter((r) => r).map((r) => r.length));
	console.log(`distinct row lengths     : ${[...widths].slice(0, 5).join(", ")}`);
}

if (process.argv.indexOf("--hist") > -1) {
	const h = vm.runInContext("fb_hist", sandbox);
	const total = h.reduce((a, b) => a + b, 0);
	const pairs = h.map((c, i) => [i, c]).filter((p) => p[1] > 0).sort((a, b) => b[1] - a[1]);
	console.log(`\npalette indices used: ${pairs.length} of 256, ${total} pixel samples`);
	console.log("  top 12 by frequency: " +
		pairs.slice(0, 12).map((p) => `${p[0]}(${(100 * p[1] / total).toFixed(1)}%)`).join(" "));
}

dumpConsole();

if (dumpPath && rows.length) {
	fs.writeFileSync(dumpPath, rows.slice().reverse().join("\n") + "\n");
	console.log(`\nframebuffer written to ${dumpPath}`);
}
