# `scripts/web/` - Website Builder

The website builder converts PNG output into a static validation dashboard.

| Module | Purpose |
|---|---|
| `build_website.py` | CLI entry point and configuration loader |
| `web_builder.py` | Discovers plots, builds navigation metadata, and renders templates |
| `templates/` | Jinja2 HTML templates |
| `static/` | CSS, JavaScript, and image assets |

The builder expects plots under:

```text
<plots>/<DETECTOR>/<VARIANT>/<validation>/<system>/<plot>.png
```

[`config/web.yaml`](../../config/web.yaml) supplies site metadata and optional
display-name overrides.
Detector variants remain config-driven; they do not need to be listed there to
appear on the site.
