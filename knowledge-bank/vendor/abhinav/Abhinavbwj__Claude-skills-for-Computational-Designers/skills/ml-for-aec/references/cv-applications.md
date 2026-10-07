# Computer Vision for AEC: Deep Reference

This reference provides comprehensive technical detail on computer vision architectures, training data preparation, evaluation metrics, and deployment strategies for AEC applications.

---

## 1. Model Architecture Summaries

### 1.1 YOLO (You Only Look Once)

**Concept**: Single-stage object detector that divides the image into a grid and predicts bounding boxes and class probabilities simultaneously for all grid cells in one forward pass.

**Architecture evolution**:

| Version | Year | Key Innovation | Params | mAP (COCO) | Speed (FPS) |
|---------|------|---------------|--------|-------------|-------------|
| YOLOv3 | 2018 | Multi-scale detection, Darknet-53 backbone | 62M | 33.0 | 65 |
| YOLOv4 | 2020 | CSPDarknet, PANet, mosaic augmentation | 64M | 43.5 | 62 |
| YOLOv5 | 2020 | PyTorch native, auto-anchor, easy training | 7-87M | 37-50 | 140-30 |
| YOLOv7 | 2022 | E-ELAN, model re-parameterization | 6-151M | 51-56 | 161-30 |
| YOLOv8 | 2023 | Anchor-free, decoupled head, new backbone | 3-68M | 37-53 | 195-40 |
| YOLOv9 | 2024 | PGI (Programmable Gradient Information), GELAN | varies | 51-55 | varies |

**YOLOv8 detailed architecture**:
```
Backbone: CSPDarknet (Cross-Stage Partial connections)
  - Conv layers with batch normalization and SiLU activation
  - C2f modules (faster CSP bottleneck with 2 convolutions)
  - SPPF (Spatial Pyramid Pooling - Fast)

Neck: PANet (Path Aggregation Network)
  - Top-down FPN for semantic features
  - Bottom-up path for localization features
  - Concatenation of multi-scale features

Head: Decoupled head (separate classification and regression branches)
  - Anchor-free detection (predicts center offset + width/height directly)
  - 3 detection scales (P3/8, P4/16, P5/32)
  - Classification: sigmoid per class
  - Regression: DFL (Distribution Focal Loss) for box prediction

Loss: CIoU loss (box) + BCE loss (classification) + DFL loss (distribution)
```

**AEC-specific YOLO training tips**:
- For architectural drawings: Use grayscale input (convert RGB to single channel, then tile 3x for RGB model input)
- For small objects (door handles, electrical outlets): Use YOLOv8-nano at higher resolution (1280x1280)
- For construction site images: Augment with weather conditions (rain, fog, bright sunlight)
- Anchor-free YOLOv8 eliminates need for custom anchor tuning for AEC-specific object sizes

### 1.2 Faster R-CNN

**Concept**: Two-stage detector with a Region Proposal Network (RPN) generating candidate regions, followed by a classification and regression head for each region.

**Architecture**:
```
Stage 1: Backbone + FPN
  - ResNet-50/101 or ResNeXt backbone
  - Feature Pyramid Network (FPN) for multi-scale features
  - Output: Feature maps at multiple scales (P2-P6)

Stage 2: Region Proposal Network (RPN)
  - 3x3 conv sliding window over feature maps
  - At each position: predict objectness score + bounding box offset
  - Anchors: multiple scales and aspect ratios per position
  - NMS to reduce proposals to top ~1000

Stage 3: ROI Head
  - ROI Align: extract fixed-size features from each proposal region
  - Two FC layers → classification scores + box regression
  - Per-class NMS to produce final detections
```

**When to use Faster R-CNN over YOLO for AEC**:
- When localization precision is critical (e.g., detecting exact wall endpoints in drawings)
- When objects have extreme aspect ratios (long thin pipes, narrow windows)
- When speed is not the primary concern (offline batch processing of drawings)
- When fine-grained distinction between similar classes is needed

**Implementation**: Detectron2 (Facebook), MMDetection (OpenMMLab), torchvision

### 1.3 U-Net

**Concept**: Encoder-decoder architecture with skip connections for pixel-level segmentation. Originally designed for medical image segmentation; exceptionally effective for floor plan and drawing segmentation.

