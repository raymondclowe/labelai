import os
import json
import logging
import tempfile
from flask import Flask, request, jsonify
import google.generativeai as genai
from werkzeug.utils import secure_filename
from PIL import Image
import io
import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import math

# Initialize Flask
app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MODEL_NAME = os.environ.get('MODEL_NAME', "gemini-2.0-flash-exp")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Configure Gemini AI
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
            "response_mime_type": "text/plain",
        },
    )
    logging.info(f"Gemini AI model '{MODEL_NAME}' initialized successfully.")
except KeyError:
    logging.error("Error: GEMINI_API_KEY environment variable not set.")
    exit()
except Exception as e:
    logging.error(f"Error initializing Gemini AI: {e}")
    exit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_gemini(path, mime_type=None):
    """Uploads the given file to Gemini."""
    try:
        file = genai.upload_file(path, mime_type=mime_type)
        logging.info(f"Uploaded file '{file.display_name}' as: {file.uri}")
        return file
    except Exception as e:
        logging.error(f"Error uploading to Gemini: {e}")
        return None

def get_address_from_gps(latitude, longitude):
    """Uses geopy to reverse geolocate coordinates into an address."""
    if not (isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))):
        logging.warning(f"Invalid GPS coordinates: latitude={latitude}, longitude={longitude}")
        return None

    geolocator = Nominatim(user_agent="price_label_app")
    try:
        location = geolocator.reverse(f"{latitude}, {longitude}", exactly_one=True, timeout=5)
        if location:
            return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
      logging.error(f"Error during reverse geocoding: {e}")
      return None
    except Exception as e:
      logging.exception(f"Unexpected error during reverse geocoding: {e}")
      return None
    return None

def find_center_label(image, debug_save_images=False):
    """Finds and crops the label nearest to the center of the image."""
    try:
        width, height = image.size
        # Placeholder logic: Assume the entire image is the label, but convert to PNG and save a cropped version

        # Find center of image
        center_x, center_y = width / 2, height / 2

        # Crop a square around the center 
        crop_size = min(width, height) * 0.8 # Lets say 80%
        left = center_x - crop_size / 2
        top = center_y - crop_size / 2
        right = center_x + crop_size / 2
        bottom = center_y + crop_size / 2

        # Ensure crop window is within bounds
        left = max(0, int(left))
        top = max(0, int(top))
        right = min(width, int(right))
        bottom = min(height, int(bottom))


        cropped_image = image.crop((left, top, right, bottom))
        
        if cropped_image.format != "PNG":
            # If the image is not already png, convert it
           cropped_image = cropped_image.convert('RGB')
           temp_buffer = io.BytesIO()
           cropped_image.save(temp_buffer, format='PNG')
           temp_buffer.seek(0)
           cropped_image = Image.open(temp_buffer)


        if debug_save_images:
            debug_path = os.path.join(app.config['UPLOAD_FOLDER'], "debug_cropped_image.png")
            cropped_image.save(debug_path)
            logging.info(f"Saved debug image: {debug_path}")

        return cropped_image

    except Exception as e:
        logging.exception(f"Error processing the image: {e}")
        return None


def create_prompt(image_part, shop_name=None, gps_coords=None, date_time=None, hint_text=None):
    """Generates the prompt for Gemini."""

    prompt_parts = [image_part]
    text_parts = ["Analyze the image for supermarket price label details. Return a JSON object with these fields:"]
    fields = {
        "product_name": "The name of the product (string).",
        "price": "The price of the item (string).",
        "unit": "The unit of measure (e.g., kg, lb, each) if available (string).",
        "sale_price": "If it exists a sale price for the item (string).",
        "original_price": "If it exists a regular price for the item (string).",
        "currency": "The currency, such as '$' or '£' (string).",
        "valid_until": "An expiration date if available (string, format YYYY-MM-DD, can be null).",
        "barcode": "The product barcode if available (string, or null if not present).",
        "weight": "If the item is sold by weight the weight value (string, such as '100g')."
    }

    for field_name, field_desc in fields.items():
        text_parts.append(f" - `{field_name}`: {field_desc}")

    text_parts.append("\nAdditional context:")
    if shop_name:
        text_parts.append(f"- The shop name is '{shop_name}'.")
    if gps_coords:
        latitude, longitude = gps_coords
        address = get_address_from_gps(latitude, longitude)
        if address:
            text_parts.append(f"- Location is at approximately '{address}'.")
        text_parts.append(f"- GPS coordinates are Latitude: {latitude}, Longitude: {longitude}.")
    if date_time:
      try:
        parsed_date = datetime.datetime.fromisoformat(date_time)
        text_parts.append(f"- Date and time is '{parsed_date.strftime('%Y-%m-%d %H:%M:%S')}'.")
      except ValueError:
          text_parts.append(f"- The user has provided a date and time, but it was not valid {date_time}.")
    if hint_text:
        text_parts.append(f"- The following hint information was given: '{hint_text}'.")


    text_parts.append("\nIf some fields are not present or cannot be determined, use `null` for their value instead of leaving them out. If you are unsure of a value, still make your best guess.")
    text_parts.append("\nLook out for discounts and deals, typically there may be a full price such as 10 in large digits sometimes crossed out, then a deal price such as 15.90/2 meaning $15.90 for 2, so the unit price is 7.95. Return fields showing the discount is true, the total price, and the discount terms, in this case 'buy 2'.")
    text_parts.append("\nReturn only the JSON.")

    prompt_parts.append(" ".join(text_parts))

    return prompt_parts

