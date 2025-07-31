import csv
import random
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Function to load products from CSV
def load_products():
    products_data = []
    try:
        # Use 'utf-8-sig' to handle BOM (Byte Order Mark)
        with open('products.csv', 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            # Clean up fieldnames to remove any hidden characters like BOM
            reader.fieldnames = [field.strip() for field in reader.fieldnames]
            print("CSV Headers (cleaned):", reader.fieldnames)
            for i, row in enumerate(reader):
                # Clean up keys in each row as well, just in case
                cleaned_row = {key.strip(): value for key, value in row.items()}
                products_data.append(cleaned_row)
                if i == 0: # Print first row keys to debug
                    print("First product keys (cleaned):", cleaned_row.keys())
    except FileNotFoundError:
        print("products.csv not found. Please ensure it's in the root directory.")
    return products_data

all_products = load_products()

@router.get("/", response_class=HTMLResponse)
async def jjim_list(request: Request):
    # Select 4 random products for the jjim list
    if len(all_products) >= 4:
        random_jjim_products = random.sample(all_products, 4)
    else:
        random_jjim_products = all_products # If less than 4, show all available

    return templates.TemplateResponse("jjim/jjim.html", {"request": request, "jjim_products": random_jjim_products})

@router.get("/compare/{product_names}", response_class=HTMLResponse)
async def compare_products(request: Request, product_names: str):
    import urllib.parse # Add this import
    decoded_product_names = urllib.parse.unquote(product_names) # Decode URL
    print(f"Received product_names (encoded): {product_names}")
    print(f"Decoded product_names: {decoded_product_names}")
    selected_names = [name.strip() for name in decoded_product_names.split(',')]
    print(f"Selected names after split: {selected_names}")
    products_to_compare = []

    for name in selected_names:
        found_product = next((p for p in all_products if p['상품명'] == name), None)
        if found_product:
            products_to_compare.append(found_product)
            print(f"Found product: {name}")
        else:
            print(f"Product not found in all_products: {name}")

    if not products_to_compare:
        print("No products found for comparison. Raising 404.")
        raise HTTPException(status_code=404, detail="Products not found for comparison")

    return templates.TemplateResponse("jjim/compare.html", {"request": request, "products": products_to_compare})