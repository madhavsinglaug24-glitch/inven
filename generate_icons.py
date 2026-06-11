import os
from PIL import Image, ImageDraw, ImageFont

def create_icon(size, filename):
    # Teal color #0D9488
    img = Image.new('RGB', (size, size), color=(13, 148, 136))
    d = ImageDraw.Draw(img)
    
    # Just draw SDE text
    try:
        # Try to use a standard font if available, else default
        font = ImageFont.truetype("arial.ttf", int(size * 0.4))
    except:
        font = ImageFont.load_default()
        
    text = "SDE"
    
    # Calculate text size using getbbox
    try:
        bbox = d.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # Fallback for older PIL versions
        text_width, text_height = d.textsize(text, font=font)
        
    # Draw text in the center
    d.text(((size - text_width) / 2, (size - text_height) / 2), text, fill=(255, 255, 255), font=font)
    
    img.save(filename)
    print(f"Generated {filename}")

os.makedirs('frontend/public', exist_ok=True)
create_icon(192, 'frontend/public/pwa-192x192.png')
create_icon(512, 'frontend/public/pwa-512x512.png')
create_icon(180, 'frontend/public/apple-touch-icon.png')
