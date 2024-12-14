# Supermarket Price Label AI Processor

This Flask application provides an API endpoint for processing images of supermarket price labels using Google's Gemini AI model. It takes an image, extracts the price label details, and returns a JSON object containing structured information.

## Features

*   **Image Upload:** Accepts images of price labels via POST requests.
*   **AI-Powered Analysis:** Uses Google Gemini AI to extract key information from the label image.
*   **Structured Output:** Returns the extracted details in JSON format.
*   **Optional Context:** Accepts optional parameters like shop name, GPS coordinates, date/time, and hint text to improve AI accuracy.
*   **Markdown Removal:** Handles JSON responses wrapped in markdown code blocks.
*   **Image Downscaling:** Downscales large images before sending to the AI for faster processing.
*   **Logging:** Uses logging for error handling and debugging.
*   **Flexible Configuration:** Allows model name, upload folder to be configured via environment variables.
*  **Basic Image Cropping** Crops a square from the center of the image and converts to PNG.

## Setup

### Prerequisites

*   Python 3.7+
*   `pip` (Python package installer)
*   Google Gemini API Key

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/<your-username>/<your-repo-name>.git
    cd <your-repo-name>
    ```
2.  Create a virtual environment (recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
4.  Create a `.env` file in the root directory with your Gemini API key:
    ```
    GEMINI_API_KEY=your_api_key_here
    UPLOAD_FOLDER=my_uploads # Optional folder to override the default 'uploads'
    MODEL_NAME=gemini-pro-exp #Optional model to use
    ```
    * `GEMINI_API_KEY` is required.
    * `UPLOAD_FOLDER` is optional and defaults to `uploads`.
    * `MODEL_NAME` is optional, and if not specified, defaults to `gemini-2.0-flash-exp`.

### Running the Application

1.  Ensure that your virtual environment is active.
2.  Run the Flask application:

    ```bash
    flask --app app.py run
    ```
    The application will start on `http://127.0.0.1:5000/`.

## API Endpoint

### `POST /process_label`

#### Request Body

The request body should be `multipart/form-data` and should include:

*   `image`: The image file of the price label. (Required)
*   `shop_name`: (Optional) The name of the shop.
*   `latitude`: (Optional) Latitude of the shop location (float).
*   `longitude`: (Optional) Longitude of the shop location (float).
*   `date_time`: (Optional) Date and time when the image was taken (ISO format).
*   `hint_text`: (Optional) Any prior information about the label (e.g., "This is for 2 cans of soup").
*   `debug`: (Optional) Set to `true` to save a cropped version of the image to disk. (Defaults to `false`)

#### Response

The response is a JSON object containing the following fields:

*   `product_name`: The name of the product (string, null if not available).
*   `price`: The price of the item (string, null if not available).
*   `unit`: The unit of measure (e.g., kg, lb, each) if available (string, null if not available).
*   `regular_price`: If the item has a discount, the price before the discount (string, null if not available).
*   `discount`: A bool showing if the item has a discount or offer
*  `discount_description`:  If it has a discount, a description of it such as "Buy 2", "Half price" etc
*   `discount_calculation`: A string showing how to calculate the discounted price, such as (11.90/3) or 15.90/2
*   `weight`: If the item is sold by weight, the weight value (string, null if not available).
*   `ai_response`: If the response can not be parsed as JSON, the response from the AI will be returned here in plain text.
*   `error` (If there is an error, this field will be populated)

#### Example Request (using `curl`)
Basic example with image only:

```bash
curl -X POST \
  -F "image=@price_label.jpg" \
  http://127.0.0.1:5000/process_label
```

Comprehensive example with optional fields:

```bash
curl -X POST \
  -F "image=@price_label.jpg" \
  -F "shop_name=SuperMart" \
  -F "latitude=34.0522" \
  -F "longitude=-118.2437" \
  -F "date_time=2024-10-27T14:30:00" \
  -F "hint_text=This is a label for a 12 pack of eggs" \
  -F "debug=true" \
  http://127.0.0.1:5000/process_label
```

## File Structure

```
.
├── app.py          # Main Flask application
├── requirements.txt # Python dependencies
├── README.md       # This file
├── uploads         # Default folder for uploaded images
└── venv            # Virtual environment directory (not required to be tracked in source)

```

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request.

