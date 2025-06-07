import random

from google.adk.agents import Agent, LlmAgent
from google.adk.tools import ToolContext
from ultralytics import YOLO
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import re


def translate_manga(image_path, translations, output_path='translated_manga.png'):
    """
    Complete manga translation pipeline - detects text, whites it out, and typesets translations

    Args:
        image_path: Path to input manga image
        translations: List of translated texts
        output_path: Path where translated image will be saved

    Returns:
        str: Path to the saved translated image
    """
    # Load model and image
    model = YOLO("model/best.pt")
    image = cv2.imread(image_path)

    # Run inference once
    results4 = model(image)
    masks = results4[0].masks
    boxes = results4[0].boxes

    if masks is None or boxes is None:
        # No text detected, save original image
        cv2.imwrite(output_path, image)
        return os.path.abspath(output_path)

    # Extract text regions
    text_regions = []
    for i in range(len(masks.data)):
        mask = masks.data[i].cpu().numpy()
        mask_resized = cv2.resize(mask, (image.shape[1], image.shape[0]))
        binary_mask = (mask_resized > 0.5).astype(np.uint8)

        box = boxes.xyxy[i].cpu().numpy()
        x1, y1, x2, y2 = map(int, box)

        text_regions.append({
            'mask': binary_mask,
            'bbox': (x1, y1, x2, y2),
            'center': ((x1 + x2) // 2, (y1 + y2) // 2)
        })

    # Sort regions by reading order (top to bottom, left to right)
    text_regions.sort(key=lambda r: (r['center'][1], r['center'][0]))

    # Convert to PIL for text rendering
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    # Get font path based on OS
    font_paths = [
        "/System/Library/Fonts/Arial.ttf",  # macOS
        "C:/Windows/Fonts/arial.ttf",  # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux
    ]

    font_path = None
    for path in font_paths:
        if os.path.exists(path):
            font_path = path
            break

    # Process each text region
    for i, region in enumerate(text_regions):
        if i >= len(translations) or not translations[i].strip():
            continue

        # White out original text
        mask = region['mask']
        mask_3ch = np.stack([mask] * 3, axis=-1)
        image_array = np.array(pil_image)
        image_array = np.where(mask_3ch == 1, 255, image_array)
        pil_image = Image.fromarray(image_array)

        # Typeset translation
        _typeset_text(pil_image, translations[i], region['bbox'], font_path)

    # Save final image
    pil_image.save(output_path, quality=95, dpi=(300, 300))
    return os.path.abspath(output_path)


def _typeset_text(image, text, bbox, font_path):
    """Helper function to typeset text in a region by adjusting font size to fit"""
    draw = ImageDraw.Draw(image)
    x1, y1, x2, y2 = bbox
    region_width = x2 - x1
    region_height = y2 - y1
    
    # Add padding to prevent text touching edges
    padding = max(4, min(region_width, region_height) // 20)
    usable_width = region_width - (padding * 2)
    usable_height = region_height - (padding * 2)

    # Find font size that fits the text without word breaking
    font_size = _find_font_size_to_fit(text, usable_width, usable_height, font_path)
    
    # Load font
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    # Wrap text into lines (without breaking words)
    lines = _wrap_text_no_break(text, usable_width, font, draw)

    # Calculate text positioning
    line_height = _get_line_height(font, draw)
    line_spacing = max(1, line_height * 0.1)
    total_height = len(lines) * line_height + (len(lines) - 1) * line_spacing
    
    start_y = y1 + padding + (usable_height - total_height) // 2

    # Draw text with outline
    outline_width = max(1, font_size // 15)

    for j, line in enumerate(lines):
        text_bbox = draw.textbbox((0, 0), line, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x1 + padding + (usable_width - text_width) // 2
        text_y = start_y + j * (line_height + line_spacing)

        # Draw white outline
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((text_x + dx, text_y + dy), line, font=font, fill='white')

        # Draw main text
        draw.text((text_x, text_y), line, font=font, fill='black')


def _find_font_size_to_fit(text, width, height, font_path, min_size=6, max_size=60):
    """Find the largest font size where text fits without breaking words"""
    best_size = min_size
    
    for size in range(max_size, min_size - 1, -1):
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        temp_img = Image.new('RGB', (width, height))
        temp_draw = ImageDraw.Draw(temp_img)

        # Test if text fits without word breaking
        if _text_fits_without_breaking(text, width, height, font, temp_draw):
            best_size = size
            break
    
    return best_size


def _text_fits_without_breaking(text, width, height, font, draw):
    """Check if text fits without breaking any words"""
    lines = _wrap_text_no_break(text, width, font, draw)
    
    if not lines:
        return True
    
    # Check if any line is too wide
    for line in lines:
        line_width = draw.textbbox((0, 0), line, font=font)[2]
        if line_width > width * 0.95:  # 95% to be safe
            return False
    
    # Check total height
    line_height = _get_line_height(font, draw)
    line_spacing = max(1, line_height * 0.1)
    total_height = len(lines) * line_height + (len(lines) - 1) * line_spacing
    
    return total_height <= height * 0.90  # 90% to be safe


def _wrap_text_no_break(text, width, font, draw):
    """Wrap text without breaking words - only at natural word boundaries"""
    if not text.strip():
        return []
    
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        # Test if adding this word would exceed width
        test_line = current_line + [word]
        test_text = ' '.join(test_line)
        text_width = draw.textbbox((0, 0), test_text, font=font)[2]

        if text_width <= width * 0.95:  # Safe margin
            current_line.append(word)
        else:
            # If current line has words, finish it and start new line
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Single word is too long - this will be caught by the fitting check
                # and font size will be reduced
                lines.append(word)

    # Add remaining words
    if current_line:
        lines.append(' '.join(current_line))

    return lines


def _get_line_height(font, draw):
    """Get consistent line height measurement"""
    test_bbox = draw.textbbox((0, 0), "ABCgjpqyQ", font=font)
    return test_bbox[3] - test_bbox[1]



def recreate_manga_panel(current_post: str, tool_context: ToolContext) -> dict:
    """Simulates recreating a cleaned manga panel with translated text."""
    print(f"--- Tool: recreate_manga_panel called with content: {current_post} ---")

    # Here you'd normally call an image rendering or panel redrawing function.
    # For now, just simulate a success.
    
    # First, remove everything before the first numbered bracket (including any JAPANESE: prefix)
    # This handles cases where there might be text between "JAPANESE:" and "[1]"
    text_with_newlines = re.sub(r'^.*?(?:JAPANESE:\s*)?.*?\[\d+\]\s*', '', current_post.strip())
    # Then replace remaining numbered brackets with newlines
    text_with_newlines = re.sub(r'\[\d+\]\s*', '\n', text_with_newlines)
    
    # Split on multiple newlines (original logic)
    paragraphs = re.split(r'\n\s*\n+', text_with_newlines.strip())

    # Remove inner newlines and strip extra whitespace
    cleaned = [' '.join(p.strip().splitlines()) for p in paragraphs if p.strip()]
    with open('manga_links.txt', 'r', encoding='utf-8') as file:
        lines = file.readlines()
        last_line = lines[-1].strip() if lines else ''

    # Remove extra spaces and keep non-empty entries
    cleaned = [para.strip() for para in paragraphs if para.strip()]
    random_number = random.randint(0, 99999)
    base_name = "translated_manga"
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)  # Ensure the directory exists

    new_filename = os.path.join(output_dir, f"{base_name}_{random_number}.png")
    output_file = translate_manga(last_line, cleaned,new_filename)
    try:
        with open("currentpost.txt", "a") as file:
            file.write(current_post + "\n")
    except Exception as e:
        print(f"Error writing link to file: {e}")
    try:

        recreated_image_path = "output/translated_manga.png"  # Placeholder

        # You might want to store or track this in tool context
        tool_context.state["last_recreated_panel"] = recreated_image_path

        return {
            "status": "success",
            "message": f"Manga panel recreated successfully at {recreated_image_path}",
            "image_path": new_filename
        }

    except Exception as e:
        print(f"Error in recreate_manga_panel: {e}")
        return {
            "status": "error",
            "message": f"Failed to recreate manga panel: {e}"
        }
def show_image(image_path: str, tool_context: ToolContext) -> dict:
    """
    Opens the image using the default image viewer (locally).
    Intended for local preview of rendered manga panels.
    """
    print(f"--- Tool: show_image called with image_path: {image_path} ---")

    try:
        if not os.path.exists(image_path):
            return {
                "status": "error",
                "message": f"Image not found at: {image_path}"
            }

        # Open the image using PIL for local viewing
        img = Image.open(image_path)
        img.show()

        # Optionally store in context
        tool_context.state["last_displayed_image"] = image_path

        return {
            "status": "success",
            "message": f"Image displayed successfully: {image_path}",
            "image_path": image_path,

        }

    except Exception as e:
        print(f"Error in show_image: {e}")
        return {
            "status": "error",
            "message": f"Failed to display image: {e}"
        }
proof_reader = LlmAgent(
    name="proof_reader",
    model="gemini-2.0-flash",
    description="An agent that recreates cleaned manga panels by rendering English-translated text onto the original image using the provided content.",
    instruction="""
You are a manga rendering agent.

1. First, use the recreate_manga_panel tool to render the manga panel.
### OUTPUT
- Respond only with: `Manga panel successfully recreated.`
- image_path:<IMAGE_PATH>
- status:<Status>
After Output:
immediately call the show_image tool using the image_path returned from recreate_manga_panel.
    """,
    tools=[recreate_manga_panel,show_image],
    output_key="current_post",
)
