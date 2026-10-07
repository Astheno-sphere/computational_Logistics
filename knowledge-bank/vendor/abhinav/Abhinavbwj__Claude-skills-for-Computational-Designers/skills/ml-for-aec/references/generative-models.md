# Generative ML Models for AEC: Deep Reference

This reference provides comprehensive technical detail on generative model architectures, training methodologies, evaluation metrics, and practical guidance for applying generative ML to architectural and engineering design.

---

## 1. GAN Architectures for AEC

### 1.1 Fundamentals of GANs

A GAN consists of two networks trained adversarially:

**Generator G**: Maps random noise z (sampled from latent distribution, typically Gaussian) to a data sample G(z). Objective: produce samples indistinguishable from real data.

**Discriminator D**: Classifies inputs as real (from training data) or fake (from generator). Objective: correctly distinguish real from generated samples.

**Training objective** (minimax game):
```
min_G max_D  V(D, G) = E[log D(x)] + E[log(1 - D(G(z)))]

where:
  x ~ real data distribution
  z ~ latent distribution (e.g., N(0, I))
```

The generator improves by fooling the discriminator; the discriminator improves by detecting fakes. At equilibrium, the generator produces samples indistinguishable from real data.

### 1.2 pix2pix (Image-to-Image Translation)

**Architecture**:
```
Generator: U-Net (encoder-decoder with skip connections)
  Input: Condition image (e.g., sketch, segmentation map)
  Output: Translated image (e.g., rendered facade, floor plan)

  Encoder: [Conv-BN-LeakyReLU-Conv-BN-LeakyReLU-Downsample] x 8
  Decoder: [Upsample-Conv-BN-ReLU-Dropout-Conv-BN-ReLU] x 8
  Skip connections: Concatenate encoder and decoder features at each level

Discriminator: PatchGAN (70x70 patches)
  Input: Concatenation of condition image and output image
  Output: N x N grid of real/fake predictions (each predicting a patch)
  Architecture: [Conv-LeakyReLU] → [Conv-BN-LeakyReLU] x 3 → Conv → Sigmoid

Loss:
  L_GAN = standard GAN loss (BCE)
  L_L1 = ||G(x) - y||_1 (pixel-wise L1 reconstruction loss)
  L_total = L_GAN + λ * L_L1  (λ = 100 by default)
```

**AEC applications of pix2pix**:

| Input (Condition) | Output (Generated) | Training Data |
|-------------------|-------------------|---------------|
| Architectural sketch | Rendered facade | Sketch-rendering pairs |
| Zoning/program diagram | Floor plan layout | Zoning-floor plan pairs |
| Section outline | Detailed section | Outline-detail pairs |
| Height map / massing | Site plan rendering | Height map-aerial pairs |
| Grayscale floor plan | Colored/annotated plan | Plain-annotated pairs |
| Edge map of facade | Photo-realistic facade | Edge-photo pairs |

**Training tips for AEC pix2pix**:
- Minimum 200 training pairs for simple tasks; 500-1000 for complex tasks
- Image size: 256x256 (fast) to 512x512 (better quality); 1024x1024 possible with more GPU memory
- L1 weight (lambda): 100 for floor plans (structure matters); 10-50 for renderings (texture variety preferred)
- Training time: 200-500 epochs; ~2-8 hours on a single GPU
- Use paired data: ensure input and output are pixel-aligned

### 1.3 CycleGAN (Unpaired Image Translation)

**Key innovation**: Learns mappings between two domains without paired examples using cycle consistency.

**Architecture**:
```
Generator G_AB: Translates domain A → domain B (ResNet-based)
Generator G_BA: Translates domain B → domain A (ResNet-based)
Discriminator D_A: Distinguishes real A from fake A
Discriminator D_B: Distinguishes real B from fake B

Cycle consistency loss:
  L_cycle = ||G_BA(G_AB(a)) - a||_1 + ||G_AB(G_BA(b)) - b||_1
  "If I translate A→B→A, I should get back the original A"

Identity loss (optional, preserves color):
  L_identity = ||G_AB(b) - b||_1 + ||G_BA(a) - a||_1

Total loss: L_GAN(G_AB, D_B) + L_GAN(G_BA, D_A) + λ_cyc * L_cycle + λ_id * L_identity
```

