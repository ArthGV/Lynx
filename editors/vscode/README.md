# lynx for VS Code

Syntax highlighting, comment toggling and indentation-aware editing for `.lx`
files.

## How it works

VS Code colours code with a **TextMate grammar**: a list of regexes, each
labelled with a scope name (`keyword.control`, `constant.numeric`, …). The
theme maps scopes to colours, so the extension never picks a colour itself —
it only says what each piece of text *is*.

Two of the three files here are generated from `src/core/grammar.py`, the
language's single source of truth:

| file | what it is |
| --- | --- |
| `generate.py` | reads `grammar.py` + the lexer's regexes, writes the two below |
| `syntaxes/lynx.tmLanguage.json` | *generated* — what each piece of text is |
| `language-configuration.json` | *generated* — comments, brackets, auto-indent |
| `package.json` | hand-written — the manifest tying `.lx` to the grammar |

So a new keyword, operator or symbol in `grammar.py` reaches the editor with:

```bash
python editors/vscode/generate.py
```

`generate.py` refuses to run if `grammar.py` grew a symbol it doesn't know how
to colour — classify it in `SYMBOL_SCOPE`. `tests/test_editor_grammar.py`
fails when the checked-in files are stale, so the language can't drift away
from its highlighting unnoticed.

## Install it locally

Link the folder into VS Code's extensions directory and restart:

```bash
ln -s "$(pwd)/editors/vscode" ~/.vscode/extensions/lynx-language
```

Open a `.lx` file — the status bar should read **lynx**. After editing the
grammar, run `generate.py` and then **Developer: Reload Window** (⇧⌘P).

To inspect what a token resolves to, use **Developer: Inspect Editor Tokens
and Scopes** — it shows the scope under the cursor and which rule produced it.

## Package it

```bash
npm install -g @vscode/vsce
cd editors/vscode && vsce package     # -> lynx-language-0.1.0.vsix
code --install-extension lynx-language-0.1.0.vsix
```

Publishing to the Marketplace additionally needs `publisher` in `package.json`
to be a registered publisher **ID** (no spaces), plus a `repository` field.
