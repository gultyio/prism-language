# Prism

To make `prism` and `pr-install` available from any Command Prompt, run
`setup-prism-path.bat` once from this folder, then open a **new** Command
Prompt. It adds this folder to your user PATH.

Run a script with:

```bat
prism script.prism
```

The `Prism.exe` launcher runs the interpreter. If the executable is not
available, `prism.bat` runs the `prism_ide.py` file beside it and requires
Python 3 with Tkinter. If you haven't set up PATH, run `prism.bat
script.prism` while in this folder.

Install the prebuilt libraries from this folder:

```bat
pr-install WC
pr-install WC+
pr-install Bitwin
pr-install IAF
pr-install C-S
```

These are Prism `.prism` packages, not Python packages: `pr-install` copies
them to `%APPDATA%\Prism\libraries`, and scripts load them with
`library.use;[Name]`. The source interpreter uses Python 3 and Tkinter; no
additional Python libraries are required. PyInstaller is only needed to build
the standalone executable.

`Prism.exe` includes the prebuilt library packages, so Python is not required
when using the packaged executable. Build from the project root using the
command below, or build `PrismLG.spec` from this folder; both produce the
`Prism.exe` expected by the launchers.

## Build the executable from source

From the project root, with Python and PyInstaller installed, run:

```bat
python -m PyInstaller --noconfirm --clean --onefile --name Prism --add-data "Prism\libraries;libraries" --distpath Prism Prism\prism_ide.py
```

Load each installed library in a script with `library.use;[library-name]`.
Available libraries are WC, WC+, Bitwin, IAF, and C-S.

### WC+ (Window Customization PLUS)

Use WC+ after creating the target window with `display.h.window.show`:

```prism
library.use;[WC+]
wcplus.window.opacity;(GameWindow);(0.8)
wcplus.window.topmost;(GameWindow);(true)
wcplus.window.resizable;(GameWindow);(true);(false)
wcplus.window.minsize;(GameWindow);(320);(200)
```

`wc+.window.` is also accepted as a command prefix. Opacity must be from 0.0
to 1.0; boolean options accept `true`, `false`, `1`, or `0`; minsize values
must be positive integer dimensions.

### IAF (Improved Argument Functions)

IAF adds parameterized user functions. Parameters are temporarily bound for
the duration of the call and previous variables with those names are restored
afterward:

```prism
library.use;[IAF]
h.func.definefunc;(greet);(name);
     h.printline;"Hello"
     h.printline;[name]

c.func.call;(greet);("Ada")
```

Arguments may be quoted strings, numbers, or references to defined variables
such as `([user_name])`. The argument count must match the declared parameter
count. Existing no-argument functions using `c.function_name();` continue to
work.

### C-S (search and choose a stored item)

`scan.choose.store()` opens a searchable window listing the current variables,
functions, classes, open windows, and persistent-store entries. Select an item
and click **Choose Item** (or double-click it) to save its name in
`[store_choice]`, its kind in `[store_choice_type]`, and its complete entry in
`[selected_store]`.

```prism
library.use;[C-S]
h.func.define;[score]
h.change;variable:[score];[100]
store.[score]
scan.choose.store()
h.printline;[store_choice]
```

The last line can run after selecting an item in the chooser.

Bitwin runs UTF-8 Prism source encoded as hexadecimal; it does not execute
native machine code. See `..\SOURCECODE\README.md` for other syntax examples.
The IDE Examples menu includes a WC+/IAF/C-S walkthrough; install these
libraries before running it.

## Logic gates

Prism supports two-input `AND`, `OR`, `XOR`, `NAND`, `NOR`, and `XNOR` gates.
Each input must be `0`, `1`, or a variable reference containing one of those
values. Each command prints `Result(0)` or `Result(1)` and opens a graphical
visualizer window showing both inputs, active/inactive wires, the gate, and
output.
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
result on its canvas. The visualizer routes the output to the connected target.
If no ID is supplied, results receive an automatic ID and the latest result of
each gate is used. The IDE Help & Syntax window and Examples menu also include
a gate-and-connection walkthrough.

## Wolfenstein raycast maps

`3D.raycast.wolfensteinformula.shapes` displays the tiled top-down map and a
first-person 3D perspective raycast view side by side. The player starts on the
nearest walkable tile, even when the map pattern repeats a wall at its center.
Use `0` (or a space) for open floor; a completely solid pattern is reported as
an error because it has no valid player start. Focus the viewport and press
W/S or Up/Down to move, and A/D or Left/Right to turn. Movement is blocked by
walls; both the top-down player marker and 3D perspective update as you move.
