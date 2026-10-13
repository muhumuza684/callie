const $ = id => document.getElementById(id);
const P = d => `<svg viewBox="0 0 24 24"><path d="${d}"/></svg>`;
const I = {
  phone: P("M6.6 10.8a15 15 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11 11 0 0 0 3.6.6 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.6 3.6a1 1 0 0 1-.25 1z"),
  mic: P("M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V22h2v-3.1A7 7 0 0 0 19 12z"),
  plus: P("M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z"),
  people: P("M16 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3zM8 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0 2c-2.3 0-7 1.2-7 3.5V19h14v-2.5C15 14.2 10.3 13 8 13zm8 0c-.3 0-.6 0-1 .1 1.2.8 2 1.9 2 3.4V19h6v-2.5C23 14.2 18.3 13 16 13z"),
  clock: P("M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm.5 5H11v6l5.2 3.1.8-1.3-4.5-2.7z"),
  cal: P("M7 2v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2zm12 8v10H5V10z"),
  gear: P("M19.4 13a7.9 7.9 0 0 0 0-2l2-1.6a.5.5 0 0 0 .1-.6l-1.9-3.3a.5.5 0 0 0-.6-.2l-2.4 1a7.4 7.4 0 0 0-1.7-1l-.4-2.5a.5.5 0 0 0-.5-.4h-3.8a.5.5 0 0 0-.5.4l-.4 2.5a7.4 7.4 0 0 0-1.7 1l-2.4-1a.5.5 0 0 0-.6.2L2.5 8.8a.5.5 0 0 0 .1.6l2 1.6a7.9 7.9 0 0 0 0 2l-2 1.6a.5.5 0 0 0-.1.6l1.9 3.3a.5.5 0 0 0 .6.2l2.4-1a7.4 7.4 0 0 0 1.7 1l.4 2.5a.5.5 0 0 0 .5.4h3.8a.5.5 0 0 0 .5-.4l.4-2.5a7.4 7.4 0 0 0 1.7-1l2.4 1a.5.5 0 0 0 .6-.2l1.9-3.3a.5.5 0 0 0-.1-.6zM12 15.5A3.5 3.5 0 1 1 15.5 12 3.5 3.5 0 0 1 12 15.5z"),
};
const G = ["#ffb36b,#ff7a59", "#b69cff,#7b5cff", "#6fd3ff,#3b8bff", "#ff9fb2,#ff6f91", "#7be0a1,#2fa866", "#f6d365,#fda085"];
let LABEL = {}, vprof = { rate: 1, pitch: 1, speech: 1, gender: "f", lang: "en-US" }, hb, LANGLABEL = {}, warnedLang = {};
const MIN_RING = 1600;
let S = { contacts: [], recents: [], schedule: [] };
let ws, ctx, stream, node, cur, callId = 0, busy = false, muted = false, ringId, timerId, t0;
let wake = null, heard = false, silent = 0, micWarned = false, testStream, testCtx, testRaf;
let pending = 0, gen = 0, speaking = false, minTurn = 0, voice = null, audioNext = 0, audioChain = Promise.resolve();
const sources = new Set(), fired = new Set();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const esc = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const find = id => S.contacts.find(c => c.id === id);
const av = (c, s = 46) => `<div class="av" style="background:linear-gradient(135deg,${G[c.color % G.length]});width:${s}px;height:${s}px">${esc(c.name[0].toUpperCase())}</div>`;
const TABNAMES = ["contacts", "recents", "schedule", "settings"];
const view = v => { document.body.dataset.v = v; if (TABNAMES.includes(v)) document.body.dataset.tab = v; };
const home = () => document.body.dataset.tab || "contacts";
// What people see: calm, plain wording. Technical detail is never shown; it is kept for the "Report a problem" email.
const NOTICES = {
  net: "Your connection is weak. Please try again in a moment.",
  busy: "Callie is busy right now. Please try again shortly.",
  mic: "We can't hear you. Please check that your microphone isn't muted.",
  micaccess: "We couldn't use your microphone. Please allow microphone access and try again.",
  micblocked: "Microphone access is blocked. Please allow it in your browser's site settings, then try again.",
  micnone: "No microphone was found on this device.",
  micbusy: "Your microphone is being used by another app. Please close it and try again.",
  secure: "Callie needs a secure connection to use the microphone. Please open the secure link.",
  config: "Callie is unavailable right now. Please try again later.",
  generic: "Something went wrong. Please try again.",
};
const REF = (() => { let r = localStorage.getItem("ref"); if (!r) { r = Math.random().toString(36).slice(2, 8).toUpperCase(); localStorage.setItem("ref", r); } return r; })();
const problems = [];
function note(code, detail = "") { problems.push(code + (detail ? ":" + detail : "") + "@" + new Date().toTimeString().slice(0, 5)); if (problems.length > 6) problems.shift(); }
window.addEventListener("error", e => note("js", String(e.message || "").slice(0, 40)));
window.addEventListener("unhandledrejection", e => { note("js", String((e.reason && e.reason.name) || "rejected").slice(0, 40)); e.preventDefault(); });
function writeTo(addr) {
  const subject = "Callie support (" + REF + ")";
  const body = "Please describe what happened:\n\n\n\n--- please keep these lines ---\nRef: " + REF + "\nApp: v" + (S.version || "?") + "\nDevice: " + navigator.userAgent + "\nRecent: " + (problems.join(" ") || "none");
  const q = "&su=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) location.href = "mailto:" + addr + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
  else window.open("https://mail.google.com/mail/?view=cm&fs=1&to=" + encodeURIComponent(addr) + q, "_blank", "noopener");
}
const toast = m => { $("toast").textContent = m; $("toast").classList.add("on"); setTimeout(() => $("toast").classList.remove("on"), 3500); };
async function api(p, m = "GET", b) {
  const r = await fetch(p, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined });
  if (!r.ok) { const e = new Error(String(r.status)); e.status = r.status; throw e; }
  return r.json();
}
const t12 = hm => { const [h, m] = hm.split(":").map(Number); return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`; };

// ---------- lists ----------
function draw() {
  $("list").innerHTML = S.contacts.map(c => `<div class="row" data-call="${c.id}">${av(c)}<div><b>${esc(c.name)}</b><small>${LABEL[c.voice] || c.voice}${c.lang && c.lang !== "en" ? " · " + LANGLABEL[c.lang] : ""}</small></div><button class="x" data-delc="${c.id}">✕</button></div>`).join("");
  $("rec").innerHTML = S.recents.filter(r => find(r.contact)).map(r => {
    const c = find(r.contact), d = new Date(r.at), today = d.toDateString() === new Date().toDateString();
    return `<div class="row" data-call="${c.id}">${av(c)}<div><b>${esc(c.name)}</b></div><span class="end">${today ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : d.toLocaleDateString([], { weekday: "short" })}</span></div>`;
  }).join("");
  $("sch").innerHTML = S.schedule.filter(s => find(s.contact)).map(s => {
    const c = find(s.contact);
    return `<div class="row">${av(c)}<div><b>${esc(c.name)}</b><small>${t12(s.time)} · daily</small></div><div class="tog ${s.on ? "on" : ""}" data-tog="${s.id}"></div><button class="x" data-dels="${s.id}">✕</button></div>`;
  }).join("");
  $("sc").innerHTML = S.contacts.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
}
async function load() {
  S = await api("/api/state");
  LABEL = Object.fromEntries((S.types || []).map(t => [t.id, t.label]));
  LANGLABEL = Object.fromEntries((S.langs || []).map(l => [l.id, l.label]));
  if (!$("lang").children.length) $("lang").innerHTML = (S.langs || []).map(l => `<option value="${l.id}">${l.label}</option>`).join("");
  if (!$("chips").children.length) $("chips").innerHTML = (S.types || []).map((t, i) => `<button class="chip${i ? "" : " on"}" data-voice="${t.id}">${t.label}</button>`).join("");
  $("memtog").classList.toggle("on", !!(S.settings && S.settings.memory));
  $("mails").innerHTML = (S.support || []).map(a => `<div class="mail"><span>${esc(a)}</span><button class="mini" data-act="copy" data-addr="${esc(a)}">Copy</button><button class="mini pri" data-act="write" data-addr="${esc(a)}">Write</button></div>`).join("");
  $("ref").textContent = REF;
  $("built").textContent = "Built in Uganda, by Bryt Ma Tech UG" + (S.version ? " · v" + S.version : "");
  draw();
}
$("tabs").innerHTML = [["contacts", "Contacts", I.people], ["recents", "Recents", I.clock], ["schedule", "Schedule", I.cal], ["settings", "Settings", I.gear]]
  .map(t => `<button class="tab" data-tab="${t[0]}">${t[2]}${t[1]}</button>`).join("");
$("addc").innerHTML = I.plus; $("adds").innerHTML = I.plus;
$("notify").classList.toggle("on", localStorage.getItem("notify") === "1");

// ---------- tones & speech ----------
function tone(freqs, dur, vol = 0.07) {
  if (!ctx) return;
  const g = ctx.createGain(); g.gain.value = vol; g.connect(ctx.destination);
  freqs.forEach(f => { const o = ctx.createOscillator(); o.frequency.value = f; o.connect(g); o.start(); o.stop(ctx.currentTime + dur); });
}
// ---------- ringtones (synthesised in the browser, no audio files) ----------
const B = { A4: 440, C5: 523.25, E5: 659.25, G5: 783.99, C6: 1046.5, E6: 1318.5 };
const RINGS = {
  classic: { label: "Classic", cycle: 3000, notes: [{ f: [440, 480], at: 0, d: 1.0, type: "sine", vol: .07, hold: true }] },
  chime:   { label: "Chime",   cycle: 2800, notes: [B.E5, B.G5, B.C6, B.E6].map((f, i) => ({ f: [f], at: i * .18, d: .9, type: "sine", vol: .08 })) },
  marimba: { label: "Marimba", cycle: 2400, notes: [B.C5, B.E5, B.G5, B.E5, B.C5, B.G5].map((f, i) => ({ f: [f], at: i * .15, d: .28, type: "triangle", vol: .12 })) },
  pulse:   { label: "Pulse",   cycle: 2000, notes: [0, .26, .52].map(at => ({ f: [880], at, d: .14, type: "square", vol: .035 })) },
  gentle:  { label: "Gentle",  cycle: 3600, notes: [{ f: [B.A4, B.C5, B.E5], at: 0, d: 1.9, type: "sine", vol: .05, att: .35 }] },
};
function playRing(name, c = ctx) {
  if (!c) return;
  (RINGS[name] || RINGS.classic).notes.forEach(n => {
    const t = c.currentTime + n.at, g = c.createGain();
    g.gain.setValueAtTime(.0001, t);
    g.gain.exponentialRampToValueAtTime(n.vol, t + (n.att || .01));
    if (n.hold) g.gain.setValueAtTime(n.vol, t + n.d - .08);
    g.gain.exponentialRampToValueAtTime(.0001, t + n.d);
    g.connect(c.destination);
    n.f.forEach(f => { const o = c.createOscillator(); o.type = n.type; o.frequency.value = f; o.connect(g); o.start(t); o.stop(t + n.d + .05); });
  });
}
function startRing(incoming = false) {
  stopRing();
  const pick = incoming ? (localStorage.getItem("ring") || "classic") : "classic";   // outgoing calls keep a plain ringback
  const buzz = () => { if (incoming && navigator.vibrate) navigator.vibrate([500, 250, 500]); };
  if (pick === "phone") { buzz(); ringId = setInterval(buzz, 3000); return; }          // the phone's own notification sound plays instead
  playRing(pick); buzz();
  ringId = setInterval(() => { playRing(pick); buzz(); }, RINGS[pick].cycle);
}
function stopRing() { clearInterval(ringId); if (navigator.vibrate) navigator.vibrate(0); }
let inflight = [], voiceFailed = false;
const FEM = /zira|aria|jenny|samantha|hazel|susan|catherine|sonia|libby|emma|michelle|ava|female|hortense|julie|denise|elvira|helena|sabina|paola|xiaoxiao|xiaoyi|huihui|yaoyao|swara|kalpana|zariyah|hoda|laila|zuri|francisca|maria|brenda|catarina|raquel/i;
const MAL = /david|mark|guy|ryan|george|alex|james|brian|davis|eric|roger|(?<!fe)male|paul|henri|claude|alvaro|pablo|raul|jorge|yunxi|yunjian|kangkang|yunyang|madhur|hemant|hamed|shakir|naayf|rafiki|antonio|felipe|donato|fabrice/i;
function pickVoice(g = "f", lang = vprof.lang || "en-US") {
  const all = speechSynthesis.getVoices(), base = lang.slice(0, 2).toLowerCase();
  let vs = all.filter(v => v.lang.toLowerCase().startsWith(base));
  if (!vs.length && all.length) {
    if (base !== "en" && !warnedLang[base]) { warnedLang[base] = 1; toast("This language has no installed voice on your device, so a default voice is used."); }
    vs = all.filter(v => v.lang.startsWith("en"));
  }
  if (voiceFailed && vs.some(v => v.localService)) vs = vs.filter(v => v.localService);
  const re = g === "m" ? MAL : FEM, other = g === "m" ? FEM : MAL;
  const match = vs.filter(v => re.test(v.name) && !other.test(v.name));
  return match.find(v => /natural|online/i.test(v.name)) || match[0] || vs.find(v => !other.test(v.name)) || vs[0] || null;
}
speechSynthesis.onvoiceschanged = () => { voice = pickVoice(vprof.gender); }; voice = pickVoice(vprof.gender);
function syncSpeaking() {
  const sp = pending > 0;
  if (sp === speaking) return;
  speaking = sp; document.querySelector(".stage").classList.toggle("talk", sp);
  const tell = () => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "tts_state", speaking: speaking })); };
  tell(); clearInterval(hb); if (sp) hb = setInterval(tell, 5000);   // heartbeat: the server forgets a silent 'speaking' state
}
// Online (cloud) browser voices go silent when the network blocks them: switch to a local voice and replay.
function useLocalVoice() {
  if (voiceFailed) return;
  voiceFailed = true; voice = pickVoice(vprof.gender);
  const redo = inflight.map(i => i.text);
  stopSpeaking(); redo.forEach(t => speak(t));
}
function speak(text) {
  const u = new SpeechSynthesisUtterance(text), g = gen, item = { text }; let timer;
  if (voice) u.voice = voice;
  u.lang = vprof.lang || "en-US"; u.pitch = vprof.pitch; u.rate = 1.05 * vprof.speech;
  const finish = () => { clearTimeout(timer); if (g !== gen) return; inflight = inflight.filter(i => i !== item); pending = Math.max(0, pending - 1); syncSpeaking(); };
  u.onstart = () => clearTimeout(timer);
  u.onend = finish;
  u.onerror = ev => { if (g !== gen) return; if (ev.error === "interrupted" || ev.error === "canceled" || voiceFailed) finish(); else useLocalVoice(); };
  inflight.push(item); pending++; syncSpeaking();
  if (pending === 1 && !voiceFailed) timer = setTimeout(() => { if (g === gen) useLocalVoice(); }, 4000);
  speechSynthesis.speak(u);
}
function stopSpeaking() {
  gen++; speechSynthesis.cancel(); inflight = [];
  sources.forEach(s => { try { s.stop(); } catch (e) {} }); sources.clear(); audioNext = 0; audioChain = Promise.resolve();
  pending = 0; syncSpeaking();
}
function onAudio(buf) {
  audioChain = audioChain.then(async () => {
    if (!ctx || new DataView(buf).getUint32(0) < minTurn) return;
    const g = gen;
    let ab; try { ab = await ctx.decodeAudioData(buf.slice(4)); } catch (e) { return; }
    if (g !== gen || !ctx) return;
    const src = ctx.createBufferSource(); src.buffer = ab; src.connect(ctx.destination);
    const t = Math.max(ctx.currentTime + 0.05, audioNext); src.playbackRate.value = vprof.rate; src.start(t); audioNext = t + ab.duration / vprof.rate;
    sources.add(src); pending++; syncSpeaking();
    src.onended = () => { sources.delete(src); if (g === gen) { pending = Math.max(0, pending - 1); syncSpeaking(); } };
  });
}

// ---------- microphone ----------
function micError(e) {          // one friendly sentence for every way the microphone can fail
  note("mic", e && e.name);
  if (!navigator.mediaDevices) return NOTICES.secure;
  switch (e && e.name) {
    case "NotAllowedError": case "SecurityError": return NOTICES.micblocked;
    case "NotFoundError": case "OverconstrainedError": return NOTICES.micnone;
    case "NotReadableError": case "AbortError": return NOTICES.micbusy;
    default: return NOTICES.micaccess;
  }
}
let micPerm = null;
async function refreshMicState() {
  let st = "unknown";
  try {
    micPerm = micPerm || await navigator.permissions.query({ name: "microphone" });
    micPerm.onchange = refreshMicState; st = micPerm.state;
  } catch (e) {}
  $("micstate").textContent = {
    granted: "Microphone access is allowed.",
    prompt: "Callie asks for microphone access when you make a call. You can allow it now.",
    denied: "Microphone access is blocked. Open your browser's site settings for this address, allow the microphone, then reload.",
    unknown: "Press Allow microphone so Callie can hear you.",
  }[st];
  $("micallow").hidden = st === "granted" || st === "denied";
}
async function getMic() {
  const base = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 };
  const id = localStorage.getItem("mic");
  try { return await navigator.mediaDevices.getUserMedia({ audio: id ? { ...base, deviceId: { exact: id } } : base }); }
  catch (e) { if (id) return navigator.mediaDevices.getUserMedia({ audio: base }); throw e; }
}
async function listMics() {
  const ds = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "audioinput");
  $("mic").innerHTML = ds.map(d => `<option value="${d.deviceId}">${esc(d.label || "Microphone")}</option>`).join("");
  const saved = localStorage.getItem("mic");
  if (saved && ds.some(d => d.deviceId === saved)) $("mic").value = saved;
}
function stopMicTest() {
  cancelAnimationFrame(testRaf);
  if (testStream) testStream.getTracks().forEach(t => t.stop());
  if (testCtx) testCtx.close().catch(() => {});
  testStream = testCtx = null; $("meter").style.width = "0"; $("mictest").textContent = "Test microphone";
}
async function startMicTest() {   // Settings: speak and watch the bar - pick another microphone if it stays flat
  stopMicTest();
  try { testStream = await getMic(); } catch (e) { toast(micError(e)); return; }
  await listMics();
  $("mictest").textContent = "Stop test";
  testCtx = new AudioContext();
  const an = testCtx.createAnalyser(); an.fftSize = 1024;
  testCtx.createMediaStreamSource(testStream).connect(an);
  const buf = new Float32Array(an.fftSize);
  const loop = () => {
    an.getFloatTimeDomainData(buf);
    let s = 0; for (const v of buf) s += v * v;
    $("meter").style.width = Math.min(100, Math.sqrt(s / buf.length) * 500) + "%";
    testRaf = requestAnimationFrame(loop);
  };
  loop();
}
$("mic").onchange = () => { localStorage.setItem("mic", $("mic").value); if (testStream) startMicTest(); };
$("micbox").addEventListener("toggle", () => { if ($("micbox").open) { listMics().catch(() => {}); refreshMicState(); } else stopMicTest(); });
listMics().catch(() => {});

// keep the phone screen on during a call
async function keepAwake() { try { if ("wakeLock" in navigator) wake = await navigator.wakeLock.request("screen"); } catch (e) {} }
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (ctx && ctx.state !== "running") ctx.resume().catch(() => {});      // phones pause audio when the screen was off
  if (document.body.dataset.v === "live") keepAwake();
});

// ---------- call screen ----------
const cb = (act, cls, icon, label) => `<div class="cb"><button class="rb ${cls}" data-act="${act}" aria-label="${label}">${icon}</button><span>${label}</span></div>`;
const endB = cb("end", "r", I.phone, "End");
function show(c, sub, btns, v) {
  $("cav").style.background = `linear-gradient(135deg,${G[c.color % G.length]})`;
  $("cav").textContent = c.name[0].toUpperCase(); $("cname").innerHTML = esc(c.name) + '<span class="ai">AI</span>';
  $("csub").textContent = sub; $("ctl").innerHTML = btns; view(v);
}
function live() {
  keepAwake(); stopRing(); tone([880], 0.12, 0.05); t0 = Date.now();
  show(cur, "00:00", cb("mute", "", I.mic, "Mute") + endB, "live");
  const tick = () => { const s = Math.floor((Date.now() - t0) / 1000); $("csub").textContent = String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
  clearInterval(timerId); timerId = setInterval(tick, 500);
}
async function startCall(id, answered = false) {
  cur = find(id); if (!cur) return;
  stopMicTest(); heard = false; silent = 0; micWarned = false;
  const cid = ++callId; busy = true; $("err").textContent = "";
  if (ctx) ctx.close().catch(() => {});
  show(cur, answered ? "Connecting…" : "Calling…", endB, "calling");
  ctx = new AudioContext(); await ctx.resume(); if (!answered) startRing();
  const t = performance.now();
  try {
    stream = await getMic();
    if (ctx.state !== "running") await ctx.resume();           // some phones pause audio while the permission box is open
    const track = stream.getAudioTracks()[0];
    if (track) {                                               // the browser tells us when the device itself mutes the microphone
      track.onmute = () => { note("mic", "muted"); $("err").textContent = NOTICES.mic; };
      track.onunmute = () => { if ($("err").textContent === NOTICES.mic) $("err").textContent = ""; };
    }
    await ctx.audioWorklet.addModule("worklet.js?v=27");
  } catch (e) { const msg = micError(e); if (cid === callId) fail(msg); return; }
  if (cid !== callId) return;
  node = new AudioWorkletNode(ctx, "capture"); ctx.createMediaStreamSource(stream).connect(node);
  const wait = (answered ? 300 : MIN_RING) - (performance.now() - t); if (wait > 0) await sleep(wait);
  if (cid !== callId) return;
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/voice?contact=" + encodeURIComponent(id) + "&ref=" + REF);
  ws.binaryType = "arraybuffer";
  ws.onmessage = e => (typeof e.data === "string" ? onMsg(JSON.parse(e.data)) : onAudio(e.data));
  ws.onclose = () => { if (cid === callId && busy) { hangup(false); note("net", "closed"); toast("The call was interrupted. Please try again."); } };
  node.port.onmessage = e => {
    const a = new Int16Array(e.data); let sum = 0;
    for (let i = 0; i < a.length; i++) sum += a[i] * a[i];
    if (sum > 0) {                 // any sound at all means the microphone works
      heard = true;
      if (micWarned) { micWarned = false; if ($("err").textContent === NOTICES.mic) $("err").textContent = ""; }
    } else if (!speaking && document.body.dataset.v === "live") silent++;     // only the caller's own quiet time counts
    if (!heard && silent === 750) { micWarned = true; note("mic", "silent"); $("err").textContent = NOTICES.mic; }   // 15 s and never a sound
    document.querySelector(".stage").style.setProperty("--lvl", Math.min(1, Math.sqrt(sum / a.length) / 32768 * 10).toFixed(2));  // ring grows with your voice
    if (document.body.dataset.v === "live" && ws && ws.readyState === 1) ws.send(muted ? new Int16Array(320).buffer : e.data);
  };
}
function onMsg(m) {
  if (m.type === "ready") { vprof = m.voice || vprof; voice = pickVoice(vprof.gender); live(); }
  else if (m.type === "say") { if (m.turn >= minTurn) speak(m.text); }
  else if (m.type === "stop") { minTurn = m.turn; stopSpeaking(); }
  else if (m.type === "notice") { note(m.code); $("err").textContent = NOTICES[m.code] || NOTICES.generic; }
}
function cleanup() {
  if (wake) { wake.release().catch(() => {}); wake = null; }
  stopRing(); clearInterval(timerId); stopSpeaking();
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (ctx) ctx.close().catch(() => {});
  ws = ctx = stream = node = null; muted = false; minTurn = 0;
}
function fail(msg) { callId++; cleanup(); busy = false; view(home()); toast(msg); }
function hangup(notify = true) {
  if (!busy) return;
  callId++;
  if (notify && ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "hangup" }));
  if (ws) ws.close();
  cleanup(); busy = false; $("err").textContent = ""; $("csub").textContent = "Call ended"; $("ctl").innerHTML = "";
  setTimeout(() => { if (!busy) { view(home()); load().catch(() => {}); } }, 1200);
}
function incoming(s) {
  if (busy) return;
  cur = find(s.contact); if (!cur) return;
  busy = true; callId++; $("err").textContent = "";
  if (!ctx) { ctx = new AudioContext(); ctx.resume(); }
  show(cur, "Incoming call", cb("answer", "g", I.phone, "Accept") + cb("decline", "r", I.phone, "Decline"), "incoming");
  startRing(true);
  if ("Notification" in window && Notification.permission === "granted" && document.hidden) new Notification(cur.name + " is calling", { silent: (localStorage.getItem("ring") || "classic") !== "phone", icon: "icons/icon-192.png", requireInteraction: true });
}
setInterval(() => {
  if (busy) return;
  const d = new Date(), hm = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  S.schedule.filter(s => s.on && s.time === hm).forEach(s => {
    const k = s.id + d.toDateString() + hm;
    if (!fired.has(k)) { fired.add(k); incoming(s); }
  });
}, 15000);

// ---------- clicks ----------
function setEdit(on) { document.body.dataset.edit = on ? "1" : "0"; document.querySelectorAll('[data-act=edit]').forEach(b => b.textContent = on ? "Done" : "Edit"); }
document.addEventListener("click", async e => {
  const el = e.target.closest("[data-act],[data-tab],[data-call],[data-delc],[data-dels],[data-tog],[data-voice],[data-pick]");
  if (!el) return;
  const d = el.dataset;
  try {
    if (d.pick) applyTheme(d.pick);
    else if (d.delc) { await api("/api/contacts/" + d.delc, "DELETE"); await load(); }
    else if (d.dels) { await api("/api/schedule/" + d.dels, "DELETE"); await load(); }
    else if (d.tog) { await api(`/api/schedule/${d.tog}/toggle`, "POST"); await load(); }
    else if (d.tab) { if (busy) document.body.dataset.tab = d.tab; else view(d.tab); setEdit(false); stopMicTest(); }
    else if (d.call) { if (!busy) startCall(d.call); }
    else if (d.voice) { document.querySelectorAll(".chip").forEach(c => c.classList.remove("on")); el.classList.add("on"); }
    else if (d.act === "edit") setEdit(document.body.dataset.edit !== "1");
    else if (d.act === "add-c") $("sheet-c").classList.toggle("open");
    else if (d.act === "add-s") { $("sheet-s").classList.toggle("open"); if ("Notification" in window && Notification.permission === "default") Notification.requestPermission(); }
    else if (d.act === "create-c") {
      const name = $("nm").value.trim(); if (!name) return;
      await api("/api/contacts", "POST", { name, voice: document.querySelector(".chip.on").dataset.voice, lang: $("lang").value });
      $("nm").value = ""; $("sheet-c").classList.remove("open"); await load();
    } else if (d.act === "create-s") {
      await api("/api/schedule", "POST", { contact: $("sc").value, time: $("tm").value }); $("sheet-s").classList.remove("open"); await load();
    } else if (d.act === "notify") {
      const on = !el.classList.contains("on"); el.classList.toggle("on", on); localStorage.setItem("notify", on ? "1" : "0");
      if (on && "Notification" in window) Notification.requestPermission();
    } else if (d.act === "mute") { muted = !muted; el.classList.toggle("on", muted); el.closest(".cb").querySelector("span").textContent = muted ? "Unmute" : "Mute"; }
    else if (d.act === "memory") {
      const on = !el.classList.contains("on");
      await api("/api/settings", "POST", { memory: on });
      el.classList.toggle("on", on);
      toast(on ? "Callie will remember your calls" : "Memory is off");
    } else if (d.act === "clear-memory") {
      if (confirm("Delete everything Callie remembers about your calls?")) { await api("/api/memory", "DELETE"); toast("Memories cleared"); }
    } else if (d.act === "micallow") {
      try { const st = await getMic(); st.getTracks().forEach(t => t.stop()); toast("Microphone allowed"); await listMics(); } catch (e) { toast(micError(e)); }
      refreshMicState();
    } else if (d.act === "mictest") { if (testStream) stopMicTest(); else await startMicTest(); }
    else if (d.act === "support") { $("sheet-support").classList.add("open"); }
    else if (d.act === "close-sheet") { document.querySelectorAll(".sheet").forEach(x => x.classList.remove("open")); }
    else if (d.act === "write") { writeTo(d.addr); }
    else if (d.act === "copy") {
      try { await navigator.clipboard.writeText(d.addr); toast("Copied"); } catch (e) { toast("Please copy it by hand: " + d.addr); }
    }
    else if (d.act === "end") hangup(true);
    else if (d.act === "decline") { stopRing(); busy = false; view(home()); }
    else if (d.act === "answer") { stopRing(); startCall(cur.id, true); }
  } catch (err) { note("ui", String(err.message)); toast(String(err.message) === "409" ? "Keep at least one contact" : NOTICES.generic); }
});
// ---------- appearance & ringtone settings ----------
const THEMES = [["auto", "Auto", "linear-gradient(135deg,#141417 50%,#fff 50%)"], ["midnight", "Midnight", "linear-gradient(135deg,#141417 50%,#22c55e 50%)"],
  ["daylight", "Daylight", "linear-gradient(135deg,#fff 50%,#16a34a 50%)"], ["ocean", "Ocean", "linear-gradient(135deg,#0d1626 50%,#3b82f6 50%)"],
  ["sunset", "Sunset", "linear-gradient(135deg,#1c100d 50%,#f97316 50%)"], ["royal", "Royal", "linear-gradient(135deg,#150f24 50%,#a855f7 50%)"]];
$("themes").innerHTML = THEMES.map(t => `<button class="sw" data-pick="${t[0]}" title="${t[1]}" aria-label="${t[1]} theme" style="background:${t[2]}"></button>`).join("");
function applyTheme(t) {
  document.documentElement.dataset.theme = t; localStorage.setItem("theme", t);
  document.querySelectorAll(".sw").forEach(b => b.classList.toggle("on", b.dataset.pick === t));
  const m = document.querySelector('meta[name="theme-color"]');
  if (m) m.content = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#141417";
}
applyTheme(localStorage.getItem("theme") || "auto");
$("ring").innerHTML = '<option value="phone">Phone default</option>' + Object.entries(RINGS).map(([k, r]) => `<option value="${k}">${r.label}</option>`).join("");
$("ring").value = localStorage.getItem("ring") || "classic";
$("ring").onchange = async () => {
  localStorage.setItem("ring", $("ring").value);
  if ($("ring").value === "phone") { if (navigator.vibrate) navigator.vibrate(300); toast("Uses your phone's notification sound and vibration"); return; }
  const c = new AudioContext(); await c.resume(); playRing($("ring").value, c); setTimeout(() => c.close().catch(() => {}), 4500);
};
document.body.dataset.edit = "0";
(function boot() { load().catch(() => { note("net", "boot"); toast("You seem to be offline. Reconnecting…"); setTimeout(boot, 5000); }); })();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

// tells the desktop app this window is still open
const ping = () => fetch("/api/ping", { method: "POST" }).catch(() => {});
ping(); setInterval(ping, 20000);

refreshMicState();
