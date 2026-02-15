# Texturalia

<div align="center">

![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Version](https://img.shields.io/badge/version-v2.4.4-blue?style=flat-square&logo=blender)
![Blender](https://img.shields.io/badge/blender-4.2%2B-orange?style=flat-square&logo=blender)
![Python](https://img.shields.io/badge/python-3.11%2B-yellow?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square)

**The most powerful AI-Enhanced Texture Generation & Baking tool for Blender.**

[Features](#-key-features) • [Installation](#-installation) • [Workflow](#-workflow) • [Requirements](#-requirements)

</div>

---

## 🆕 What's New in v2.4.4
- **🎨 Fixed Paint Visibility**: Model now renders visually correct (Solid Black) for masking.
- **🚫 Disabled Wireframes**: Viewport stays clean; wireframes are no longer forced on.
- **💡 Fixed Preview Colors**: "Live Preview" uses an Emission Shader (Shadeless) for 100% color accuracy.
- **✏️ UI Polish**: Renamed generic terms (e.g., "Radius" -> "Size") for better UX.

---

## ✨ Key Features

### 📸 Advanced Camera Rig
- **Automated Setup**: Instantly generates a 6-view orthographic rig.
- **Custom Views**: Add orbital cameras, adjust angles, and focus on details.
- **Precision Control**: Fine-tune distance, lens scale, and target height per view.

### 🎨 Local AI Enhancement (ComfyUI)
- **Direct Integration**: Connects seamlessly to your local ComfyUI instance.
- **Text-to-Texture**: Use prompts to generate textures for each specific view.
- **Control**: Adjustable denoising strength and seed control for reproducible results.

### 🎞️ History & Gallery
- **Version Control**: Every generation is saved. Never lose a good result.
- **Visual Gallery**: Browse and restore previous versions instantly.
- **History Bar**: Viewport overlay for quick access to your iterations.

### 🍞 Texture Baking & Preview
- **Live Projection**: Real-time shadeless preview of your generated textures on the model.
- **Seamless Baking**: Blends all views into a final UV map with normal-based masking.

---

## 📦 Installation

1.  **Download** the `texturalia` folder/zip.
2.  Open **Blender 4.2+**.
3.  Go to `Edit` → `Preferences` → `Add-ons`.
4.  Click **Install...** and select the file.
5.  Enable the checkbox for **Texturalia**.

### ComfyUI Setup
1.  Ensure **ComfyUI** is running locally (Default: `http://127.0.0.1:8188`).
2.  In the Texturalia Panel (N-Panel), click **Test Connection** to verify.

---

## 🚀 Workflow

| Step | Action |
| :--- | :--- |
| **1. Rigging** | Select object → Click **Create Rig & Init**. Creates a safe "Work Copy". |
| **2. Capture** | Select a view (e.g., "Front") → Click **Capture** to snapshot the viewport. |
| **3. Enhance** | Enter Prompt & Denoise → Click **Enhance View** to process via AI. |
| **4. Masking** | (Optional) Use **Paint Mask** to define areas for Inpainting/Detailing. |
| **5. Preview** | Click **Enable Live Preview** to see the projection on your model. |
| **6. Bake** | Click **Bake Texture** to generate the final UV map. |
| **7. Finish** | Click **Finish & Clean** to apply the texture to the original mesh. |

---

## 📋 Requirements

*   **Blender**: 4.2.0 or higher
*   **ComfyUI**: Running locally with API enabled
*   **Models**: SDXL or SD1.5 checkpoints (depending on workflow)

### 🧩 ComfyUI Dependencies
To use the included workflows, you need the following installed in your ComfyUI:

| Type | Resource Name | Link |
| :--- | :--- | :--- |
| **Checkpoint** | `dreamshaper_8.safetensors` | [Civitai](https://civitai.com/models/4384/dreamshaper) |
| **ControlNet** | `control_v11f1p_sd15_depth.pth` | [HuggingFace](https://huggingface.co/lllyasviel/ControlNet-v1-1/blob/main/control_v11f1p_sd15_depth.pth) |
| **Node Pack** | `ComfyUI_IPAdapter_plus` | [GitHub](https://github.com/cubiq/ComfyUI_IPAdapter_plus) |
| **Node Pack** | `ComfyUI-Easy-Use-Nodes` | [GitHub](https://github.com/yolain/ComfyUI-Easy-Use-Nodes) |
| **Node Pack** | `ComfyUI-Advanced-ControlNet` | [GitHub](https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet) |

> **Note**: You can install missing nodes easily using the **ComfyUI Manager**.

---

<div align="center">
Developed by <b>Ulises Freitas</b>
</div>
