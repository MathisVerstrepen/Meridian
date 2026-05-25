import base64
import logging
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageFilter, ImageStat
from schemas.images import ImageEditSelectionPayload
from services.files import save_file_to_disk
from services.image_playground.constants import (
    IMAGE_EDIT_DEBUG_RAW_SUBDIRECTORY,
    IMAGE_EDIT_PADDING_PCT,
)

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ImageEditSceneAnalysis:
    lighting_direction: str
    color_temperature: str
    perspective_type: str
    texture_profile: str
    noise_profile: str


@dataclass(frozen=True)
class ImageEditMaskAnalysis:
    margin_pct: float
    min_margin_pct: float
    left_margin_pct: float
    top_margin_pct: float
    right_margin_pct: float
    bottom_margin_pct: float
    is_central: bool


def image_bytes_as_data_uri(image: Image.Image, content_type: str = "image/png") -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{content_type};base64,{encoded_image}"


def normalize_image_edit_selection(
    selection: ImageEditSelectionPayload,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    x1 = min(max(0, selection.x), image_width)
    y1 = min(max(0, selection.y), image_height)
    x2 = min(max(0, selection.x + selection.width), image_width)
    y2 = min(max(0, selection.y + selection.height), image_height)
    if x2 <= x1 or y2 <= y1:
        raise HTTPException(status_code=400, detail="Edit selection is outside the image.")
    return x1, y1, x2, y2


def get_padded_edit_crop(
    image: Image.Image,
    selection: ImageEditSelectionPayload,
    padding_pct: float = IMAGE_EDIT_PADDING_PCT,
) -> tuple[Image.Image, Image.Image, tuple[int, int, int, int], tuple[int, int, int, int]]:
    image_width, image_height = image.size
    selection_box = normalize_image_edit_selection(selection, image_width, image_height)
    x1, y1, x2, y2 = selection_box
    width = x2 - x1
    height = y2 - y1
    pad_x = int(width * padding_pct)
    pad_y = int(height * padding_pct)

    crop_box = (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(image_width, x2 + pad_x),
        min(image_height, y2 + pad_y),
    )
    crop_x1, crop_y1, crop_x2, crop_y2 = crop_box
    cropped_image = image.crop(crop_box)
    cropped_mask = Image.new("L", (crop_x2 - crop_x1, crop_y2 - crop_y1), 0)
    cropped_mask.paste(255, (x1 - crop_x1, y1 - crop_y1, x2 - crop_x1, y2 - crop_y1))
    return cropped_image, cropped_mask, crop_box, selection_box


def mean_luminance(image: Image.Image) -> float:
    return float(ImageStat.Stat(image.convert("L")).mean[0])


def analyze_image_edit_scene(cropped_image: Image.Image) -> ImageEditSceneAnalysis:
    analysis_image = cropped_image.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
    width, height = analysis_image.size
    quadrants = {
        "from upper-left": analysis_image.crop((0, 0, width // 2, height // 2)),
        "from upper-right": analysis_image.crop((width // 2, 0, width, height // 2)),
        "from lower-left": analysis_image.crop((0, height // 2, width // 2, height)),
        "from lower-right": analysis_image.crop((width // 2, height // 2, width, height)),
    }
    lighting_direction = max(quadrants.items(), key=lambda item: mean_luminance(item[1]))[0]

    rgb_stats = ImageStat.Stat(analysis_image)
    red_mean, _green_mean, blue_mean = rgb_stats.mean
    if red_mean > blue_mean * 1.12:
        color_temperature = "warm, approximately 3500K"
    elif blue_mean > red_mean * 1.12:
        color_temperature = "cool, approximately 6500K"
    else:
        color_temperature = "neutral, approximately 5000K"

    luminance_stddev = ImageStat.Stat(analysis_image.convert("L")).stddev[0]
    if luminance_stddev > 55:
        texture_profile = "strong visible texture and high local contrast"
        noise_profile = "visible grain or sensor texture"
    elif luminance_stddev > 30:
        texture_profile = "moderate natural texture detail"
        noise_profile = "fine natural image grain"
    else:
        texture_profile = "smooth low-contrast tonal gradients"
        noise_profile = "low-noise clean image texture"

    return ImageEditSceneAnalysis(
        lighting_direction=lighting_direction,
        color_temperature=color_temperature,
        perspective_type="the natural camera perspective visible in the crop",
        texture_profile=texture_profile,
        noise_profile=noise_profile,
    )


def analyze_image_edit_mask(cropped_mask: Image.Image) -> ImageEditMaskAnalysis:
    mask_bounds = cropped_mask.getbbox()
    if not mask_bounds:
        return ImageEditMaskAnalysis(
            margin_pct=0,
            min_margin_pct=0,
            left_margin_pct=0,
            top_margin_pct=0,
            right_margin_pct=0,
            bottom_margin_pct=0,
            is_central=False,
        )

    crop_width, crop_height = cropped_mask.size
    left, top, right, bottom = mask_bounds
    left_margin_pct = left / max(crop_width, 1)
    top_margin_pct = top / max(crop_height, 1)
    right_margin_pct = (crop_width - right) / max(crop_width, 1)
    bottom_margin_pct = (crop_height - bottom) / max(crop_height, 1)
    edge_margin_pcts = [left_margin_pct, top_margin_pct, right_margin_pct, bottom_margin_pct]
    min_margin_pct = min(edge_margin_pcts)
    margin_pct = sum(edge_margin_pcts) / len(edge_margin_pcts)
    return ImageEditMaskAnalysis(
        margin_pct=margin_pct,
        min_margin_pct=min_margin_pct,
        left_margin_pct=left_margin_pct,
        top_margin_pct=top_margin_pct,
        right_margin_pct=right_margin_pct,
        bottom_margin_pct=bottom_margin_pct,
        is_central=min_margin_pct >= 0.1,
    )


def format_image_edit_mask_margins(mask: ImageEditMaskAnalysis) -> str:
    return (
        f"left {round(mask.left_margin_pct * 100)}%, "
        f"top {round(mask.top_margin_pct * 100)}%, "
        f"right {round(mask.right_margin_pct * 100)}%, "
        f"bottom {round(mask.bottom_margin_pct * 100)}%"
    )


def classify_image_edit_intent(user_prompt: str) -> str:
    prompt = user_prompt.lower()
    if not prompt.strip():
        return "remove"
    if any(keyword in prompt for keyword in ["remove", "erase", "delete", "clean up"]):
        return "remove"
    if any(keyword in prompt for keyword in ["replace", "swap", "change", "turn "]):
        return "replace"
    if any(keyword in prompt for keyword in ["add", "insert", "place", "put "]):
        return "add"
    if any(keyword in prompt for keyword in ["style", "make it look", "color grade"]):
        return "style_transfer"
    return "replace"


def build_image_edit_instruction(user_prompt: str, edit_type: str) -> str:
    edit_prompt = user_prompt.strip()
    if edit_type == "remove":
        subject = edit_prompt or "the selected subject"
        return (
            f"Using this image, remove {subject}. Fill the removed area with content that "
            "seamlessly continues the surrounding background texture, lighting, and perspective. "
            "Do not introduce any new objects or alter any other elements."
        )
    if edit_type == "add":
        subject = edit_prompt or "a natural object matching the scene"
        return (
            f"Using this image, add {subject} inside the selected central region. Place it "
            "naturally within the scene and match the existing scale, perspective, depth of "
            "field, and contact shadows."
        )
    if edit_type == "style_transfer":
        style = edit_prompt or "the requested style"
        return (
            f"Using this image, apply this style only within the selected central region: "
            f"{style}. Preserve all object positions, silhouettes, perspective, and composition."
        )
    subject = edit_prompt or "the selected subject with a natural replacement"
    return (
        f"Using this image, replace or change only the selected subject according to: {subject}. "
        "Keep its position, size, contact shadows, and spatial relationship to surrounding "
        "objects physically consistent."
    )


def build_image_edit_prompt(
    *,
    user_prompt: str,
    model: str,
    cropped_image: Image.Image,
    cropped_mask: Image.Image,
) -> str:
    scene = analyze_image_edit_scene(cropped_image)
    mask = analyze_image_edit_mask(cropped_mask)
    edit_type = classify_image_edit_intent(user_prompt)

    if mask.min_margin_pct >= 0.05:
        boundary_margin = max(5, min(25, round(mask.min_margin_pct * 100)))
        boundary_lock = (
            f"BOUNDARY LOCK: The outermost {boundary_margin}% on all four sides is a locked "
            "no-edit buffer zone. These edge pixels must remain pixel-identical to the input: "
            "do not modify, recolor, relight, sharpen, denoise, blur, or add content there."
        )
    else:
        boundary_lock = (
            "BOUNDARY LOCK: The selected region has asymmetric context margins "
            f"({format_image_edit_mask_margins(mask)}). Preserve every crop edge exactly, and "
            "treat any side with little or no margin as an image boundary that must remain "
            "pixel-identical for stitching back into the larger original image."
        )

    edit_zone = (
        "EDIT ZONE: Modify only the selected central mask region. The backend will composite "
        "only masked pixels back into the source image, so make the edit fit naturally inside "
        "that region without relying on changes outside it. New content should NEVER extend "
        "beyond the masked area."
    )
    blending = (
        "BLENDING REQUIREMENT: The transition at the mask boundary must be seamless, with no "
        "visible seam, halo, rectangular edge, vignette, border, frame, color discontinuity, "
        "or change in texture sharpness."
    )
    lighting = (
        "LIGHTING PHYSICS: Preserve the original lighting direction "
        f"{scene.lighting_direction}, {scene.color_temperature} color temperature, shadow "
        "softness, highlight intensity, and ambient occlusion exactly as they appear."
    )
    perspective = (
        f"PERSPECTIVE: Preserve {scene.perspective_type}. Use existing lines, surface angles, "
        "object scale, and depth cues as perspective references."
    )
    texture = (
        f"TEXTURE AND NOISE: Match the original {scene.texture_profile} and "
        f"{scene.noise_profile}. Grain/noise must be continuous across the edit boundary."
    )
    preservation = (
        "PRESERVATION: Keep everything else exactly the same. Do not alter background, floor, "
        "walls, ceiling, windows, furniture, shadows, reflections, labels, text, or any "
        "unselected objects."
    )

    components = [
        "TASK: Edit only the selected region of this padded crop.",
        "SPATIAL FRAMING: This image is a cropped sub-region from a larger photograph and will "
        "be composited back into the full-resolution original.",
        boundary_lock,
        edit_zone,
        build_image_edit_instruction(user_prompt, edit_type),
        blending,
        lighting,
        perspective,
        texture,
        preservation,
    ]

    return "\n\n".join(components)


def align_edited_crop_to_original_crop(
    original_crop: Image.Image,
    edited_crop: Image.Image,
    cropped_mask: Image.Image,
) -> Image.Image:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        original_cv = cv2.cvtColor(np.array(original_crop.convert("RGB")), cv2.COLOR_RGB2BGR)
        edited_cv = cv2.cvtColor(np.array(edited_crop.convert("RGB")), cv2.COLOR_RGB2BGR)
        original_gray = cv2.cvtColor(original_cv, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        edited_gray = cv2.cvtColor(edited_cv, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        locked_mask = (np.array(cropped_mask) < 16).astype(np.uint8) * 255

        if int(np.count_nonzero(locked_mask)) < max(1024, locked_mask.size // 10):
            return edited_crop

        warp_matrix = np.eye(2, 3, dtype=np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5)
        correlation, aligned_warp_matrix = cv2.findTransformECC(
            original_gray,
            edited_gray,
            warp_matrix,
            cv2.MOTION_TRANSLATION,
            criteria,
            inputMask=locked_mask,
        )
        warp_matrix = np.asarray(aligned_warp_matrix, dtype=np.float32)
        translation_x = float(warp_matrix[0, 2])
        translation_y = float(warp_matrix[1, 2])
        max_translation = min(32.0, max(original_crop.size) * 0.03)
        if (
            float(correlation) < 0.82
            or abs(translation_x) > max_translation
            or abs(translation_y) > max_translation
        ):
            logger.warning(
                "Discarding unreliable image edit alignment shift: %.2f, %.2f (corr %.3f)",
                translation_x,
                translation_y,
                float(correlation),
            )
            return edited_crop

        aligned_cv = cv2.warpAffine(
            edited_cv,
            warp_matrix,
            original_crop.size,
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_REFLECT,
        )
        logger.info(
            "Aligned image edit crop by translation %.2f, %.2f",
            translation_x,
            translation_y,
        )
        return Image.fromarray(cv2.cvtColor(aligned_cv, cv2.COLOR_BGR2RGB))
    except Exception as exc:
        logger.warning("Could not align image edit crop before compositing: %s", exc)
        return edited_crop


def resize_image_to_cover(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    target_width, target_height = target_size
    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        return image.resize(target_size, Image.Resampling.LANCZOS)

    scale = max(target_width / source_width, target_height / source_height)
    resized_size = (
        max(target_width, int(round(source_width * scale))),
        max(target_height, int(round(source_height * scale))),
    )
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def color_transfer_image_edit_crop(
    original_crop: Image.Image,
    edited_crop: Image.Image,
    cropped_mask: Image.Image,
) -> Image.Image:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        original_rgb = np.array(original_crop.convert("RGB"))
        edited_rgb = np.array(edited_crop.convert("RGB"))
        preserved_mask = np.array(cropped_mask.convert("L")) < 128

        if int(np.count_nonzero(preserved_mask)) < 100:
            return edited_crop

        original_lab = cv2.cvtColor(original_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        edited_lab = cv2.cvtColor(edited_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

        for channel in range(3):
            original_values = original_lab[:, :, channel][preserved_mask]
            edited_values = edited_lab[:, :, channel][preserved_mask]
            original_mean = float(original_values.mean())
            original_std = float(original_values.std()) + 1e-6
            edited_mean = float(edited_values.mean())
            edited_std = float(edited_values.std()) + 1e-6
            scale = max(0.5, min(2.0, original_std / edited_std))
            edited_lab[:, :, channel] = (edited_lab[:, :, channel] - edited_mean) * scale
            edited_lab[:, :, channel] += original_mean

        corrected_rgb = cv2.cvtColor(
            np.clip(edited_lab, 0, 255).astype(np.uint8),
            cv2.COLOR_LAB2RGB,
        )
        return Image.fromarray(corrected_rgb)
    except Exception as exc:
        logger.warning("Could not color-match image edit crop before compositing: %s", exc)
        return edited_crop


def image_edit_laplacian_blend(
    original_array: Any,
    edited_array: Any,
    mask_array: Any,
    *,
    levels: int = 6,
) -> Any:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    original_float = original_array.astype(np.float32)
    edited_float = edited_array.astype(np.float32)
    mask_float = mask_array.astype(np.float32) / 255.0
    if mask_float.ndim == 2:
        mask_float = cv2.cvtColor(mask_float, cv2.COLOR_GRAY2RGB)
    mask_float = cv2.GaussianBlur(mask_float, (0, 0), sigmaX=5)

    min_dimension = min(original_array.shape[0], original_array.shape[1])
    effective_levels = 0
    while effective_levels < levels and min_dimension >= 32:
        effective_levels += 1
        min_dimension //= 2

    def gaussian_pyramid(image: Any) -> list[Any]:
        pyramid = [image.copy()]
        current = image
        for _ in range(effective_levels):
            current = cv2.pyrDown(current)
            pyramid.append(current)
        return pyramid

    def laplacian_pyramid(gaussian_levels: list[Any]) -> list[Any]:
        pyramid = []
        for index in range(len(gaussian_levels) - 1):
            size = (gaussian_levels[index].shape[1], gaussian_levels[index].shape[0])
            upsampled = cv2.pyrUp(gaussian_levels[index + 1], dstsize=size)
            pyramid.append(gaussian_levels[index] - upsampled)
        pyramid.append(gaussian_levels[-1])
        return pyramid

    original_laplacian = laplacian_pyramid(gaussian_pyramid(original_float))
    edited_laplacian = laplacian_pyramid(gaussian_pyramid(edited_float))
    mask_gaussian = gaussian_pyramid(mask_float)

    blended_pyramid = []
    for original_level, edited_level, mask_level in zip(
        original_laplacian,
        edited_laplacian,
        mask_gaussian,
    ):
        blended_pyramid.append(edited_level * mask_level + original_level * (1.0 - mask_level))

    result = blended_pyramid[-1]
    for index in range(len(blended_pyramid) - 2, -1, -1):
        size = (blended_pyramid[index].shape[1], blended_pyramid[index].shape[0])
        result = cv2.pyrUp(result, dstsize=size) + blended_pyramid[index]

    return np.clip(result, 0, 255).astype(np.uint8)


def laplacian_composite_image_edit_result(
    original_image: Image.Image,
    edited_crop: Image.Image,
    cropped_mask: Image.Image,
    crop_box: tuple[int, int, int, int],
) -> Image.Image:
    import numpy as np  # type: ignore

    x1, y1, x2, y2 = crop_box
    original_array = np.array(original_image.convert("RGB"))
    edited_array = original_array.copy()
    mask_array = np.zeros((original_image.height, original_image.width), dtype=np.uint8)
    edited_array[y1:y2, x1:x2] = np.array(edited_crop.convert("RGB"))
    mask_array[y1:y2, x1:x2] = np.array(cropped_mask.convert("L"))

    blended = image_edit_laplacian_blend(original_array, edited_array, mask_array)
    return Image.fromarray(blended)


def composite_image_edit_result(
    original_image: Image.Image,
    edited_crop: Image.Image,
    cropped_mask: Image.Image,
    crop_box: tuple[int, int, int, int],
) -> Image.Image:
    x1, y1, x2, y2 = crop_box
    target_size = (x2 - x1, y2 - y1)
    edited_crop = resize_image_to_cover(edited_crop.convert("RGB"), target_size)
    original_crop = original_image.crop(crop_box)
    edited_crop = align_edited_crop_to_original_crop(original_crop, edited_crop, cropped_mask)
    edited_crop = color_transfer_image_edit_crop(original_crop, edited_crop, cropped_mask)

    try:
        return laplacian_composite_image_edit_result(
            original_image.convert("RGB"),
            edited_crop,
            cropped_mask,
            crop_box,
        )
    except Exception as exc:
        logger.warning("Could not Laplacian-blend image edit result: %s", exc)
        softened_mask = cropped_mask.filter(ImageFilter.GaussianBlur(radius=1.5))
        blended_crop = Image.composite(edited_crop, original_crop, softened_mask)
        result = original_image.copy()
        result.paste(blended_crop, (x1, y1))
        return result


def encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def save_debug_raw_edit_image(
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    image_bytes: bytes,
    extension: str,
) -> None:
    try:
        normalized_extension = extension.lstrip(".") or "png"
        filename = f"raw_edit_{job_id}.{normalized_extension}"
        unique_filename = await save_file_to_disk(
            user_id=user_id,
            file_contents=image_bytes,
            original_filename=filename,
            subdirectory=IMAGE_EDIT_DEBUG_RAW_SUBDIRECTORY,
        )
        logger.info(
            "Saved raw image edit provider output to %s/%s",
            IMAGE_EDIT_DEBUG_RAW_SUBDIRECTORY,
            unique_filename,
        )
    except Exception as exc:
        logger.warning("Could not save raw image edit provider output: %s", exc)
