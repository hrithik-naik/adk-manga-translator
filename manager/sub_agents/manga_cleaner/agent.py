from datetime import datetime
import os
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from ultralytics import YOLO
import cv2
import numpy as np
import google.generativeai as genai
import random
from dotenv import load_dotenv
from pathlib import Path
import os
import requests
from urllib.parse import urlparse
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
models = genai.GenerativeModel('gemini-1.5-flash')
def ensure_local_image(image_path: str) -> str:
    """
    If image_path is a URL, downloads the image to `OnlineDownloads/` and returns the local path.
    If it's already a local path, returns it unchanged.
    """
    if image_path.startswith("http://") or image_path.startswith("https://"):
        os.makedirs("OnlineDownloads", exist_ok=True)
        parsed_url = urlparse(image_path)
        filename = os.path.basename(parsed_url.path)

        # Ensure a unique filename to avoid clashes
        local_path = Path("OnlineDownloads") / f"downloaded_{random.randint(1000, 99999)}_{filename}"

        try:
            response = requests.get(image_path, timeout=10)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                f.write(response.content)

            print(f"Image downloaded to: {local_path}")
            return str(local_path)

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download image: {e}")

    # Already a local file
    return image_path

def process(data: dict) -> dict:
    if "image_path" not in data:
        raise ValueError("Input data must contain 'image_path'.")
    image_path = data["image_path"]
    image_path = ensure_local_image(image_path)

    model = YOLO("model/best.pt")
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image at path: {image_path}")

    # Run inference
    results1 = model(image)

    # Get mask data
    masks = results1[0].masks
    prediction_count = 0
    if masks is not None:
        prediction_count = len(masks.data)

    print(f"OCRAgent: Processing data: {data}")

    try:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            print("OCRAgent: Image data read successfully. Sending request to Gemini for OCR.")

        # Guess MIME type based on file extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/png" if ext == ".png" else "image/jpeg"

        response = models.generate_content([
            f"""
  You are an OCR agent tasked with extracting exactly {prediction_count} readable Japanese text regions from this manga panel image.

Guidelines:
- Extract each text region separately without merging small regions.
- If a region contains long text, split it into smaller regions as needed.
- Preserve the original reading order: top to bottom, left to right.
- Return exactly {prediction_count} numbered sections.

Format your output strictly as:

```
[1]
<first text region>

[2]
<second text region>

...

[{prediction_count}]
<last text region>
```

⚠️ Make sure there are exactly {prediction_count} numbered sections.

This will be used for precise translation and typesetting, so keep the text clean, accurate, and separated properly.
            """,
            {"mime_type": mime_type, "data": image_data}
        ])

        extracted_text = response.text
        print(f"OCRAgent: Gemini OCR response received. Extracted text: '{extracted_text}'")
        return {"extracted_text": extracted_text, "image_path": image_path}

    except Exception as e:
        print(f"OCRAgent: Error occurred - {e}")
        return {"error": f"OCR failed: {e}", "image_path": image_path}

def whitening(image_path):
    model = YOLO("model/best.pt")
    image_path = ensure_local_image(image_path)
    image = cv2.imread(image_path)

    # Run inference
    results2 = model(image)
    output_image = image.copy()

    # Get mask data
    masks = results2[0].masks
    prediction_count = 0

    if masks is not None:
        prediction_count = len(masks.data)
        for i in range(prediction_count):
            mask = masks.data[i].cpu().numpy()
            mask_resized = cv2.resize(mask, (image.shape[1], image.shape[0]))
            binary_mask = (mask_resized > 0.5).astype(np.uint8) * 255
            mask_3ch = cv2.merge([binary_mask] * 3)
            output_image = np.where(mask_3ch == 255, 255, output_image)
    random_number = random.randint(0, 99999)
    base_name = "whitening"
    new_filename = f"whitener/{base_name}_{random_number}.png"
    cv2.imwrite(new_filename, output_image)
    # Save the output image
    return prediction_count

def get_nerd_joke(link: str, tool_context: ToolContext) -> dict:
    """Process the manga and return number of predictions as a nerdy joke."""
    print(f"--- Tool: get_nerd_joke called for link: {link} ---")
    link=ensure_local_image(link)
    # Save link to local file
    try:
        with open("manga_links.txt", "a") as file:
            file.write(link + "\n")
    except Exception as e:
        print(f"Error writing link to file: {e}")
    results3 = {"extracted_text": ""}  # Initialize to avoid reference before assignment

    try:
        prediction_count = whitening(link)
        results3 = process({"image_path": link})
        joke = f"I found {prediction_count} regions in this manga panel. Looks like a lot of cleaning to do!"
    except Exception as e:
        print(f"Error during whitening: {e}")
        joke = "Oops! Something went wrong while analyzing the image."

    tool_context.state["last_joke_topic"] = "manga"

    return {"status": "success", "joke": joke, "link": results3["extracted_text"]}




# Create the funny nerd agent
manga_cleaner = Agent(
    name="manga_cleaner",
    model="gemini-2.0-flash",
    description="A manga that clears the manga using the tools ",
    instruction="""
    You are a Manga cleaner agent that gets the link and cleans the manga panels.
    when asked to clean a manga:
    1.Use the get_nerd_joke tool to fetch a joke about the requested link which is in format manga link :
     Example response format:
    "Output format:
    Predictions:<JOKE>
    JAPANESE:
    <LINK>
    """,
    tools=[get_nerd_joke],
    output_key="current_post",
)