**AEC applications**:
- Style transfer: Modern building → Classical style (and vice versa)
- Season transfer: Summer site → Winter visualization
- Time of day: Daytime rendering → Nighttime rendering
- Sketch-to-photo: Architectural sketch → Photo-realistic image (when paired data is unavailable)
- As-built to clean: Construction photo → Clean rendering

**Limitations for AEC**: CycleGAN changes textures and colors effectively but struggles with geometric transformations. It cannot reliably add windows to a blank facade or rearrange room layouts. Use pix2pix for geometric tasks.

### 1.4 StyleGAN (Style-Based Generation)

**Architecture** (StyleGAN2/3):
```
Mapping network: z (512-dim) → MLP (8 FC layers) → w (512-dim style vector)
  w represents "style" — disentangled from noise

Synthesis network: Progressively grows image from 4x4 to 1024x1024
  Each block:
    - Upsample (bilinear)
    - Modulated convolution (convolution weights modulated by w)
    - Add noise (per-pixel random noise for stochastic detail)
    - LeakyReLU activation

Style mixing:
  - Different w vectors can be used at different layers
  - Coarse layers (4x4 - 16x16): control pose, shape, structure
  - Medium layers (32x32 - 128x128): control features, proportions
  - Fine layers (256x256 - 1024x1024): control color, texture, micro-details
```

**AEC applications**:
- **Facade texture generation**: Train on building facade photographs; generate novel facade textures. Fine layers control material appearance; coarse layers control overall composition.
- **Interior design exploration**: Train on interior photographs; interpolate between styles (modern, traditional, minimalist, industrial).
- **Synthetic training data**: Generate diverse building images for training other CV models.
- **Design exploration**: Navigate latent space to explore design variations.

**Style mixing for architecture**:
```python
# Mix coarse structure from design A with fine details from design B
w_structure = mapping(z_design_A)  # Shape, proportions
w_detail = mapping(z_design_B)     # Materials, textures

# Use w_structure for layers 0-6, w_detail for layers 7-17
w_mixed = [w_structure] * 7 + [w_detail] * 11
generated = synthesis(w_mixed)
# Result: Design A's proportions with Design B's material palette
```

### 1.5 Conditional GAN (cGAN) for AEC

**Concept**: Generator and discriminator both receive additional conditioning information (label, image, graph, text).

**Conditioning methods**:
- **Label concatenation**: Append one-hot label to noise vector z
- **Feature-wise modulation**: Use condition to modulate intermediate features (AdaIN, FiLM)
- **Cross-attention**: Condition attends to generation features (as in text-conditioned models)
- **Spatial conditioning**: Concatenate spatial map (segmentation, edge map) with input

**AEC conditional generation examples**:
```
Condition: "3-bedroom apartment, 85m2, south-facing living room"
→ Encode as vector: [num_bedrooms=3, area=85, orientation=south, ...]
→ Generator produces floor plan conditioned on this vector

Condition: Room adjacency graph
→ Encode graph with GNN: node features (room type, area), edge features (adjacency strength)
→ Generator produces floor plan layout conditioned on graph embedding

Condition: Building height + footprint outline
→ Encode as image (footprint mask + height map)
→ Generator produces facade rendering conditioned on massing
```

---

## 2. VAE for Design Exploration

### 2.1 VAE Architecture

```
Encoder q(z|x):
  Input: Design representation (image, graph, parameter vector)
  Output: μ (mean) and σ (standard deviation) of latent distribution
  Architecture: CNN for images, GNN for graphs, MLP for parameter vectors

Reparameterization trick:
  z = μ + σ * ε, where ε ~ N(0, I)
  (Enables gradient to flow through sampling)

Decoder p(x|z):
  Input: Latent vector z
  Output: Reconstructed design
  Architecture: Transposed CNN, GNN decoder, or MLP

Loss:
  L = Reconstruction_loss + β * KL_divergence
  Reconstruction: BCE (binary data) or MSE (continuous data)
  KL: D_KL(q(z|x) || p(z)) = -0.5 * Σ(1 + log(σ²) - μ² - σ²)
  β: Balances reconstruction quality vs. latent space regularity
```

### 2.2 Latent Space Properties for Design

**Interpolation**: Linearly interpolate between two designs in latent space:
```python
z_A = encoder(design_A)  # Latent vector for design A
z_B = encoder(design_B)  # Latent vector for design B

# Generate 10 intermediate designs
for alpha in np.linspace(0, 1, 10):
    z_interp = (1 - alpha) * z_A + alpha * z_B
    intermediate_design = decoder(z_interp)
    # Produces smooth transition from A to B
```

