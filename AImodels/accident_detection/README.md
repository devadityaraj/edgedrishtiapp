# Accident/Fall Detection Model

**Key:** `accident`
**Default:** YOLOv8 Nano + temporal motion analysis
**Task:** Detects falls and accidents by analyzing person pose changes over time

## Files

| File | Required | Description |
|---|---|---|
| `model.pt` | Optional | Custom YOLOv8 weights (e.g., trained on fall detection datasets) |
| `config.json` | Optional | Override confidence threshold and settings |

## config.json format

```json
{
    "confidence_threshold": 0.5
}
```

## How It Works

1. Tracks persons across frames using YOLO's tracker
2. Monitors aspect ratio changes (vertical → horizontal = fall)
3. Detects rapid downward centroid movement
4. Generates `fall_detected` events with confidence scores

## Notes

- Works on top of person detection — no specialized weights required
- Custom weights can improve accuracy for specific scenarios (e.g., workplace falls, elderly care)