**Architecture**:
```
Encoder (contracting path):
  Level 1: [Conv3x3-BN-ReLU] x2 → MaxPool2x2     (64 channels)
  Level 2: [Conv3x3-BN-ReLU] x2 → MaxPool2x2     (128 channels)
  Level 3: [Conv3x3-BN-ReLU] x2 → MaxPool2x2     (256 channels)
  Level 4: [Conv3x3-BN-ReLU] x2 → MaxPool2x2     (512 channels)

Bottleneck:
  [Conv3x3-BN-ReLU] x2                             (1024 channels)

Decoder (expanding path):
  Level 4: UpConv2x2 + Concat(skip4) → [Conv3x3-BN-ReLU] x2  (512 ch)
  Level 3: UpConv2x2 + Concat(skip3) → [Conv3x3-BN-ReLU] x2  (256 ch)
  Level 2: UpConv2x2 + Concat(skip2) → [Conv3x3-BN-ReLU] x2  (128 ch)
  Level 1: UpConv2x2 + Concat(skip1) → [Conv3x3-BN-ReLU] x2  (64 ch)

Output: Conv1x1 → num_classes channels → Softmax/Sigmoid
```

**Key design choices for AEC**:
- Input size: 256x256 (fast, low detail) to 1024x1024 (slow, high detail)
- For binary tasks (wall/not-wall): 1 output channel + sigmoid
- For multi-class (wall, door, window, room, background): N channels + softmax
- Dropout: 0.2-0.5 in bottleneck to prevent overfitting on small AEC datasets
- Batch size: 4-16 (limited by GPU memory at high resolutions)

**U-Net variants for AEC**:
- **Attention U-Net**: Attention gates in skip connections; focuses on relevant features; better for detecting small elements (doors, windows) in large floor plans
- **U-Net++**: Dense skip connections; multi-scale feature fusion; better boundary delineation
- **U-Net with ResNet backbone**: Replace plain convolutions with ResNet blocks; better feature extraction with pre-trained weights

### 1.4 Mask R-CNN

**Concept**: Extends Faster R-CNN with a parallel mask prediction branch that outputs a binary mask for each detected instance.

**Architecture** (additions to Faster R-CNN):
```
After ROI Align (14x14 features per proposal):
  Classification branch: FC layers → class scores
  Box regression branch: FC layers → box offsets
  Mask branch (NEW):
    4x [Conv3x3-BN-ReLU, 256 channels]
    1x ConvTranspose2x2 (upsample to 28x28)
    1x Conv1x1 → K binary masks (K = number of classes)

Key: Mask is predicted per-class; at inference, use the mask corresponding
     to the predicted class. This decouples classification from segmentation.
```

**AEC instance segmentation tasks**:
- Individual room detection in floor plans (each room is a separate instance)
- Individual facade panel detection in curtain wall images
- Individual pipe/duct instance in MEP drawings or 3D renders
- Individual crack instance detection (separate cracks, not merged)
- Individual worker detection with body mask (for pose estimation)

### 1.5 Vision Transformer (ViT)

**Concept**: Apply Transformer architecture (from NLP) directly to images by treating image patches as tokens.

**Architecture**:
```
Input: Image (H x W x 3)
Patch embedding: Divide into P x P patches → flatten → linear projection → D-dim tokens
  e.g., 224x224 image, 16x16 patches → 196 tokens of dimension D=768

Position embedding: Add learnable position embeddings to tokens
CLS token: Prepend a learnable [CLS] token for classification

Transformer encoder: L layers of:
  Multi-Head Self-Attention (MHSA)
  Layer Norm
  MLP (Feed-Forward: Linear-GELU-Linear)
  Layer Norm
  Residual connections

Output: [CLS] token → MLP head → class predictions
```

**ViT variants for AEC**:
- **DeiT (Data-efficient ViT)**: Better training on smaller datasets with distillation
- **Swin Transformer**: Shifted window attention; hierarchical; good for dense prediction (segmentation)
- **BEiT**: Pre-trained with masked image modeling; strong transfer learning

**When to use ViT for AEC**:
- Large datasets (ViT needs more data than CNNs to train from scratch)
- Pre-trained models available (ImageNet-21K, fine-tune on AEC)
- Tasks where global context matters (understanding full floor plan layout, not just local patterns)
- Swin Transformer for dense prediction tasks (segmentation, detection)

