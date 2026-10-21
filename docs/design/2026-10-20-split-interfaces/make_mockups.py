"""Generate the split-interface Connect mockups (static HTML). Run: python3 docs/design/2026-10-20-split-interfaces/make_mockups.py"""
from pathlib import Path

OUT = Path(__file__).resolve().parent
EXTRA = """<style>
.stage { border: 1px solid #2f4a2c; background: var(--raised); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.stage.todo { border-color: var(--line2); }
.stage .h { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 14px; }
.stage .n { width: 22px; height: 22px; border-radius: 50%; background: var(--ok); color: var(--bg); display: grid; place-items: center; font-size: 11px; }
.stage.todo .n { background: none; border: 1px solid #4b5562; color: var(--mut); }
.chain { display: flex; align-items: center; }
.node { border: 1px solid var(--line2); border-radius: 8px; padding: 8px 10px; background: var(--bg); min-width: 120px; }
.node b { display: block; font-size: 13px; } .node span { color: var(--mut); font-size: 12px; }
.wire { flex: 1; height: 2px; background: repeating-linear-gradient(90deg, var(--acc) 0 6px, transparent 6px 10px); }
.tick { width: 18px; height: 18px; border-radius: 4px; background: var(--acc); color: var(--bg); display: grid; place-items: center; font-size: 11px; }
.row { display: flex; gap: 12px; align-items: center; }
.btn-o { border: 1.5px solid var(--acc); color: var(--acc); border-radius: 8px; padding: 8px 14px; font-weight: 600; white-space: nowrap; }
.ok { color: var(--ok); }
.btn-o.off { border-color: #3b4320; color: #5c6438; }
.meter { height: 10px; border-radius: 3px; background: #2a1d10; position: relative; } .meter i { position: absolute; inset: 0 14% 0 0; background: var(--warn); border-radius: 3px; }
.combo.big { padding: 10px 12px; font-size: 14px; flex: 1; }
.menu.wide div { padding: 9px 12px; }
.menu .hint { color: var(--mut); font-size: 11px; }
</style>"""


def top() -> str:
    steps = ('<span><span class="d">✓</span>Gear</span><span class="on"><span class="d">2</span>Connect</span>'
             '<span><span class="d">3</span>Record</span><span><span class="d">4</span>Train</span><span><span class="d">5</span>Listen</span>')
    return (f'<div class="top"><div class="brand"><i></i>Parametric</div><div class="steps">{steps}</div>'
            '<div class="proj">Klon-style drive</div></div>')


def wire() -> str:
    nodes = [("Sound card", "Output"), ("Reamp box", "Instrument level"), ("Pedal", "In → Out"), ("Sound card", "Input")]
    chain = '<div class="wire"></div>'.join(f'<div class="node"><b>{a}</b><span>{b}</span></div>' for a, b in nodes)
    return ('<div class="stage"><div class="h"><span class="n">✓</span>Wire it up</div>'
            f'<div class="chain">{chain}</div><div class="row"><span class="tick">✓</span>Monitoring is off and speakers '
            'are unplugged from the sound card</div></div>')


def card_stage(choice: str, below: str, done: bool, menu: str = "", rate: str = "48 kHz") -> str:
    cls = "stage" if done else "stage todo"
    n = "✓" if done else "2"
    return (f'<div class="{cls}"><div class="h"><span class="n">{n}</span>Find the connection</div>'
            f'<div class="row"><div class="combo big"><span>{choice}</span><span>⌄</span></div><span class="muted">↻</span>'
            f'<span class="muted">{rate}</span></div>{menu}{below}</div>')


def level_stage(ready: bool = True) -> str:
    return ('<div class="stage todo"><div class="h"><span class="n">3</span>Check the loudest level</div>'
            '<div class="muted">Turn every knob on your gear to its loudest setting. Then press Check level.</div>'
            f'<div class="row"><span class="btn-o{"" if ready else " off"}">Check level</span></div></div>')