def process_image_file(image_file, debug_save_images=False):
    """Processes the image, returning a Gemini image part or None"""
    try:
      filename = secure_filename(image_file.filename)
      file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
      image_file.save(file_path)
      logging.info(f"Image saved to {file_path}")

      img = Image.open(file_path)
      centered_image = find_center_label(img, debug_save_images=debug_save_images)
      if centered_image is None:
          return None

      with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        temp_path = tmp_file.name
        centered_image.save(temp_path) # Save as png format
        gemini_image_part = upload_to_gemini(temp_path, mime_type="image/png")
        logging.info(f"Image uploaded to Gemini from {temp_path}")

      return gemini_image_part, file_path, temp_path # Return the paths so we can clean up

    except Exception as e:
      logging.exception(f"Error during image processing: {e}")
      return None, None, None

def send_to_gemini(prompt_parts):
    """Sends the prompt to Gemini and returns the response text."""
    try:
        chat_session = model.start_chat(history=[{"role": "user", "parts": prompt_parts}])
        response = chat_session.send_message("Do it now.")
        if response is None:
          logging.error(f"Got a null response from gemini")
          return None
        return response.text

    except Exception as e:
        logging.exception(f"Error sending request to Gemini: {e}")
        return None


@app.route('/process_label', methods=['POST'])
def process_label():
    """Endpoint to process supermarket price labels."""
    if 'image' not in request.files:
        logging.error("No image file provided in the request.")
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        logging.error("No filename provided in the request.")
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(image_file.filename):
        logging.error(f"Invalid file type '{image_file.filename}'")
        return jsonify({"error": "Invalid file type, allowed types are: " + ", ".join(ALLOWED_EXTENSIONS)}), 400


    debug_save_images = request.form.get('debug', type=bool, default=False)

    # Process the image
    gemini_image_part, file_path, temp_path = process_image_file(image_file, debug_save_images=debug_save_images)
    if gemini_image_part is None:
      return jsonify({"error": "Error processing the image"}), 500

    # Extract optional fields (use get to avoid KeyErrors)
    shop_name = request.form.get('shop_name')
    latitude = request.form.get('latitude', type=float)
    longitude = request.form.get('longitude', type=float)
    gps_coords = (latitude, longitude) if latitude is not None and longitude is not None else None
    date_time = request.form.get('date_time')
    hint_text = request.form.get('hint_text')

    # Create the prompt
    prompt_parts = create_prompt(gemini_image_part, shop_name, gps_coords, date_time, hint_text)

    print(prompt_parts)

    # Get the response from Gemini
    response_text = send_to_gemini(prompt_parts)

    if response_text is None:
      return jsonify({"error": "Failed to get a response from the AI"}), 500

    # Attempt to return the response as json, if this fails just return the string
    try:
        json_response = json.loads(response_text)
        response_data = json_response
    except Exception as e:
        response_data = {"ai_response": response_text} # Send the text as the response instead
        logging.warning(f"Could not parse AI response as JSON, sending response as text, exception {e}")
    finally:
      # Clean up the temporary files
      if os.path.exists(temp_path):
        os.remove(temp_path)
      if os.path.exists(file_path):
        os.remove(file_path)
      return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(debug=True)