---

## 2. Training Data Preparation for AEC

### 2.1 Annotation Tools

| Tool | Type | Features | Cost |
|------|------|----------|------|
| **Label Studio** | Open source | Multi-media (image, text, audio), ML-assisted labeling, team collaboration | Free |
| **CVAT** | Open source | Video annotation, interpolation, semi-automatic (AI-assisted) | Free |
| **Roboflow** | Commercial | Auto-augmentation, dataset management, model training, deployment | Free tier + paid |
| **LabelImg** | Open source | Simple bounding box annotation for images | Free |
| **VGG Image Annotator (VIA)** | Open source | Browser-based, polygons, polylines, points | Free |
| **Supervisely** | Commercial | Full platform: annotation, training, deployment | Free tier + paid |
| **Scale AI** | Commercial | Managed labeling workforce for large-scale annotation | Paid |

### 2.2 Labeling Strategies for AEC

**Class taxonomy design**:

Start with a minimal taxonomy and expand as needed:

Level 1 (basic): wall, opening, room, background
Level 2 (standard): wall, door, window, room, corridor, stair, elevator, bathroom, kitchen, background
Level 3 (detailed): ext_wall, int_wall, fire_wall, single_door, double_door, sliding_door, fixed_window, operable_window, curtain_wall, ...

**Labeling guidelines for AEC images**:

- **Consistency**: Define clear rules for edge cases. Where does a wall end? Does the door include the frame? Is a window sill part of the window or the wall?
- **Bounding box tightness**: Tight boxes for detection; include some context (5-10 pixels margin) for recognition
- **Polygon precision**: For segmentation, trace element boundaries precisely; use zoom
- **Occlusion handling**: Label visible portions; mark occluded elements if needed for training
- **Scale consistency**: Annotate elements regardless of size if they are task-relevant

**Quality assurance for annotations**:
1. Double-annotate 10-20% of samples (inter-annotator agreement check)
2. Cohen's kappa or IoU agreement threshold: > 0.85
3. Expert review of ambiguous cases
4. Iterative refinement: train model, review errors, re-annotate ambiguous samples

### 2.3 Data Augmentation for Architecture Images

**Geometric augmentations**:
- Rotation: ±5 degrees for photos, 0/90/180/270 for drawings (orthogonal only)
- Flipping: Horizontal flip for most tasks; vertical flip for plan views
- Scaling: ±10-20% zoom
- Cropping: Random crops at 80-100% of image area
- NOT for architectural drawings where orientation matters (north arrow, labels)

**Photometric augmentations**:
- Brightness: ±20%
- Contrast: ±20%
- Color jitter: ±10% hue, saturation
- Gaussian noise: sigma 5-15 (simulate low-quality scans)
- JPEG compression artifacts (simulate low-quality images)

**AEC-specific augmentations**:
- Line weight variation (for drawing element detection)
- Background replacement (for site photos)
- Weather simulation (rain, fog, snow) for outdoor construction monitoring
- Drawing style transfer (different firms use different CAD standards)

**Augmentation libraries**: Albumentations (Python, comprehensive, fast), torchvision transforms, imgaug

### 2.4 Synthetic Data Generation for AEC

When real annotated data is scarce, generate synthetic training data:

**BIM-to-synthetic-image pipeline**:
1. Create parametric BIM model (Revit, Rhino)
2. Vary parameters: dimensions, materials, lighting, camera angle
3. Render images with automatic annotations (from model metadata)
4. Each render produces an image + pixel-perfect label map + bounding boxes

**Advantages**: Unlimited data, perfect labels, controllable diversity
**Disadvantages**: Domain gap between synthetic and real images; may need domain adaptation or fine-tuning on small real dataset

**Tools**: Blender (free, Python scripting), Unity Perception, NVIDIA Omniverse Replicator

---

## 3. Transfer Learning from ImageNet

### 3.1 Pre-trained Backbones for AEC

Most AEC CV tasks benefit from ImageNet pre-trained backbones:

| Backbone | ImageNet Top-1 | Params | AEC Transfer Quality |
|----------|---------------|--------|---------------------|
| ResNet-50 | 76.1% | 25M | Good; standard baseline |
| ResNet-101 | 77.4% | 45M | Better; when data is sufficient |
| EfficientNet-B4 | 82.9% | 19M | Good; efficient; mobile-friendly |
| ConvNeXt-B | 83.8% | 89M | Strong; modern CNN |
| Swin-T | 81.3% | 29M | Strong; good for segmentation |
| ViT-B/16 | 77.9% | 87M | Needs more data; pre-train on larger set |
| DINOv2 ViT-B | 82.1% | 87M | Strong self-supervised features |

### 3.2 Fine-Tuning Strategy

**Full fine-tuning**: Update all layers. Best when AEC dataset is large (>10K images) and domain is different from ImageNet.

**Feature extraction**: Freeze backbone, train only the head. Best when AEC dataset is very small (<500 images).

**Progressive unfreezing**: Start with frozen backbone, gradually unfreeze deeper layers. Best for medium AEC datasets (1K-10K images).

```python
# Progressive unfreezing example (PyTorch)
import torch
from torchvision.models import resnet50

model = resnet50(weights="IMAGENET1K_V2")

# Phase 1: Train only the new classification head
for param in model.parameters():
    param.requires_grad = False
model.fc = torch.nn.Linear(2048, num_aec_classes)

# Train for 10 epochs at lr=1e-3
# ...

# Phase 2: Unfreeze layer4
for param in model.layer4.parameters():
    param.requires_grad = True
# Train for 10 epochs at lr=1e-4
# ...

# Phase 3: Unfreeze layer3
for param in model.layer3.parameters():
    param.requires_grad = True
# Train for 10 epochs at lr=1e-5
# ...

# Phase 4: Unfreeze all
for param in model.parameters():
    param.requires_grad = True
# Train for 10 epochs at lr=1e-6
```

### 3.3 Domain Adaptation for AEC

When pre-trained features do not transfer well (architectural drawings look nothing like ImageNet photos):

**Unsupervised domain adaptation**:
- DANN (Domain-Adversarial Neural Network): Train feature extractor to be domain-invariant
- Maximum Mean Discrepancy (MMD): Minimize distribution distance between source and target features

**Self-supervised pre-training on AEC data**:
- MAE (Masked Autoencoder): Pre-train on unlabeled AEC images by masking and reconstructing patches
- DINO: Self-supervised ViT pre-training on AEC images
- Then fine-tune on labeled AEC dataset

This approach is recommended when you have many unlabeled AEC images (common) but few labeled ones (also common).

---

## 4. Model Evaluation Metrics

### 4.1 Object Detection Metrics

**IoU (Intersection over Union)**:
```
IoU = Area(Prediction ∩ Ground Truth) / Area(Prediction ∪ Ground Truth)
Range: 0 (no overlap) to 1 (perfect overlap)
Threshold: IoU ≥ 0.5 is standard; ≥ 0.75 for strict evaluation
```

**Precision and Recall**:
```
Precision = True Positives / (True Positives + False Positives)
  "Of all detections, how many are correct?"

Recall = True Positives / (True Positives + False Negatives)
  "Of all ground truth objects, how many are detected?"
```

**Average Precision (AP)**:
- Compute precision at each recall level (by varying confidence threshold)
- AP = area under precision-recall curve
- AP@0.5: Using IoU threshold 0.5
- AP@0.75: Using IoU threshold 0.75 (stricter)
- AP@[0.5:0.95]: Average over IoU thresholds 0.5 to 0.95 in steps of 0.05 (COCO standard)

**mAP (mean Average Precision)**:
- Average AP across all classes
- mAP@0.5, mAP@0.75, mAP@[0.5:0.95]

**For AEC applications**:
- mAP@0.5 is sufficient for most tasks (detecting doors, windows, workers)
- mAP@0.75 for precision-critical tasks (structural element measurement from detection)
- Report per-class AP to identify which elements are hardest to detect

### 4.2 Segmentation Metrics

**Pixel-level metrics**:
```
Pixel Accuracy = correct pixels / total pixels
  Misleading for imbalanced classes (e.g., 90% background → 90% accuracy by predicting all background)

Mean IoU (mIoU) = (1/K) * Σ IoU_k for k = 1..K classes
  Standard metric for semantic segmentation
  More informative than pixel accuracy

Dice Coefficient = 2 * |P ∩ G| / (|P| + |G|)
  Equivalent to F1 score at pixel level
  Common in medical/architectural segmentation

Boundary F1 (BF) = F1 score computed only on boundary pixels
  Better for evaluating boundary precision (important for wall/room delineation)
```