For AEC: Interpolate between a compact plan and an open plan; between a modern facade and a traditional one; between a low-rise and high-rise massing.

**Arithmetic in latent space**:
```
z_modern_house = encoder(modern_house)
z_traditional_house = encoder(traditional_house)
z_modern_apartment = encoder(modern_apartment)

z_traditional_apartment = z_traditional_house - z_modern_house + z_modern_apartment
traditional_apartment = decoder(z_traditional_apartment)
# Concept: "traditional" - "house" + "apartment" = "traditional apartment"
```

**Disentangled representations** (β-VAE): By increasing β > 1, the latent dimensions become more disentangled. Ideally, each latent dimension controls one factor of variation:
- z[0]: Building height
- z[1]: Facade transparency (WWR)
- z[2]: Plan compactness
- z[3]: Symmetry level

### 2.3 Conditional VAE (cVAE) for AEC

Condition the VAE on design requirements:
```
Encoder: q(z | x, c) where c = condition (program, site, constraints)
Decoder: p(x | z, c)

Generation: Sample z ~ N(0, I), decode with condition c
  → Generate design satisfying condition c with variation from z
```

**Application**: Condition on building program (room types and areas); generate diverse floor plan layouts. Different z samples produce different layouts, all satisfying the program.

---

## 3. Diffusion Models

### 3.1 DDPM (Denoising Diffusion Probabilistic Model)

**Forward process** (adding noise):
```
q(x_t | x_{t-1}) = N(x_t; √(1-β_t) * x_{t-1}, β_t * I)

Starting from clean data x_0, progressively add Gaussian noise over T steps
(T typically 1000). At step T, x_T ≈ pure Gaussian noise.

Closed form: x_t = √(ᾱ_t) * x_0 + √(1-ᾱ_t) * ε
where ᾱ_t = Π_{s=1}^{t} (1 - β_s), ε ~ N(0, I)
```

**Reverse process** (denoising, learned):
```
p_θ(x_{t-1} | x_t) = N(x_{t-1}; μ_θ(x_t, t), σ_t² * I)

A neural network predicts the noise ε_θ(x_t, t) added at step t.
Then: μ_θ = (1/√α_t) * (x_t - (β_t/√(1-ᾱ_t)) * ε_θ(x_t, t))

Training: minimize ||ε - ε_θ(x_t, t)||² (predict the noise)
```

**Noise schedule**: β_t increases linearly from β_1 = 0.0001 to β_T = 0.02 (standard).

**U-Net architecture for noise prediction**:
```
Input: Noisy image x_t and timestep t
  - Timestep embedding: sinusoidal positional encoding → MLP → add to features
  - Encoder: ResNet blocks with self-attention at 16x16, 8x8
  - Decoder: ResNet blocks with skip connections from encoder
  - Output: Predicted noise ε (same spatial dimensions as input)
```

### 3.2 Stable Diffusion for Architecture

**Architecture** (Latent Diffusion Model):
```
1. VAE encoder: Compress image x (512x512x3) → latent z (64x64x4)
   - 8x spatial compression
   - Diffusion operates in latent space (much faster than pixel space)

2. U-Net denoiser: Predict noise in latent space
   - Text conditioning via cross-attention:
     Text prompt → CLIP text encoder → text embeddings
     U-Net cross-attention layers attend to text embeddings
   - Timestep conditioning via sinusoidal embedding

3. VAE decoder: Decompress denoised latent → image
```

**Fine-tuning Stable Diffusion for AEC**:

**Full fine-tuning** (expensive, requires ~100+ GPU-hours):
- Replace entire U-Net weights with AEC-trained weights
- Need: 10,000+ high-quality architectural images
- Risk: Catastrophic forgetting of general image knowledge

**LoRA** (Low-Rank Adaptation) (recommended for AEC):
```python
# LoRA injects trainable low-rank matrices into attention layers
# Instead of fine-tuning W (d x d), train A (d x r) and B (r x d)
# where r << d (typically r=4-64)
# W_new = W_original + A @ B

# Training:
# - Dataset: 100-5000 architectural images
# - Training time: 2-8 hours on single GPU
# - LoRA rank: 4-32 (higher = more capacity, more overfitting risk)
# - Learning rate: 1e-4
# - Epochs: 500-2000 steps
```

