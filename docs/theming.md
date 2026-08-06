# Theming

The UI uses CSS custom properties for theme and palette control. Theme changes are stored in runtime config and applied through templates.

## Modes

| Mode | Config | HTML state |
|---|---|---|
| Light | `THEME = 'light'` | Default |
| Dark | `THEME = 'dark'` | `html.dark` |

## Palettes

| Palette | Config value |
|---|---|
| Lavender | `lavender` |
| Sage | `sage` |
| Blue | `blue` |
| Rose | `rose` |

## Files

| File | Role |
|---|---|
| `app/static/css/style.css` | Main design system |
| `app/templates/base.html` | HR app shell, navigation, title bar |
| `app/templates/candidate_interview.html` | Candidate portal styling |
| `app/routes/settings.py` | Theme persistence and validation |

## Customizing a Palette

1. Edit the relevant `html[data-palette="..."]` block in `style.css`.
2. Keep semantic tokens consistent, for example primary, surface, border, and text colors.
3. Verify both light and dark modes.
4. Check dashboard, forms, modals, and candidate interview screens.

## Adding a Palette

1. Add a new CSS variable block in `style.css`.
2. Add a palette swatch in `base.html`.
3. Add the key to validation in `settings.py`.
4. Test persistence after restart.

## pywebview Window

The app uses a custom HTML title bar instead of a native window frame. Window controls call the pywebview JavaScript API exposed in `main.py`.

When changing layout, keep title-bar drag behavior separate from form controls so users do not accidentally move the window while interacting with inputs.
