# Shared YOLOv8 Model Weights

If you have a custom trained general YOLOv8 model, place the weights file here:
* Filename: `model.pt`

This single weights file will be shared across:
* Person Detection
* Object Detection
* Vehicle Detection
* Animal Detection

Optional configuration parameters can be set in `config.json` inside this folder.
By default, if this folder is empty, the system automatically falls back to utilizing the shared `yolov8n.pt` weights.
