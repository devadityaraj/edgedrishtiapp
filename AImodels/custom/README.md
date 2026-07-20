# Custom AI Models

Drop any custom `.pt` model file here. The app auto-discovers them on startup.

## How It Works

1. Place your `<name>.pt` file in this folder
2. Restart the app
3. The model is registered as `custom_<name>` (e.g., `weapon.pt` → `custom_weapon`)
4. Assign the model to cameras through the Admin UI

## Supported Formats

- `.pt` — YOLOv8 / Ultralytics weights (recommended)
- `.pt` — TorchScript serialized models (fallback)

## Examples

```
custom/
├── weapon.pt          → registered as custom_weapon
├── ppe.pt             → registered as custom_ppe
├── loitering.pt       → registered as custom_loitering
└── license_plate.pt   → registered as custom_license_plate
```
