import os
import io
import json
import openai
import tempfile
from fastapi import FastAPI, File, UploadFile
from google.cloud import vision
from pdf2image import convert_from_path
from tempfile import NamedTemporaryFile

# 🔹 Initialize FastAPI
app = FastAPI()

# 🔹 Set Up Google Cloud Vision API Credentials
GOOGLE_CLOUD_KEY = "C:/Users/Admin/Desktop/Invoice ELIT/googlevision.json"  # Update your path
if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CLOUD_KEY

# 🔹 Initialize OpenAI API
OPENAI_API_KEY = "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"  # Replace with your actual key
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def extract_text_from_image(image_path):
    """Extract text from an image using Google Vision API."""
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

def extract_text_from_pdf(pdf_path):
    """Converts PDF to images and extracts text using Google Vision API."""
    images = convert_from_path(pdf_path, poppler_path=r'poppler-24.08.0\library\bin')
    text = ""

    # Use a temporary directory to store images
    with tempfile.TemporaryDirectory() as temp_dir:
        image_paths = []
        
        for i, image in enumerate(images):
            image_path = os.path.join(temp_dir, f"invoice_page_{i+1}.jpg")
            image.save(image_path, "JPEG")
            image_paths.append(image_path)

        for img_path in image_paths:
            text += extract_text_from_image(img_path) + "\n\n"
            
    # Temporary files are automatically deleted when exiting the `with` block
    return text

def extract_invoice_details(text):
    """Extract structured invoice details using OpenAI."""
    prompt = f"""
    Extract the following details from the invoice text and return JSON:
    - Invoice Number
    - PO Number
    - Supplier Name
    - Total Amount
    - Discount
    - Tax Amount
    - VAT, SGST, CGST, IGST
    - Invoice Amount
    - Line Items (Item Code, Description, UOM, Tax %, Quantity, Price, Line Amount)

    **Invoice Text:**
    {text}

    **JSON Format:**
    {{
      "invHeaderArr": [
        {{
          "invNumber": "<Invoice Number>",
          "poNumber": "<PO Number>",
          "supplierName": "<Supplier Name>",
          "amount": <Total Amount>,
          "discount": <Discount>,
          "taxAmount": <Tax Amount>,
          "vat": <VAT Amount>,
          "sgst": <SGST>,
          "cgst": <CGST>,
          "igst": <IGST>,
          "invAmount": <Invoice Amount>,
          "invLinesArr": [
            {{
              "lineNo": <Line Number>,
              "itemCode": "<Item Code>",
              "description": "<Description>",
              "uom": "<UOM>",
              "taxPercent": <Tax %>,
              "quantity": <Quantity>,
              "unitPrice": <Unit Price>,
              "lineAmount": <Line Amount>
            }}
          ]
        }}
      ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
    
        if response and response.choices:
            return response.choices[0].message.content.strip()
        else:
            return {"error": "OpenAI API returned an empty response"}

    except Exception as e:
        print("OpenAI API Error:", e)
        return {"error": f"OpenAI API Error: {str(e)}"}


@app.post("/extract_invoice")
async def extract_invoice(file: UploadFile = File(...)):
    """API endpoint to process uploaded invoice file."""
    try:
        with NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(file.file.read())
            temp_path = temp_file.name

        extracted_text = extract_text_from_pdf(temp_path) if file.filename.lower().endswith('.pdf') else extract_text_from_image(temp_path)
        os.remove(temp_path)  # Clean up

        if not extracted_text.strip():
            return {"error": "No text extracted from the invoice."}

        invoice_details = extract_invoice_details(extracted_text)
        return {"invoiceData": invoice_details}

    except Exception as e:
        return {"error": str(e)}
