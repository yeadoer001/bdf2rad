# Block Plugin Development

## Add a block

1. Create `blocks/<NAME>/`.
2. Add `manifest.json`.
3. Add `template.json` containing the fixed target Block lines and only explicit `{{PLACEHOLDER}}` fields.
4. Add `translator.py` exposing `translate(model, ctx, plugin)`.
5. Run `py bridge.py scan`.
6. Run conversion; the plugin is discovered automatically.

## Replace a block

Edit only the files inside that block folder. The next Python process discovers the current files from disk, so no central registry or package replacement is required.

## Format-lock rule

The literal target Block lines, comments, field order and line count belong to the template. The translator supplies values. Any new target syntax must be backed by an official Radioss reference or a supplied working example; otherwise the plugin must remain audit-only.
