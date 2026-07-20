# Face Matching Model

**Key:** `face`
**Default:** OpenCV Haar Cascades + embedding comparison
**Task:** Detects faces and matches them against enrolled identities

## Files

| File | Required | Description |
|---|---|---|
| `model.pt` | Optional | Custom face detection model (YOLOv8-face or similar) |
| `config.json` | Optional | Override confidence threshold and settings |

## config.json format

```json
{
    "confidence_threshold": 0.6
}
```

## How It Works

1. Detects faces in frames using OpenCV or custom model
2. Extracts face embeddings (128/512-dimensional vectors)
3. Compares against enrolled faces stored in the database
4. Returns match results with confidence scores

## Enrolling Faces

Faces are enrolled through the Admin UI or API. The embeddings are stored encrypted in the database.

## Notes

- Requires `opencv-python-headless` (already in requirements)
- For better accuracy, consider using InsightFace or dlib (requires cmake + build tools)
