"""Optional Stable Diffusion dependencies are imported only in live mode."""

import base64
import io


def setup_stable_diffusion(settings):
    """Load the entire pipeline before the HTTP server begins listening."""
    try:
        import torch
        from diffusers import BitsAndBytesConfig, SD3Transformer2DModel, StableDiffusion3Pipeline
    except ImportError as exc:
        raise RuntimeError("Install requirements-model.txt before enabling live generation.") from exc

    device = settings.model_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else (
            "mps" if torch.backends.mps.is_available() else "cpu"
        )
    if settings.quantize_4bit and device != "cuda":
        raise RuntimeError(
            "This project's 4-bit mode requires an NVIDIA CUDA GPU. "
            "Use GENERATION_MODE=demo, or set QUANTIZE_4BIT=false for unquantized CPU/MPS."
        )
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("MODEL_DEVICE=cuda but PyTorch cannot see an NVIDIA GPU.")

    dtype = torch.float32
    if device == "cuda":
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    kwargs = {"torch_dtype": dtype, "token": settings.hf_token or None}
    if settings.quantize_4bit:
        quantization = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype
        )
        kwargs["transformer"] = SD3Transformer2DModel.from_pretrained(
            settings.model_id, subfolder="transformer", quantization_config=quantization,
            torch_dtype=dtype, token=settings.hf_token or None,
        )
    pipeline = StableDiffusion3Pipeline.from_pretrained(settings.model_id, **kwargs)
    if device == "cuda" and settings.cpu_offload:
        pipeline.enable_model_cpu_offload()
    else:
        pipeline.to(device)
    pipeline.vae.enable_slicing()
    return pipeline


def generate_image(pipeline, prompt: str, settings, seed: int) -> str:
    """Run outside Tornado's event loop; serialize GPU access in the handler."""
    import torch

    generator = torch.Generator(device="cpu").manual_seed(seed)
    with torch.inference_mode():
        output = pipeline(
            prompt=prompt, num_inference_steps=settings.inference_steps,
            guidance_scale=4.5, height=settings.image_size, width=settings.image_size,
            max_sequence_length=256, generator=generator,
        ).images[0]
    buffer = io.BytesIO()
    output.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