def aside() -> str:
    needs = "".join(f"<div>✓ {t}</div>" for t in ("A sound card with one output and one input",
                                                 "A reamp box (it makes the sound card output safe for a pedal input)",
                                                 "The gear's own power supply"))
    return (f'<div class="aside"><div class="sec" style="margin-top:0">What you need</div>{needs}<div class="grow"></div>'
            '<div class="disc">› Show me how to fix it</div><div class="disc">› Expert settings</div></div>')


def window(label: str, why: str, stage2: str) -> str:
    ready = "Find my connection</span>" in stage2 and "btn-o off" not in stage2
    main = (f'<div class="main"><h2>Connect your sound card</h2>{wire()}{stage2}{level_stage(ready or "Found:" in stage2 or "menu" in stage2)}</div>')
    return (f'<div class="label-above">{label}</div><p class="why">{why}</p><div class="win">{top()}'
            f'<div class="content">{main}{aside()}</div><div class="foot">No recordings planned yet'
            '<span class="pri off">Next: Record →</span></div></div>')


MENU = ('<div class="menu wide"><div class="sel">USB Audio CODEC (Core Audio)<span class="hint">2 in · 2 out ✓</span></div>'
        '<div>BlackHole 2ch (Core Audio)<span class="hint">2 in · 2 out</span></div>'
        '<div>Aggregate Device (Core Audio)<span class="hint">2 in · 4 out</span></div></div>')
FIND_OFF = '<div class="row"><span class="btn-o off">Find my connection</span></div>'
FIND = '<div class="row"><span class="btn-o">Find my connection</span><span class="ok">Found: Output 1 → Input 1.</span></div>'

listed = window(
    "A · A split interface is one sound card",
    "macOS shows the UMC22 (“USB Audio CODEC”) as an output-only and an input-only device with the same name. Connect "
    "pairs them into one entry, in the same list as every other card. The channel counts help tell cards apart.",
    card_stage("USB Audio CODEC (Core Audio)", "", True, MENU))
found = window(
    "B · Everything after the choice works as before",
    "Find my connection plays on the output half and listens on the input half. The level check, recording and "
    "training do not change. The project saves the name, so a reopened project finds both halves again.",
    card_stage("USB Audio CODEC (Core Audio)", FIND, True))
twins = window(
    "C · Two cards with the same name",
    "Two devices with the same name cannot be told apart (recording finds a card by its name). The app does not list "
    "that name and says what to do. Every other card still works: here BlackHole 2ch is chosen and Find is on.",
    card_stage("BlackHole 2ch (Core Audio)",
               '<div class="warnline">Two sound cards are called “USB Audio CODEC”, so the app cannot tell them '
               'apart. Unplug one, then press refresh.</div><div class="row"><span class="btn-o">Find my connection'
               '</span></div>', True))
missing = window(
    "E · A reopened project whose sound card is missing",
    "The saved card is not in today's list (unplugged, or now ambiguous). Connect selects nothing, saves nothing, and "
    "says so. Plugging it in and pressing refresh selects it again; choosing another card is the user's decision.",
    card_stage("Choose a sound card",
               '<div class="warnline">This project used “USB Audio CODEC”, which is not connected. Plug it in, then '
               'press refresh, or choose another sound card.</div>' + FIND_OFF, False, rate=""))
rates = window(
    "D · The two halves run at different rates",
    "Each half has its own sample rate in Audio MIDI Setup. Both must match the capture signals (48 kHz). The "
    "existing rate message and button name the half that is wrong.",
    card_stage("USB Audio CODEC (Core Audio)",
               '<div class="warnline">The input of your sound card runs at 44.1 kHz. Set it to 48 kHz in Audio MIDI '
               'Setup, then check again.</div><div class="row"><span class="btn-o">Open Audio MIDI Setup</span></div>'
               + FIND_OFF, False, rate="in 44.1 kHz · out 48 kHz"))

html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Split interfaces on Connect</title>'
        '<link rel="stylesheet" href="listen.css">' + EXTRA + '</head><body>'
        '<h1>Split interfaces on Connect</h1><p class="intro">Connect stage 2 when a sound card appears to macOS as '
        'two one-direction devices. Drawn on the real Phase 2 Connect layout. Dark theme.</p>'
        + listed + found + twins + rates + missing + "</body></html>")
(OUT / "connect.html").write_text(html)
print("written")
