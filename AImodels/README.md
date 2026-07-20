# AI Models Directory

Each subfolder contains the weights and configuration for one AI model.
Drop your `.pt` model weights into the appropriate folder and restart the app.

## Folder Structure

```
AImodels/
├── person_detection/       → YOLOv8 person detector
├── fire_smoke_detection/   → Fire/smoke detector (YOLO or heuristic fallback)
├── accident_detection/     → Fall/accident detector (uses person tracking)
├── object_detection/       → General object detector (80 COCO classes)
├── face_matching/          → Face detection + recognition
└── custom/                 → Drop any custom .pt model here
```

## Default Behavior

If no custom weights are found in a folder, the app uses **YOLOv8 Nano** (`yolov8n.pt`)
which is automatically downloaded by Ultralytics on first run (~6MB).

## Adding Custom Weights

1. Train your model (e.g., using Ultralytics YOLOv8)
2. Place the `.pt` file in the matching folder
3. Restart the app — it picks up the new weights automatically

## Supported Formats

- `.pt` — YOLOv8 / Ultralytics weights (recommended)
- `.pt` — TorchScript serialized models
- `.onnx` — ONNX format (for custom models only)
