# Prism

To make `prism` and `pr-install` available from any Command Prompt, run
`setup-prism-path.bat` once from this folder, then open a **new** Command
Prompt. It adds this folder to your user PATH.

Run a script with:

```bat
prism script.prism
```

The `Prism.exe` launcher runs the interpreter. If the executable is not
available, `prism.bat` falls back to `..\SOURCECODE\prism_ide.py` and requires
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
python -m PyInstaller --noconfirm --clean --onefile --name Prism --add-data "SOURCECODE\libraries;libraries" --distpath Prism SOURCECODE\prism_ide.py
```

In a script, load an installed library with `library.use;[WC]` or
`library.use;[Bitwin]`. WC provides window title, background, and size commands.
Bitwin runs UTF-8 Prism source encoded as hexadecimal; it does not execute
native machine code. See `..\SOURCECODE\README.md` for examples and syntax.
