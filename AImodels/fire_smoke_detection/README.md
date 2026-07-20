# Fire/Smoke Detection Model

**Key:** `fire_smoke`
**Default:** YOLOv8 Nano + HSV color heuristic
**Task:** Detects fire and smoke in video frames

## Files

| File | Required | Description |
|---|---|---|
| `model.pt` | Optional | Custom YOLOv8 weights trained on fire/smoke datasets |
| `config.json` | Optional | Override confidence threshold and settings |

## config.json format

```json
{
    "confidence_threshold": 0.6
}
```

## Notes

- If a custom `model.pt` is found here, it is used as the primary detector (best accuracy)
- If not, the app falls back to YOLOv8 Nano + HSV color masking + motion heuristic
- The heuristic approach works without GPU but may produce more false positives
- Recommended datasets to train a custom model: [FASDD](https://github.com/OlafenwaMoses/FireNET), [D-Fire](https://github.com/gaiasd/DFireDataset)