**DreamBooth** (for specific architectural styles or buildings):
- Fine-tune on 10-30 images of a specific building or style
- Associates a unique identifier token with the subject
- "A photo of [V] building in modernist style" → generates that specific building style

**Textual Inversion** (lightest weight):
- Learn a new text embedding for a visual concept
- Only optimizes a single embedding vector (no model weight changes)
- "A [brutalist-concrete] facade with large windows" → learns what "brutalist-concrete" looks like from 5-10 examples

### 3.3 ControlNet for Architectural Generation

ControlNet adds spatial conditioning to Stable Diffusion without modifying the original model:

**Architecture**:
```
Original Stable Diffusion U-Net (frozen, no gradient)
+
ControlNet copy of encoder + middle block (trainable)
  - Input: Conditioning signal (edge map, depth, segmentation)
  - Zero convolution: Initialized to zero, gradually learns connection strength
  - Output: Added to original U-Net decoder features

Result: Generated image follows the spatial structure of the condition
while maintaining the quality and diversity of Stable Diffusion
```

**Control types for AEC**:

| Control Type | AEC Application | Preparation |
|-------------|-----------------|-------------|
| Canny edges | Sketch → rendered building | Run Canny edge detection on architectural sketch |
| Depth map | Massing → rendered building | Render depth map from 3D massing model |
| Segmentation map | Program diagram → floor plan rendering | Color-code rooms by type |
| Normal map | Surface detail control | Extract normals from 3D model |
| Scribble | Quick concept sketch → rendering | Rough hand-drawn sketch |
| LineArt | Detailed line drawing → rendering | Clean architectural line drawing |
| OpenPose | Human-scale visualization | Pose data for people in renderings |

**Multi-ControlNet**: Combine multiple conditions simultaneously:
```
Condition 1: Canny edge map (controls overall structure)
Condition 2: Depth map (controls spatial depth)
Condition 3: Segmentation map (controls material zones)

Weight each condition: 0.3 * Canny + 0.5 * Depth + 0.2 * Segmentation
→ Generated image respects all three conditions with specified emphasis
```

### 3.4 HouseDiffusion (Floor Plan Diffusion)

**Specialized diffusion model for floor plan generation**:

```
Input: Room adjacency graph G = (V, E)
  V: nodes with attributes (room_type, target_area)
  E: edges with attributes (adjacency_type: required, preferred)

Representation: Each room represented as a polygon (sequence of corner points)
  All corners diffused simultaneously in 2D coordinate space

Forward process: Add noise to room corner coordinates
  x_t = √(ᾱ_t) * x_0 + √(1-ᾱ_t) * ε
  where x_0 = corner coordinates of ground truth floor plan

Reverse process: GNN-based denoiser
  1. Encode graph structure with Graph Attention Network
  2. At each denoising step:
     - Compute graph-conditioned features for each room
     - Predict noise for each corner coordinate
     - Room-level constraints (area, non-overlap) applied as guidance
  3. After T denoising steps: clean floor plan layout

Post-processing:
  - Snap corners to grid
  - Enforce orthogonality
  - Ensure non-overlap
  - Add wall thickness
  - Place doors at adjacent room boundaries
```

**Advantages over GANs for floor plans**:
- More diverse outputs (mode coverage vs. mode collapse)
- Stable training (no adversarial dynamics)
- Controllable generation via guidance
- Better at satisfying constraints through iterative refinement

---

## 4. Graph Neural Networks for Layout

### 4.1 GNN Architecture for Floor Plan Generation

```
Input graph: G = (V, E, u)
  V: Room nodes with features [room_type_onehot, target_area, min_dim, daylight_required]
  E: Edge features [adjacency_type, adjacency_strength]
  u: Global features [total_area, building_type, num_floors]

Encoder (3-5 GNN layers):
  For each layer l:
    Message: m_{ij} = MLP_msg(h_i^l, h_j^l, e_{ij})  # Message from j to i
    Aggregate: M_i = Σ_{j∈N(i)} m_{ij}                 # Sum messages
    Update: h_i^{l+1} = MLP_upd(h_i^l, M_i)            # Update node embedding

  Options for message passing:
    - GCN: Simple weighted average of neighbors
    - GAT: Attention-weighted average (learned importance per edge)
    - MPNN: Custom message and update functions (most flexible)

Decoder:
  For each room node:
    MLP_pos: h_i → (x_i, y_i)         # Predict room center position
    MLP_size: h_i → (w_i, h_i)        # Predict room dimensions
    MLP_orient: h_i → rotation_i       # Predict room orientation (optional)

Loss:
  L_position = MSE(predicted_center, ground_truth_center)
  L_size = MSE(predicted_size, ground_truth_size)
  L_overlap = penalty for room overlaps
  L_adjacency = penalty for unsatisfied adjacencies
  L_boundary = penalty for rooms outside building boundary
  L = λ_pos * L_position + λ_size * L_size + λ_overlap * L_overlap + ...
```

