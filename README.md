# MAME Explorer


Keyboard-driven CUI for browsing the logical structure defined by MAME `-listxml` and Software List XML (`hash/*.xml`). The XML is the source of truth for the tree, Properties, and search.

MAME Explorer is an **XML/metadata reader and explorer**. It is not a ROM checker, CHD checker, ROM manager, or ROM-set management tool. It does not calculate or verify ROM/CHD hashes.

Implementation: [`mame_explorer.py`](mame_explorer.py)  
Design document: [`docs/design.md`](docs/design.md)  
Japanese README: [`README_jp.md`](README_jp.md)

## Features (current)

- Browse Arcade (`<machine>`) and Software Lists (`<softwarelist>`) in a single tree
- Lazy loading of large listxml output
- Properties panel for any node
- Simple search over currently expanded (visible) nodes
- Optional caches (`read arcade|softwarelist|romdir`) for faster re-open
- **CHD mode** (`mame_explorer.py chd`): use the romdir cache to prune the tree to branches whose XML-defined Disk name has a matching `.chd` file
- Automatic detection of `mame` executable and `hash/` directory from a package path (executable, directory, or archive)

The `romdir` cache records CHD file names and paths for Explorer-side filtering. It is not a ROM/CHD verification database.

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
python mame_explorer.py read romdir /path/to/chd/root     # optional, for CHD-aware tree filtering
python mame_explorer.py                                   # browse the caches
python mame_explorer.py chd                               # CHD mode (requires romdir cache)
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
| Tab | On a Disk node (with romdir cache): show matching CHD file candidates |
| Q | Quit |

## Scope

MAME Explorer reads and presents MAME metadata. In particular:

- The logical tree comes from MAME `-listxml` and Software List XML.
- XML-defined attributes such as `name`, `sha1`, `status`, and `writeable` are displayed as metadata when present.
- The application does **not** independently verify those hashes against ROM or CHD files.
- Real ROM/CHD files are not treated as the source of truth for the logical model.
- `romdir` is an optional filesystem index used by CHD mode to filter the Explorer view by matching CHD filenames.
- MAME Explorer does not copy, organize, repair, validate, or manage ROM sets.


## License

MIT License – see [LICENSE](LICENSE).

Copyright (c) 2026 skt001
