# MAME Explorer

**Status: Work in Progress**

Keyboard-driven CUI that builds a browsable tree of MAME Arcade machines and Software Lists from XML only (`-listxml` and `hash/*.xml`).  
Properties, search, and (planned) CHD verification / Extract are based on the logical model derived from those XMLs.

Implementation: [`mame_explorer.py`](mame_explorer.py)  
Design document: [`docs/design.md`](docs/design.md)  
Japanese README: [`README_jp.md`](README_jp.md)

## Features (current)

- Browse Arcade (`<machine>`) and Software Lists (`<softwarelist>`) in a single tree
- Lazy loading of large listxml output
- Properties panel for any node
- Simple search over currently expanded (visible) nodes
- Optional caches (`read arcade|softwarelist|romdir`) for faster re-open and real CHD candidate lookup (Tab on a Disk node)
- Automatic detection of `mame` executable and `hash/` directory from a package path (executable, directory, or archive)

## Requirements

- Python 3.10+ (stdlib only: `curses`, `xml.etree`, etc.)
- A MAME installation or package that can run `-listxml` (and preferably ships `hash/*.xml`)

Optional: `uv` for convenient running (`uv run mame-explorer ...`).

## Usage

```bash
# Direct mode (runs -listxml and discovers hash/ every time)
python mame_explorer.py /path/to/mame
# or
python mame_explorer.py /path/to/mame-directory-or-archive

# Cache mode (recommended for repeated use)
python mame_explorer.py read arcade /path/to/mame
python mame_explorer.py read softwarelist /path/to/mame   # or path to hash/
python mame_explorer.py read romdir /path/to/chd/root     # optional, for real CHD checks
python mame_explorer.py                                   # browse the caches
```

See `python mame_explorer.py --usage` for copy-pasteable examples.

### Keys

| Key | Action |
|-----|--------|
| ↑ / ↓ | Move |
| Enter / → | Expand |
| ← | Collapse |
| P | Toggle properties panel |
| / | Search (visible nodes only) |
| Tab | On a Disk node (with romdir cache): show CHD candidates / check SHA-1 |
| Q | Quit |

## Notes

- Full `-listxml` output is large (hundreds of MB). The first run can take a while.
- Tested primarily with MAME 0.285 (Ubuntu packages). Other versions / layouts are untested.
- Extract (CHD → image) and richer search / mediaKind handling are planned but not yet implemented.
- Real ROM/CHD files are never required for browsing the tree; they are used only for optional verification (and future Extract).

## License

MIT License – see [LICENSE](LICENSE).

Copyright (c) 2026 skt001