### 4.2 Graph2Plan

**Pipeline**:
1. Input: Room adjacency graph + building boundary polygon
2. Graph encoding: Graph Attention Network encodes room relationships
3. Candidate retrieval: Find most similar floor plans in database (by graph similarity)
4. Layout prediction: GNN predicts room bounding boxes conditioned on graph and building boundary
5. Post-processing: Snap to grid, resolve overlaps, ensure adjacency

**Key insight**: Combining learning (GNN) with retrieval (similar floor plans from database) produces more realistic results than pure generation, because retrieved examples provide architectural priors.

### 4.3 Training Data Preparation for Graph Models

```python
import networkx as nx
import json

def floor_plan_to_graph(floor_plan):
    """Convert a floor plan to a room adjacency graph for GNN training."""

    G = nx.Graph()

    # Add room nodes
    for room in floor_plan.rooms:
        G.add_node(room.id, **{
            "type": room.type,               # e.g., "bedroom", "living", "kitchen"
            "type_onehot": one_hot(room.type, ROOM_TYPES),
            "area": room.area,
            "width": room.width,
            "height": room.height,
            "center_x": room.center_x,
            "center_y": room.center_y,
            "has_window": room.touches_exterior,
            "normalized_area": room.area / floor_plan.total_area,
        })

    # Add adjacency edges
    for i, room_a in enumerate(floor_plan.rooms):
        for j, room_b in enumerate(floor_plan.rooms):
            if i >= j:
                continue
            shared_wall = room_a.shared_wall_length(room_b)
            if shared_wall > 0:
                has_door = floor_plan.has_door_between(room_a, room_b)
                G.add_edge(room_a.id, room_b.id, **{
                    "shared_wall_length": shared_wall,
                    "has_door": has_door,
                    "adjacency_type": "direct" if has_door else "wall",
                })

    return G

# Generate dataset
graphs = []
for fp in floor_plan_database:
    G = floor_plan_to_graph(fp)
    graphs.append(G)

# Convert to PyTorch Geometric format for training
from torch_geometric.data import Data

def graph_to_pyg(G):
    """Convert NetworkX graph to PyTorch Geometric Data object."""
    # Node features
    x = torch.tensor([
        G.nodes[n]["type_onehot"] + [G.nodes[n]["normalized_area"]]
        for n in G.nodes
    ], dtype=torch.float)

    # Edge index
    edge_list = list(G.edges)
    edge_index = torch.tensor(
        [[e[0] for e in edge_list] + [e[1] for e in edge_list],
         [e[1] for e in edge_list] + [e[0] for e in edge_list]],
        dtype=torch.long
    )

    # Target: room positions and sizes
    y_pos = torch.tensor([
        [G.nodes[n]["center_x"], G.nodes[n]["center_y"]]
        for n in G.nodes
    ], dtype=torch.float)

    y_size = torch.tensor([
        [G.nodes[n]["width"], G.nodes[n]["height"]]
        for n in G.nodes
    ], dtype=torch.float)

    return Data(x=x, edge_index=edge_index, y_pos=y_pos, y_size=y_size)
```

---

## 5. Training Stability

### 5.1 Mode Collapse

**Problem**: Generator learns to produce only a small subset of possible outputs, ignoring the diversity of the real data distribution. For AEC: the GAN generates the same floor plan layout regardless of input conditions.

**Detection**: Inspect generated samples for visual diversity; compute intra-batch diversity metrics; monitor discriminator confidence.

**Mitigation strategies**:
- **Minibatch discrimination**: Discriminator receives statistics about the entire batch, detecting lack of diversity
- **Feature matching**: Generator loss includes matching statistics of intermediate discriminator features, not just the final output
- **Unrolled GAN**: Generator optimizes against a "future" discriminator (unrolled optimization steps)
- **Spectral normalization**: Normalize discriminator weights to stabilize training
- **Progressive growing**: Start training at low resolution, gradually increase
- **Use diffusion models instead**: Diffusion models do not suffer from mode collapse by design