**For AEC floor plan segmentation**:
- mIoU ≥ 0.80 is good for wall/room segmentation
- mIoU ≥ 0.70 is acceptable for fine-grained element detection (doors, windows)
- Boundary F1 is particularly important for accurate room area calculation

### 4.3 Instance Segmentation Metrics

- AP (Average Precision) as in object detection, but using mask IoU instead of box IoU
- PQ (Panoptic Quality): Combines segmentation and recognition quality
  ```
  PQ = SQ * RQ
  SQ (Segmentation Quality) = average IoU of matched instances
  RQ (Recognition Quality) = TP / (TP + 0.5*FP + 0.5*FN)
  ```

### 4.4 F1 Score and Confusion Matrix

For multi-class problems, always compute a confusion matrix to understand where errors occur:

```
Example: Floor Plan Element Classification

                 Predicted
              Wall  Door  Window  Room  BG
Actual Wall  [950    15    5      10    20]
      Door   [ 20   180   10      0     5]
      Window [ 10    15   175      0     0]
      Room   [  5     0    0     890    5]
      BG     [ 30     5    5      15   945]

Per-class F1:
  Wall:   Precision=0.94, Recall=0.95, F1=0.94
  Door:   Precision=0.84, Recall=0.84, F1=0.84
  Window: Precision=0.90, Recall=0.88, F1=0.89
  Room:   Precision=0.97, Recall=0.99, F1=0.98
  BG:     Precision=0.97, Recall=0.95, F1=0.96

Macro F1: 0.92
```

Doors are hardest to detect (lowest F1). This is common in AEC: doors are small, vary in representation, and can be confused with openings.

---

## 5. Deployment on Edge Devices

### 5.1 Edge Hardware for AEC

| Device | Compute | Power | Cost | Use Case |
|--------|---------|-------|------|----------|
| NVIDIA Jetson Nano | 472 GFLOPS | 5-10W | $150 | Simple detection, low FPS |
| NVIDIA Jetson Orin Nano | 40 TOPS | 7-15W | $250 | Multi-model, real-time |
| NVIDIA Jetson AGX Orin | 275 TOPS | 15-60W | $1000+ | Complex pipelines, high FPS |
| Intel Neural Compute Stick 2 | 1 TOPS | 1.5W | $70 | Ultra-low power, basic inference |
| Google Coral TPU | 4 TOPS | 2W | $60 | TFLite models, fast for small models |
| Raspberry Pi 5 + AI Kit | 13 TOPS | 5W | $100 | Prototyping, low-cost deployment |

### 5.2 Model Optimization for Edge

**Quantization**: Reduce model precision from FP32 to FP16 or INT8
- FP16: 2x speedup, minimal accuracy loss (~0.1% mAP drop)
- INT8: 4x speedup, small accuracy loss (~0.5-1% mAP drop)
- Tools: TensorRT (NVIDIA), ONNX Runtime, PyTorch quantization, TFLite

**Pruning**: Remove unimportant weights/channels
- Structured pruning: Remove entire channels (faster inference on hardware)
- Magnitude pruning: Remove weights below threshold
- Typical: 30-50% pruning with <1% accuracy loss

**Knowledge distillation**: Train a small student model to mimic a large teacher model
- Teacher: YOLOv8-Large (high accuracy)
- Student: YOLOv8-Nano (fast, deployable on edge)
- Student learns soft targets from teacher; better than training student alone

**Model export pipeline for AEC edge deployment**:
```
PyTorch model (.pt)
  → Export to ONNX (.onnx)
    → Optimize with TensorRT (.engine) [NVIDIA devices]
    → Or convert to TFLite (.tflite) [Coral, mobile]
    → Or convert to OpenVINO IR (.xml) [Intel devices]
```

### 5.3 Real-Time Inference Pipeline

For construction site safety monitoring:

