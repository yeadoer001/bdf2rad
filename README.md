# BDF2RAD Modular Block Translator 5.0

## Goal

This version separates the translation layer into independently deployable **Block Plugins**. The core converter discovers block folders at runtime; adding a new block folder with a valid `manifest.json`, `template.json`, and `translator.py` makes the block available on the next run. Editing a plugin folder changes the behavior used on the next run without replacing the rest of the repository.

The repository contains **no `.rad` files**. Target-format knowledge is stored as JSON templates and provenance metadata under `knowledge_base/` and inside each block folder.

## Block plugin contract

Each block folder looks like:

```text
blocks/
  MYBLOCK/
    manifest.json
    template.json
    translator.py
```

`manifest.json` must contain:

```json
{
  "type": "bdf2rad-block",
  "name": "myblock",
  "source_cards": ["MYBDFCARD"],
  "order": 100,
  "target_blocks": ["/TARGET/BLOCK"],
  "status": "active"
}
```

`translator.py` must expose:

```python
def translate(model, ctx, plugin):
    return blocks, audit
```

The translator must use `template.json` for the target Block layout. Do not hand-build an alternative RAD layout inside the plugin when a template exists.

## VS Code

Edit the paths at the top of `bridge.py`:

```python
INPUT_BDF = r'E:\openradioss\input\Solution 3-1(6).bdf'
OUTPUT_DIR = r'E:\openradioss\output'
BLOCK_ROOT = Path(__file__).resolve().parent / 'blocks'
ENCODING = 'gb18030'
```

Press **F5** or run:

```cmd
py bridge.py
```

To list the currently installed blocks:

```cmd
py bridge.py scan
```

To scan another folder, including a whole drive for plugin manifests:

```cmd
py bridge.py scan --root D:\
```

To convert with a different block-pack directory:

```cmd
py bridge.py convert --input "E:\openradioss\input\Solution 3-1(6).bdf" --output "E:\openradioss\output" --blocks "D:\BDF2RAD-X\blocks"
```

The converter re-discovers plugins for each process. There is no central registry to edit.

## Important semantic rule

A plugin being `active` means a translator exists. It does **not** mean the source and target physics are proven equivalent. For mappings without a defensible one-to-one target meaning, the included plugin records an audit-only result instead of inventing undocumented syntax.

## Official references

The repository uses the Radioss Block Format described by the official Starter/Engine documentation. `/NODE`, `/PART`, `/PROP/SOLID`, `/BRICK`, `/BRIC20`, `/TETRA10`, `/RBE2`, `/RBE3`, `/GRNOD/NODE`, `/BCS`, `/INIVEL`, `/ADMAS`, `/GRAV`, `/SURF/SEG`, `/INTER/TYPE2`, `/INTER/TYPE7`, and `/RUN` are represented by dedicated plugins or knowledge-base entries. Official source URLs are stored alongside the block templates.
