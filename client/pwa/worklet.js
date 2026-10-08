// Captures mic, downsamples to 16 kHz (box average), emits 320-sample Int16 frames (20 ms).
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.acc = 0; this.n = 0; this.pos = 0;
    this.out = new Int16Array(320); this.i = 0;
  }
  process(inputs) {
    const ch = inputs[0][0];
    if (!ch) return true;
    for (let k = 0; k < ch.length; k++) {
      this.acc += ch[k]; this.n++; this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const v = Math.max(-1, Math.min(1, this.acc / this.n));
        this.out[this.i++] = v * 32767;
        this.acc = 0; this.n = 0;
        if (this.i === 320) { const b = this.out.slice().buffer; this.port.postMessage(b, [b]); this.i = 0; }
      }
    }
    return true;
  }
}
registerProcessor("capture", Capture);