```python
# Inference pipeline for site safety camera
import cv2
from ultralytics import YOLO

# Load optimized model
model = YOLO("safety_model.engine")  # TensorRT optimized

cap = cv2.VideoCapture("rtsp://site-camera-01/stream")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run inference
    results = model(frame, conf=0.5, iou=0.45)

    # Check for safety violations
    for det in results[0].boxes:
        cls = int(det.cls)
        conf = float(det.conf)
        if cls == CLASS_NO_HARDHAT and conf > 0.6:
            trigger_alert(frame, det, "Missing hard hat")
        elif cls == CLASS_NO_VEST and conf > 0.6:
            trigger_alert(frame, det, "Missing safety vest")

    # Display or stream annotated frame
    annotated = results[0].plot()
    stream_output(annotated)
```

---

## 6. AEC-Specific Datasets

### 6.1 Floor Plan Datasets

| Dataset | Images | Annotation | Format | Resolution | Access |
|---------|--------|-----------|--------|------------|--------|
| CubiCasa5K | 5,000 | Walls, rooms, doors, windows | SVG + raster | 800x800 | Public (GitHub) |
| RPLAN | 80,000 | Rooms with boundaries + types | Vector | Varies | Request (authors) |
| HousExpo | 35,126 | Room polygons | JSON | Varies | Public (GitHub) |
| LIFULL HOME'S | 5M+ | Floor plan images | JPEG | Varies | Research agreement |
| CVC-FP | 122 | Walls, doors, windows, rooms | PNG masks | 2000+ | Public |
| ROBIN | 107 | Rich annotation, 20 classes | COCO format | Varies | Public |
| SESYD | 1000 | Synthetic, symbols | SVG | Varies | Public |

### 6.2 Construction Safety Datasets

| Dataset | Images | Classes | Annotation | Access |
|---------|--------|---------|-----------|--------|
| SHEL5K | 5,000 | Hard hat / no hard hat | Bounding box | Public |
| SODA | 9,000 | Safety objects | Bounding box | Public |
| Chi-SID | 2,000+ | Workers, equipment, PPE | Bounding box + keypoints | Public |
| MOCS | 16,000+ | Construction objects | Bounding box | Research request |
| Pictor-v3 | 774 | Workers, PPE | Bounding box | Public |

### 6.3 Structural Damage Datasets

| Dataset | Images | Classes | Application |
|---------|--------|---------|-------------|
| Concrete Crack Images | 40,000 | Crack / no crack | Classification |
| SDNET2018 | 56,000 | Crack / no crack (bridge decks, walls, pavements) | Classification |
| CrackForest | 118 | Crack masks | Segmentation |
| Earthquake Damage | Varies | None/slight/moderate/severe/collapse | Classification |
| Corrosion Detection | ~1,500 | Corrosion / no corrosion | Classification |

### 6.4 Point Cloud Datasets (Indoor/Building)

| Dataset | Points | Classes | Scenes | Application |
|---------|--------|---------|--------|-------------|
| S3DIS | 696M | 13 | 6 areas, 271 rooms | Indoor building segmentation |
| ScanNet | 2.5M frames | 40 | 1,513 scans | Indoor reconstruction |
| Matterport3D | 10,800 panoramas | 40 | 90 buildings | Indoor segmentation |
| ARKitScenes | 5,047 scans | 17 | Diverse indoor | AR/reconstruction |

---

## 7. Pre-Trained Model Sources

### 7.1 General Pre-Trained Models

| Source | Models | License | Notes |
|--------|--------|---------|-------|
| PyTorch Hub / torchvision | ResNet, EfficientNet, ViT, Swin, ConvNeXt | BSD | ImageNet pre-trained |
| Hugging Face | ViT, DeiT, BEiT, DINO, SAM, SegFormer | Various | Many architectures |
| Ultralytics | YOLOv5, YOLOv8, YOLOv9, RT-DETR | AGPL / Enterprise | Detection, segmentation, classification |
| Detectron2 | Faster R-CNN, Mask R-CNN, Panoptic FPN | Apache 2.0 | COCO pre-trained |
| MMDetection | 200+ detection/segmentation models | Apache 2.0 | Comprehensive model zoo |
| ONNX Model Zoo | Various CV models | MIT | Optimized for inference |
| TensorFlow Hub | Various CV models | Apache 2.0 | TF ecosystem |

### 7.2 AEC-Specific Pre-Trained Models

