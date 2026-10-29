# Prism

To make `prism` and `pr-install` available from any Command Prompt, run
`setup-prism-path.bat` once from this folder, then open a **new** Command
Prompt. It adds this folder to your user PATH.

Run a script with:

```bat
prism script.prism
```

The `Prism.exe` launcher runs the interpreter. If the executable is not
available, `prism.bat` falls back to `..\prism_ide.py` and requires
Python 3 with Tkinter. If you haven't set up PATH, run `prism.bat
script.prism` while in this folder.

Install the prebuilt libraries from this folder:

```bat
pr-install WC
pr-install Bitwin
```

`Prism.exe` includes the prebuilt library packages, so Python is not required
when using the packaged executable.

## Build the executable from source

From the project root, with Python and PyInstaller installed, run:

```bat
python -m PyInstaller --noconfirm --clean --onefile --name Prism --add-data "Prism\libraries;libraries" --distpath Prism prism_ide.py
```

In a script, load an installed library with `library.use;[WC]` or
`library.use;[Bitwin]`. WC provides window title, background, and size commands.
Bitwin runs UTF-8 Prism source encoded as hexadecimal; it does not execute
native machine code. See `..\SOURCECODE\README.md` for examples and syntax.

## Logic gates

Prism supports two-input `AND`, `OR`, `XOR`, `NAND`, `NOR`, and `XNOR` gates.
Each input must be `0`, `1`, or a variable reference containing one of those
values. Each command prints `Result(0)` or `Result(1)`, then draws an ASCII
logic-gate diagram in the console showing both inputs, the gate, and output.
An optional ID lets you connect a specific saved result; without one,
`connect.logicgate` uses the latest result for that gate.

```prism
h.func.define;[left]
h.change;variable:[left];[1]
h.func.define;[right]
h.change;variable:[right];[0]
h.func.define;[output]
h.func.definefunc;(on_hit);
     h.printline;"Function received:"
     h.printline;[logic_gate_result]

apply.logicgates.XOR; ([left]); ([right]); (ID: player_hit)
connect.logicgate.XOR; (output); (ID: player_hit)
h.printline;[output]
connect.logicgate.XOR; (on_hit); (ID: player_hit)

c.comment("Without an ID, connect uses the latest result for that gate.")
apply.logicgates.AND; (1); (1)
connect.logicgate.AND; (output)
```

Connect targets are defined variables, functions, classes, or windows.
Connecting a variable assigns the result. Connecting a function or class runs
it with the result in `[logic_gate_result]`. Connecting a window displays the
result on its canvas. The console prints the diagram again with an arrow to
the connected target. If no ID is supplied, results receive an automatic ID
and the latest result of each gate is used. The IDE Help & Syntax window and
Examples menu also include a gate-and-connection walkthrough.

## Wolfenstein raycast maps

`3D.raycast.wolfensteinformula.shapes` displays the tiled top-down map and a
first-person 3D perspective raycast view side by side. The player starts on the
nearest walkable tile, even when the map pattern repeats a wall at its center.
Use `0` (or a space) for open floor; a completely solid pattern is reported as
an error because it has no valid player start.
