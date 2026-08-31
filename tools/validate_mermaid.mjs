import fs from 'fs';
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true });
const def = (k, v) => { try { Object.defineProperty(globalThis, k, { value: v, writable: true, configurable: true }); } catch {} };
def('window', dom.window);
def('document', dom.window.document);
def('navigator', dom.window.navigator);
for (const k of ['Element','SVGElement','HTMLElement','DOMParser','NodeFilter','Node','getComputedStyle','MutationObserver','requestAnimationFrame']) {
  def(k, dom.window[k]);
}

const mermaid = (await import('mermaid')).default;
mermaid.initialize({ startOnLoad: false });

const md = fs.readFileSync(process.argv[2], 'utf8');
const blocks = [...md.matchAll(/```mermaid\n([\s\S]*?)```/g)].map(m => m[1]);
console.log(`found ${blocks.length} mermaid blocks\n`);
let bad = 0;
for (let i = 0; i < blocks.length; i++) {
  const lines = blocks[i].trim().split('\n').length;
  try {
    await mermaid.parse(blocks[i]);
    console.log(`  block ${i + 1} (${lines} lines): OK`);
  } catch (e) {
    bad++;
    console.log(`  block ${i + 1} (${lines} lines): FAIL`);
    console.log(`     ${String(e.message).split('\n').slice(0,5).join('\n     ')}`);
  }
}
console.log(bad ? `\n${bad} INVALID` : `\nAll ${blocks.length} blocks parse cleanly.`);
process.exit(bad ? 1 : 0);
