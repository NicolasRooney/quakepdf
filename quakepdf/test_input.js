/*
	test_input.js -- verify the full input path works:
	PDF pushbutton action -> key_down() -> pressed_keys -> key_queue
	-> QG_GetKey() -> Quake's key system -> player movement.

	Boots, settles, snapshots the framebuffer, holds a key, and checks
	that the view actually changed.
*/

const fs = require("fs");
const vm = require("vm");

const bundle = process.argv[2] || "out/compiled.js";
const fields = new Map();

function getField(name) {
	if (!fields.has(name)) fields.set(name, { value: "" });
	return fields.get(name);
}

const intervals = [];
const app = {
	setInterval(code, ms) { const h = { code }; intervals.push(h); return h; },
	clearInterval(h) { const i = intervals.indexOf(h); if (i > -1) intervals.splice(i, 1); },
	setTimeOut(code, ms) { return { code }; },
	alert(m) { console.log("[alert] " + m); },
};

const sandbox = {
	app, getField,
	Date, Math, JSON, Array, Object, String, Number, Boolean, Error, RegExp, Function,
	Uint8Array, Int8Array, Uint16Array, Int16Array, Uint32Array, Int32Array,
	Float32Array, Float64Array, ArrayBuffer, DataView, isNaN, parseInt, parseFloat,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

vm.runInContext(fs.readFileSync(bundle, "utf8"), sandbox, { timeout: 600000 });

const tick = intervals.find((h) => h.code.indexOf("_quakejs_tick") > -1);
if (!tick) { console.log("FAIL: no tick interval"); process.exit(1); }

function run(n) {
	for (let i = 0; i < n; i++) vm.runInContext(tick.code, sandbox, { timeout: 600000 });
}

function snapshot() {
	const out = [];
	for (let i = 0; i < 200; i++) {
		const f = fields.get("field_" + i);
		out.push(f ? f.value : "");
	}
	return out;
}

function diff(a, b) {
	let n = 0;
	for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) n++;
	return n;
}

run(40);
const before = snapshot();

vm.runInContext("key_down('w')", sandbox);
run(25);
vm.runInContext("key_up('w')", sandbox);
run(3);
const afterFwd = snapshot();

vm.runInContext("key_down('e')", sandbox);
run(25);
vm.runInContext("key_up('e')", sandbox);
run(3);
const afterTurn = snapshot();

const keyQueueBefore = vm.runInContext("key_queue.length + Object.keys(pressed_keys).length", sandbox);
vm.runInContext("key_pressed('x')", sandbox);   // escape -> opens menu
const pressedAfter = vm.runInContext("Object.keys(pressed_keys).length", sandbox);
run(10);
const afterMenu = snapshot();

console.log("scanlines changed after holding W (forward) :", diff(before, afterFwd), "/ 200");
console.log("scanlines changed after holding E (turn)    :", diff(afterFwd, afterTurn), "/ 200");
console.log("keystroke handler queued a key              :", pressedAfter > 0);
console.log("scanlines changed after ESC (menu)          :", diff(afterTurn, afterMenu), "/ 200");

const ok = diff(before, afterFwd) > 20 && diff(afterFwd, afterTurn) > 20 && pressedAfter > 0;
console.log("\n" + (ok ? "PASS: input path drives the engine" : "FAIL: input did not move the view"));
process.exit(ok ? 0 : 1);
