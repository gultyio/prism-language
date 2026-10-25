# Prism

## Run Prism scripts

The Windows launchers are in `..\Prism`. Run `setup-prism-path.bat` there once
and open a new Command Prompt to make `prism` and `pr-install` available from
any directory. The packaged `Prism.exe` includes the prebuilt libraries;
without it, the batch launchers require Python 3 with Tkinter. Then run:

```bat
prism script.prism
```

The launcher runs this folder's `prism_ide.py`. Python 3 with Tkinter is
required. You can also run `python prism_ide.py script.prism` from this folder.
Run `prism` with no arguments to open the graphical IDE.

## Install prebuilt libraries

Install a library from this folder:

```bat
pr-install WC
pr-install Bitwin
```

Packages are installed per user under `%APPDATA%\Prism\libraries`. Load an
installed package in a `.prism` script with `library.use;[Name]`.

### WC (Window Customization)

Create a window using the existing Prism syntax, then customize it:

```prism
display.h.window.show; (350); (200); (1); (MyWindow)
library.use;[WC]
wc.window.title;(MyWindow);("Custom title")
wc.window.background;(MyWindow);(#336699)
wc.window.size;(MyWindow);(800);(600)
```

Backgrounds use six-digit `#RRGGBB` colors and sizes use positive integer
dimensions.

### Bitwin

Bitwin runs UTF-8 Prism source encoded as hexadecimal. The input must contain
an even number of valid hex digits:

```prism
library.use;[Bitwin]
bitwin.run;[682e7072696e746c696e653b2248656c6c6f22]
```

The example decodes to `h.printline;"Hello"` and prints `Hello`. Bitwin runs
Prism source; it does not execute native machine code.

## Existing syntax

The IDE Help menu includes the Prism syntax reference and examples. Prism
comments use `c.comment("text")`; variables use `h.func.define;[name]` and
`h.change;variable:[name];[value]`; output uses `h.printline;"text"`.
