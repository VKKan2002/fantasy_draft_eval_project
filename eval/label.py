"""Label claims one at a time instead of hand-editing JSON.

    uv run python eval/label.py                # label the unlabelled ones
    uv run python eval/label.py --list         # show progress, change nothing

Saves after every answer, so quitting and resuming is safe. Skips anything that already
has a source (worked examples included).

The three questions, in order - stop at the first yes:
  1. Nothing factual to check?              -> not_a_claim      (x)
  2. Packet says something conflicting?      -> contradicted     (c)
  3. Can you point at an id that backs it?   -> supported        (s)
     ...if not                               -> not_in_packet    (n)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ffeval.audit.packet import FactsPacket

CASES = Path(__file__).parent / "cases" / "2025_w03_allen.json"
KEYS = {"s": "supported", "c": "contradicted", "n": "not_in_packet", "x": "not_a_claim"}


def load() -> dict:
    return json.loads(CASES.read_text())


def save(d: dict) -> None:
    CASES.write_text(json.dumps(d, indent=2) + "\n")


def show_ids(packet: FactsPacket) -> None:
    print("\nFACT IDS")
    for f in packet.facts:
        print(f"  {f.id:<36} = {f.value}")
    print("NEWS IDS")
    for n in packet.news:
        print(f"  {n.id:<36} ({n.published}) {n.text[:64]}...")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show progress and exit")
    args = ap.parse_args()

    d = load()
    packet = FactsPacket.load(d["packet"])
    todo = [c for c in d["claims"] if not c.get("source")]
    done = [c for c in d["claims"] if c.get("source")]

    if args.list:
        for c in d["claims"]:
            mark = c["label"] or "-"
            who = c.get("source") or "unlabelled"
            print(f"  {c['id']}  {mark:<14} {who:<15} {c['text'][:60]}")
        print(f"\n{len(done)} labelled, {len(todo)} to go")
        return

    if not todo:
        print("All claims labelled. Now compare with eval/reference_labels/.")
        return

    if not d.get("labelled_by"):
        d["labelled_by"] = input("Your name: ").strip()
        d["labelled_on"] = input("Today's date (YYYY-MM-DD): ").strip()
        save(d)

    print(packet.render())
    print("\n" + "=" * 78)
    print("s=supported  c=contradicted  n=not_in_packet  x=not_a_claim")
    print("?=reprint the ids   q=quit and save")
    print("=" * 78)

    for c in todo:
        while True:
            print(f"\n[{c['id']}]  {c['text']}")
            ans = input("  verdict > ").strip().lower()
            if ans == "q":
                save(d)
                print(f"\nSaved. {len([x for x in d['claims'] if x.get('source')])} done.")
                return
            if ans == "?":
                show_ids(packet)
                continue
            if ans in KEYS:
                break
            print("  s / c / n / x / ? / q")

        c["label"] = KEYS[ans]
        c["category"] = "natural" if ans == "s" else "adversarial"
        if ans == "s":
            ev = input("  which id(s) back it (space separated) > ").strip().split()
            bad = [e for e in ev if packet.fact(e) is None
                   and e not in {n.id for n in packet.news}]
            if bad:
                print(f"  warning: no such id in the packet: {', '.join(bad)}")
            c["evidence_ids"] = ev
        note = input("  note (enter to skip) > ").strip()
        if note:
            c["note"] = note
        c["source"] = d["labelled_by"]
        save(d)

    print("\nAll done. Now compare with eval/reference_labels/.")


if __name__ == "__main__":
    main()
