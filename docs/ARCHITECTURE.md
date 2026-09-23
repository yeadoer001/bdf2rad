# Architecture

```text
bridge.py
  |
  +--> block discovery (recursive)
  |
  +--> BDF parser
  |
  +--> TranslationContext
  |      |
  |      +--> Block plugins discovered at runtime
  |               |
  |               +--> template.json (format)
  |               +--> translator.py (data mapping)
  |               +--> manifest.json (metadata)
  |
  +--> Starter seed from knowledge_base/header_seed.json
  |
  +--> Engine seed from knowledge_base/header_seed.json
  |
  +--> assembly
  +--> audit JSON
```

## Why this structure

- The error-prone area is isolated into small block directories.
- New blocks can be added without changing the core converter.
- Modified block implementations replace their predecessor automatically on the next run.
- Target syntax is stored with provenance and explicit format-lock metadata.
- The repository itself contains no RAD files.