### 5.2 Gradient Vanishing

**Problem**: If the discriminator becomes too strong, its gradients to the generator vanish (discriminator confidently classifies all fakes as fake; gradient of log(1-D(G(z))) → 0).

**Mitigation**:
- **Wasserstein GAN (WGAN)**: Replace JS divergence with Wasserstein distance; use weight clipping or gradient penalty. Loss is Lipschitz-continuous, providing useful gradients even when distributions do not overlap.
- **WGAN-GP (Gradient Penalty)**:
  ```
  L_D = E[D(fake)] - E[D(real)] + λ * E[(||∇D(interpolated)||₂ - 1)²]
  λ = 10 (standard)
  ```
- **R1 regularization**: Penalize discriminator gradient magnitude on real samples
- **Two-timescale learning**: Train discriminator slower than generator (lower learning rate or fewer updates per step)

### 5.3 Training Instability Diagnostics

**Metrics to monitor during training**:
- Generator loss and discriminator loss (should oscillate, not diverge)
- FID (Frechet Inception Distance) on validation set (should decrease over time)
- Discriminator accuracy (should hover around 50-70%, not 100%)
- Generated sample diversity (visual inspection, intra-batch diversity)

**Warning signs**:
- Discriminator loss → 0 (too strong, generator cannot learn)
- Generator loss oscillates wildly (unstable adversarial dynamics)
- Generated samples look identical (mode collapse)
- FID increases after initial decrease (overfitting or instability)

### 5.4 Practical Training Recipe for AEC GANs

```
Architecture: pix2pix (conditional) or WGAN-GP (unconditional)
Image size: 256x256 (start here), scale to 512x512 if data is sufficient
Batch size: 16-32
Learning rate:
  Generator: 2e-4
  Discriminator: 2e-4 (pix2pix) or 1e-4 (WGAN-GP, slower discriminator)
Optimizer: Adam(β1=0.5, β2=0.999)
Training ratio: 1:1 for pix2pix; 5D:1G for WGAN-GP
Epochs: 200-500 (monitor FID on validation set)
Augmentation: Horizontal flip, slight color jitter (not rotation for floor plans)
Regularization:
  - Spectral normalization on discriminator
  - Dropout 0.5 in generator (pix2pix)
  - L1 reconstruction loss (pix2pix, λ=100)
```

---

## 6. Evaluation Metrics for Generative Models

### 6.1 FID (Frechet Inception Distance)

The standard metric for evaluating generative image quality:

```
FID = ||μ_real - μ_fake||² + Tr(Σ_real + Σ_fake - 2(Σ_real * Σ_fake)^(1/2))

where:
  μ, Σ = mean and covariance of Inception-v3 features (pool3 layer, 2048-dim)
  Computed on real and generated image sets

Interpretation:
  FID = 0: Generated distribution identical to real
  FID < 10: Excellent (indistinguishable to non-experts)
  FID 10-50: Good (recognizable as generated but plausible)
  FID 50-100: Fair (noticeable artifacts or style differences)
  FID > 100: Poor (clearly unrealistic)

Requirements:
  Minimum 10,000 images for reliable FID computation
  Same image size and preprocessing for real and generated sets
```

**Limitation for AEC**: Inception features are trained on ImageNet (natural images). They may not capture architecture-specific quality. Consider computing FID with features from an AEC-fine-tuned backbone.

### 6.2 IS (Inception Score)

```
IS = exp(E[KL(p(y|x) || p(y))])

where:
  p(y|x) = class distribution for a single generated image (should be peaked → recognizable)
  p(y) = marginal class distribution across all generated images (should be uniform → diverse)

Higher IS = better (both quality and diversity)
```

**Limitation**: IS does not compare to real data distribution; only evaluates generated samples internally. Less useful than FID for AEC.

### 6.3 LPIPS (Learned Perceptual Image Patch Similarity)

```
LPIPS = Σ_l w_l * ||φ_l(x) - φ_l(x_hat)||²

where:
  φ_l = features from layer l of a pre-trained network (VGG, AlexNet)
  w_l = learned weights per layer
  x, x_hat = real and generated images

Lower LPIPS = more perceptually similar
```

