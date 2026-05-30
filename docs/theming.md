# Theming and UI Customisation

The application uses a Material Design 3-inspired design system with support for light and dark modes and four selectable colour palettes. This document explains how theming works and how to customise it.

---

## Theme Modes

Two modes are available:

| Mode | Class on `<html>` | Description |
|---|---|---|
| Light | (none) | Default — white background, dark text |
| Dark | `dark` | Dark background, light text |

### Switching Themes

Click the theme toggle button in the top navigation bar. The change is applied immediately and persisted to `config/config.py` via `POST /api/settings/theme`.

### Configuration

```python
THEME = 'light'   # or 'dark'
```

---

## Colour Palettes

Four colour palettes are available, each based on a Material You tonal system:

| Palette | Key | Primary Colour | Hex |
|---|---|---|---|
| Lavender | `lavender` | Deep purple | `#65558f` |
| Organic Sage | `sage` | Forest green | `#386a20` |
| Slate Blue | `blue` | Classic blue | `#0f61a4` |
| Terracotta Rose | `rose` | Rose pink | `#984061` |

### Switching Palettes

Click any of the four colour dots in the navigation bar. The change is applied immediately and persisted.

### Configuration

```python
COLOR_PALETTE = 'lavender'
```

---

## CSS Architecture

All styles are defined in `app/static/css/style.css` using CSS custom properties (variables). The theme system works by toggling the `dark` class on the `<html>` element and the `data-palette` attribute.

### Variable Structure

```css
:root {
    /* Semantic tokens — mapped per palette */
    --md-sys-color-primary: ...;
    --md-sys-color-on-primary: ...;
    --md-sys-color-surface: ...;
    --md-sys-color-on-surface: ...;
    /* Typography */
    --font-family: 'Inter', sans-serif;
    /* Spacing */
    --radius-card: 16px;
    --radius-btn: 20px;
}

html.dark { ... }                        /* Dark mode overrides */
html[data-palette="sage"] { ... }        /* Palette overrides */
html.dark[data-palette="sage"] { ... }   /* Dark + palette combined */
```

### Palette Override Pattern

Each palette defines its own set of primary, secondary, and surface colour tokens. The base token values are defined for `lavender` in `:root`. Each other palette overrides only the tokens that differ:

```css
html[data-palette="blue"] {
    --md-sys-color-primary: #0f61a4;
    --md-sys-color-primary-container: #d1e4ff;
    --md-sys-color-secondary: #535f70;
    ...
}
```

---

## Typography

The application uses the **Inter** typeface loaded from Google Fonts:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
```

If the machine has no internet access, the browser falls back to the system sans-serif font. To bundle the font for offline use, download the Inter WOFF2 files and serve them from `app/static/fonts/`.

---

## Frameless Window

The pywebview window is created without a native title bar:

```python
webview.create_window(
    frameless=True,
    easy_drag=False,
    ...
)
```

The custom title bar is rendered in HTML in `app/templates/base.html`. Window controls (minimise, maximise, close) call `window.pywebview.api.minimize()`, `maximize()`, and `close()` via the `js_api` bridge.

`easy_drag=False` is set intentionally. Drag behaviour is implemented in JavaScript, applied only to the custom title bar element, preventing accidental window movement when interacting with page content.

---

## Customising the UI

### Changing the Primary Colour of a Palette

Edit the relevant `[data-palette="..."]` block in `app/static/css/style.css`:

```css
html[data-palette="lavender"] {
    --md-sys-color-primary: #65558f;  /* change this */
}
```

### Adding a New Palette

1. Add a new `data-palette` block in `style.css` with all required tokens.
2. Add a colour swatch button in `app/templates/base.html`:

```html
<button onclick="changePalette('mypalette')"
        style="background: #hexcolour;"
        title="My Palette">
</button>
```

3. Add the palette key to the validation list in `app/routes/settings.py`.

### Changing the Window Dimensions

Edit the `create_window` call in `main.py`:

```python
webview.create_window(
    width=1280,
    height=800,
    min_size=(1024, 700),
    ...
)
```

---

## Candidate Interview Portal Styling

The candidate interview portal (`app/templates/candidate_interview.html`) uses a subset of the same CSS variables. It does not include the navigation bar or HR-specific UI elements. The `data-palette` attribute is applied from the server-side Jinja2 template using the current `config.COLOR_PALETTE` value.
