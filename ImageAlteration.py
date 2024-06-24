import os
import piexif
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime

def get_geotagging(exif):
    if 34853 not in exif:
        raise ValueError("No EXIF geotagging found")

    geotagging = exif[34853]
    if 2 not in geotagging or 4 not in geotagging:
        raise ValueError("No latitude or longitude information found in EXIF data")
    return geotagging

def get_date_taken(exif):
    if 306 not in exif:
        raise ValueError("No EXIF date taken found")

    # Get the date from the EXIF data
    date_str = exif[306]

    # Parse the date using strptime
    date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')

    # Format the date as MM/DD/YYYY HH:MM AM/PM
    formatted_date = date_obj.strftime('%m/%d/%Y %I:%M %p')

    return formatted_date

def get_orientation(exif_data):
    """
    Get the orientation value from the EXIF data.
    :param exif_data: Dictionary containing EXIF data
    :return: Orientation value (default to 1 if not found)
    """
    for tag, value in exif_data.items():
        if ExifTags.TAGS.get(tag) == 'Orientation':
            return value
    return 1  # Default orientation value if not found

def rotate_image(exif_data, img):
    """
    Rotate the image based on the orientation value.
    :param exif_data: Dictionary containing EXIF data
    :return: Rotation angle (0, 90, 180, or 270 degrees)
    """
    orientation = get_orientation(exif_data)
    if orientation == 6:
        return img.rotate(270, expand=True)
    return img

def sanitize_exif(exif):
    sanitized = {}
    for tag, value in exif.items():
        try:
            # Check if the value is a bytes object and if all bytes are in range(0, 256)
            if isinstance(value, bytes) and all(b in range(256) for b in value):
                sanitized[tag] = value
        except TypeError:
            # The value is not iterable, skip it
            pass
    return sanitized

def watermark_with_exif(fn):
    img = Image.open(fn)
    exif_data = img._getexif()
        # Resize the image (optional)
    new_width, new_height = 1024, 768  # Specify the new width and height
    img = img.resize((new_width, new_height))
    img = rotate_image(exif_data, img)

    if exif_data is None:
        print(f"No EXIF data found for {fn}, skipping.")
        return None

    try:
        geotagging = get_geotagging(exif_data)
        date_taken = get_date_taken(exif_data)
    except ValueError as e:
        print(f"Error processing {fn}: {e}, skipping.")
        return None

    # Convert the GPS coordinates to decimal format
    lat_deg, lat_min, lat_sec = geotagging[2]
    lon_deg, lon_min, lon_sec = geotagging[4]
    latitude = lat_deg + (lat_min / 60.0) + (lat_sec / 3600.0)
    longitude = lon_deg + (lon_min / 60.0) + (lon_sec / 3600.0)

    # Determine the hemisphere
    lat_hemisphere = 'N' if geotagging[1] == 'N' else 'S'
    lon_hemisphere = 'E' if geotagging[3] == 'E' else 'W'

    # Format the latitude and longitude to have 4 decimal places
    latitude = "{:.4f}".format(latitude)
    longitude = "{:.4f}".format(longitude)

    # Create the watermark text for latitude, longitude, and date
    watermark_text_lat_lon = f"{lat_hemisphere} {latitude}°, {lon_hemisphere} {longitude}°"
    watermark_text_date = f"{date_taken}"

    # Draw the watermark onto the original image
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial", 30)  

    # Position the watermark at the lower left corner for latitude and longitude
    bbox = d.textbbox((0, 0), watermark_text_lat_lon, font=font)
    textwidth, textheight = bbox[2], bbox[3]
    width, height = img.size

    # The x-coordinate should always be 10 pixels from the left
    x = 10  # 10 pixels from the left
    y = height - textheight - 10  # 10 pixels from the bottom


    # Draw black outline for halo effect
    for adj in range(-3, 4):
        d.text((x+adj, y), watermark_text_lat_lon, font=font, fill="black")
        d.text((x, y+adj), watermark_text_lat_lon, font=font, fill="black")

    d.text((x, y), watermark_text_lat_lon, font=font, fill=(50,205,50))  # Use lime green color

    # Position the watermark at the lower right corner for date
    bbox = d.textbbox((0, 0), watermark_text_date, font=font)
    textwidth, textheight = bbox[2], bbox[3]

    # The x-coordinate should always be 10 pixels from the right
    x = width - textwidth - 10  # 10 pixels from the right

    # Draw black outline for halo effect
    for adj in range(-3, 4):
        d.text((x+adj, y), watermark_text_date, font=font, fill="black")
        d.text((x, y+adj), watermark_text_date, font=font, fill="black")

    d.text((x, y), watermark_text_date, font=font, fill=(50,205,50))  # Use lime green color

    # Save the image to a temporary file
    filename, file_extension = os.path.splitext(fn)
    temp_fn = filename + "_temp" + file_extension
    img.save(temp_fn, exif=img.info["exif"])

    # Close the image file
    img.close()

    # Replace the original image with the new image
    os.remove(fn)
    os.rename(temp_fn, fn)  

    return date_taken


def rename_image(fn, date_taken):
    if date_taken is None:
        return

    directory, filename = os.path.split(fn)
    base, ext = os.path.splitext(filename)
    new_folder = f"{date_taken[:2]}{date_taken[3:5]}"
    new_folder_path = os.path.join(directory, new_folder)
    os.makedirs(new_folder_path, exist_ok=True)
    new_name = f"{new_folder}_{base}{ext}"
    new_path = os.path.join(new_folder_path, new_name)
    shutil.move(fn, new_path)


def process_images(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            path = os.path.join(directory, filename)
            date_taken = watermark_with_exif(path)  
            rename_image(path, date_taken)



# Call the function with the path to your directory
process_images(r"C:\\Users\\Alexander.Hutcheson\\OneDrive - Michael Baker International\\Desktop\\Misc\\scratch\\BreakupPhotos\\testImages")