**Use in AEC**: Compare generated floor plans or renderings to ground truth. LPIPS correlates better with human judgment than pixel-wise MSE.

### 6.4 AEC-Specific Evaluation Metrics

Beyond image-quality metrics, AEC generative models should be evaluated on domain-specific criteria:

**Floor plan generation metrics**:
```python
def evaluate_floor_plan(generated, program):
    metrics = {}

    # 1. Area accuracy: Do rooms match target areas?
    metrics["area_mape"] = mean([
        abs(gen_room.area - prog_room.target_area) / prog_room.target_area
        for gen_room, prog_room in zip(generated.rooms, program.rooms)
    ])

    # 2. Adjacency satisfaction: Are required adjacencies present?
    total_adj = sum(1 for a in program.adjacencies if a.required)
    satisfied = sum(1 for a in program.adjacencies
                    if a.required and generated.rooms_adjacent(a.room_a, a.room_b))
    metrics["adjacency_rate"] = satisfied / total_adj

    # 3. Non-overlap: Do rooms overlap?
    metrics["overlap_area"] = calculate_total_overlap(generated.rooms)

    # 4. Boundary compliance: Are all rooms within boundary?
    metrics["boundary_violation"] = calculate_boundary_violation(
        generated.rooms, generated.boundary
    )

    # 5. Aspect ratio quality
    metrics["mean_aspect_ratio"] = mean([
        max(r.width, r.height) / min(r.width, r.height)
        for r in generated.rooms
    ])

    # 6. Window access: Do daylight-required rooms touch exterior?
    daylight_rooms = [r for r in generated.rooms if r.requires_daylight]
    metrics["daylight_rate"] = mean([
        1 if r.touches_exterior(generated.boundary) else 0
        for r in daylight_rooms
    ])

    return metrics
```

**Facade generation metrics**:
- Window-to-wall ratio accuracy (compared to target)
- Symmetry score (if design intent is symmetric)
- Structural grid alignment
- Material distribution realism
- Solar shading adequacy (compared to performance target)

### 6.5 Human Evaluation Protocol

For AEC generative models, human evaluation by domain experts is essential:

1. **Turing test**: Show architects real and generated floor plans; ask them to identify which is generated. Score: percentage of correct identifications (50% = indistinguishable).
2. **Quality rating**: Architects rate generated designs on a 1-5 scale for:
   - Functional quality (does the layout work?)
   - Aesthetic quality (does it look like good architecture?)
   - Code compliance (would this pass a code review?)
   - Constructability (could this be built?)
3. **Comparative evaluation**: Show two generated layouts for the same program; ask which is better and why.
4. **Preference alignment**: Compare model rankings to architect rankings on a set of designs.

---

## 7. Fine-Tuning Pre-Trained Models for AEC

### 7.1 LoRA Fine-Tuning for Stable Diffusion

```python
# Using diffusers library (Hugging Face)
from diffusers import StableDiffusionPipeline
from peft import LoraConfig

# Load base model
pipe = StableDiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-2-1",
    torch_dtype=torch.float16
)

# Define LoRA configuration
lora_config = LoraConfig(
    r=16,                    # LoRA rank (4-64; higher = more capacity)
    lora_alpha=32,           # Scaling factor (typically 2 * r)
    target_modules=[         # Which layers to adapt
        "to_q", "to_v",      # Cross-attention query and value
        "to_k", "to_out.0",  # Cross-attention key and output
    ],
    lora_dropout=0.05,
)

# Training configuration
training_args = {
    "instance_prompt": "a photograph of a [AEC_STYLE] building facade",
    "resolution": 512,
    "train_batch_size": 1,
    "gradient_accumulation_steps": 4,
    "learning_rate": 1e-4,
    "lr_scheduler": "cosine",
    "max_train_steps": 2000,
    "mixed_precision": "fp16",
    "seed": 42,
}

# Train LoRA weights on AEC dataset
# Dataset: 200-2000 high-quality architectural images
# Training time: 2-6 hours on single A100 GPU
```

### 7.2 ControlNet Training for AEC