As of 2026, AEC-specific pre-trained models are limited but growing:

- **CubiCasa** floor plan analysis model (proprietary)
- **Roboflow Universe**: Community-trained models for construction safety, crack detection
- **Open3D-ML** models pre-trained on S3DIS for indoor point cloud segmentation
- **Research paper code**: Many papers release trained models (check GitHub repositories)

### 7.3 Foundation Models Useful for AEC

| Model | Provider | Capability | AEC Application |
|-------|----------|-----------|-----------------|
| **SAM (Segment Anything)** | Meta | Zero-shot segmentation | Interactive building element segmentation |
| **DINOv2** | Meta | Self-supervised visual features | Feature extraction for AEC image retrieval |
| **GroundingDINO** | IDEA | Open-vocabulary detection | Detect AEC elements by text description |
| **Florence-2** | Microsoft | Multi-task vision-language | Caption + detect + segment building images |
| **Stable Diffusion** | Stability AI | Image generation | Architectural rendering, sketch-to-photo |
| **ControlNet** | Various | Conditional generation | Sketch-guided rendering, style transfer |

**Recommended workflow**: Use SAM or GroundingDINO for initial annotation (ML-assisted labeling), then fine-tune a specialized model (YOLOv8, U-Net) on the resulting labeled dataset for production deployment. This dramatically reduces manual annotation effort.

---

## 8. End-to-End AEC CV Pipeline Example

### Facade Element Detection Pipeline

```python
"""
Complete pipeline: Facade image → detected elements (windows, doors, panels)
"""

# 1. Data Preparation
from ultralytics import YOLO
import albumentations as A
from albumentations.pytorch import ToTensorV2

# Define augmentation pipeline
train_transform = A.Compose([
    A.RandomResizedCrop(640, 640, scale=(0.8, 1.0)),
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
    A.GaussNoise(var_limit=(10, 50), p=0.3),
    A.CLAHE(clip_limit=4.0, p=0.3),
], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))

# 2. Model Training
model = YOLO("yolov8m.pt")  # Pre-trained on COCO

results = model.train(
    data="facade_dataset.yaml",  # Dataset config
    epochs=100,
    imgsz=640,
    batch=16,
    lr0=0.01,
    lrf=0.001,
    mosaic=0.8,
    mixup=0.1,
    close_mosaic=10,  # Disable mosaic for last 10 epochs
    patience=20,      # Early stopping
    project="facade_detection",
    name="yolov8m_facades",
)

# 3. Evaluation
metrics = model.val()
print(f"mAP@0.5: {metrics.box.map50:.3f}")
print(f"mAP@0.5:0.95: {metrics.box.map:.3f}")
# Per-class AP
for i, cls_name in enumerate(model.names.values()):
    print(f"  {cls_name}: AP@0.5 = {metrics.box.ap50[i]:.3f}")

# 4. Export for deployment
model.export(format="onnx", dynamic=True, simplify=True)
model.export(format="engine", half=True)  # TensorRT FP16

# 5. Inference on new facade image
model = YOLO("facade_detection/yolov8m_facades/weights/best.pt")
results = model("new_facade.jpg", conf=0.5, iou=0.45)

# 6. Post-processing: extract element inventory
for det in results[0].boxes:
    cls = model.names[int(det.cls)]
    conf = float(det.conf)
    x1, y1, x2, y2 = det.xyxy[0].tolist()
    width = x2 - x1
    height = y2 - y1
    print(f"{cls}: {conf:.2f}, size={width:.0f}x{height:.0f}px")
```

### Performance Targets for AEC CV Applications

| Application | Metric | Target | Minimum Acceptable |
|-------------|--------|--------|-------------------|
| Construction safety (PPE) | mAP@0.5 | >0.90 | >0.80 |
| Floor plan wall detection | mIoU | >0.85 | >0.75 |
| Facade element detection | mAP@0.5 | >0.85 | >0.75 |
| Crack detection | Dice coefficient | >0.80 | >0.70 |
| Room segmentation | mIoU | >0.80 | >0.70 |
| Door/window detection | mAP@0.5 | >0.80 | >0.70 |
| Drawing symbol recognition | mAP@0.5 | >0.90 | >0.80 |
| Point cloud segmentation | mIoU | >0.70 | >0.60 |
