# Knowledge Base

This directory is the durable target-format knowledge layer.

- `header_seed.json`: the exact runnable Starter/Engine seed distilled from the user-supplied EuroSID example. Only explicit placeholders are variable.
- `official_blocks.json`: target Block schemas and official reference URLs.
- `source_to_target.json`: source BDF function -> target Block relationship plus provenance URLs.
- `example_profiles.json`: names and roles of the user-supplied runnable/example decks used as format references. No `.rad` file is stored in the repository.

The block plugin folder is intentionally separate from this central catalog so a new block can be added without editing the core converter.