```python
# Training a custom ControlNet for architectural sketches
from diffusers import ControlNetModel

# Initialize ControlNet from pre-trained SD encoder
controlnet = ControlNetModel.from_unet(
    pipe.unet,
    conditioning_channels=3,  # 3 for RGB control image
)

# Training data preparation:
# 1. Collect architectural images (photos/renderings)
# 2. Generate control images:
#    - Canny edges (for sketch control)
#    - Depth maps (for massing control)
#    - Segmentation maps (for zone control)
# 3. Pair: (control_image, target_image, text_prompt)

# Training: ~50K-100K steps on 8xA100
# Smaller AEC-specific datasets: fine-tune existing ControlNet instead
```

---

## 8. Prompt Engineering for Architectural Generation

### 8.1 Effective Architectural Prompts

**Structure**: `[Medium] of [Subject] in [Style], [Attributes], [Technical Specs]`

**Examples**:
```
Positive prompts:
"architectural photograph of a residential facade, brutalist concrete,
 exposed aggregate, geometric window pattern, golden hour lighting,
 professional photography, 4K, detailed"

"aerial view of an urban masterplan, mixed-use development, green roofs,
 pedestrian plazas, modern contemporary, high detail, photorealistic"

"interior of a minimalist office space, exposed concrete ceiling,
 floor-to-ceiling glazing, warm wood accents, natural daylight,
 architectural digest style"

"section drawing of a multi-story building, concrete structure,
 curtain wall facade, rooftop garden, underground parking,
 architectural rendering style, detailed"

Negative prompts (what to avoid):
"blurry, low quality, distorted, deformed, unrealistic proportions,
 cartoon, anime, painting style, watermark, text overlay,
 impossible geometry, floating objects"
```

### 8.2 Style-Specific Prompt Keywords

| Architectural Style | Prompt Keywords |
|-------------------|-----------------|
| Modernist | clean lines, white walls, pilotis, ribbon windows, flat roof, Le Corbusier |
| Brutalist | exposed concrete, raw, massive, geometric, fortress-like, Board-formed concrete |
| Parametric | organic forms, flowing curves, algorithmic, Zaha Hadid, computational |
| Minimalist | simple, restrained, white, precise, Tadao Ando, light and shadow |
| High-Tech | structural expression, glass and steel, exposed services, Rogers, Foster |
| Biophilic | green walls, natural materials, daylight, indoor plants, sustainable |
| Vernacular | local materials, traditional proportions, contextual, regional character |
| Deconstructivist | fragmented, angular, dynamic, Gehry, Libeskind, collision of forms |

### 8.3 Technical Quality Keywords

For higher quality architectural renders:
- "8K resolution, photorealistic, ray-traced, global illumination"
- "architectural photography, professional lighting, f/8 aperture"
- "V-Ray render, Lumion render, Enscape quality"
- "detailed materials, realistic textures, accurate scale"
- "human figures for scale" (but AI-generated people may look uncanny)

### 8.4 Prompt Weighting (Stable Diffusion)

Control emphasis on different aspects:
```
"(brutalist concrete facade:1.3), (large geometric windows:1.2),
 sunset lighting, (professional photography:0.8)"

Numbers > 1.0: Increase emphasis
Numbers < 1.0: Decrease emphasis
Range: 0.5 to 1.5 (extremes cause artifacts)
```

---

## 9. Current Research Frontiers

### 9.1 3D-Aware Generative Models

- **NeRF-based generation**: Generate 3D buildings as neural radiance fields; render from any viewpoint
- **3D Gaussian Splatting**: Faster alternative to NeRF for 3D scene generation
- **Multi-view diffusion**: Generate consistent images from multiple viewpoints of a building
- **Current state**: Promising for visualization; not yet suitable for producing precise BIM geometry

### 9.2 Physics-Informed Generative Models

- Incorporating structural constraints into the generation process
- Penalizing physically impossible designs during training (unsupported cantilevers, excessive spans)
- Conditioning on load paths, material capabilities
- **Challenge**: Combining ML flexibility with physics rigor without losing generative diversity

### 9.3 Interactive Generative Design

- Real-time generation as the designer sketches (ControlNet + efficient inference)
- Iterative refinement: designer edits generated output, model adapts
- Multi-modal input: sketch + text + reference images simultaneously
- **Latency target**: <2 seconds for interactive workflow

### 9.4 Foundation Models for AEC

- Pre-train large models on diverse AEC data (drawings, photos, BIM, text)
- Fine-tune for specific tasks (floor plan generation, facade design, rendering)
- Multi-task models that understand drawings, 3D models, and natural language
- **Challenge**: AEC data is orders of magnitude smaller than internet-scale data used for general foundation models
