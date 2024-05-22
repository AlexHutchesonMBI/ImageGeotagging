import os
from PIL import Image, ImageDraw, ImageFont, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
from datetime import datetime
import shutil

def get_geotagging(exif):
    if not exif or 34853 not in exif:
        raise ValueError("No EXIF geotagging found")

    geotagging = exif[34853]
    for (idx, tag) in TAGS.items():
        if tag == 'GPSInfo':
            if idx not in exif:
                raise ValueError("No EXIF geotagging found")

            for (tidx, ttag) in GPSTAGS.items():
                if tidx in exif[idx]:
                    geotagging[ttag] = exif[idx][tidx]

    if 'GPSLatitude' not in geotagging or 'GPSLongitude' not in geotagging:
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
        return fn

    directory, filename = os.path.split(fn)
    base, ext = os.path.splitext(filename)
    folder_name = os.path.basename(directory)
    new_name = f"{date_taken[:2]}{date_taken[3:5]}_{folder_name}_{base}{ext}"
    new_path = os.path.join(directory, new_name)
    shutil.move(fn, new_path)

    return new_path  # Return the new path

def move_image(fn, date_taken, root_directory):
    if date_taken is None:
        return

    directory, filename = os.path.split(fn)
    base, ext = os.path.splitext(filename)
    new_folder = f"{date_taken[:2]}{date_taken[3:5]}"
    new_folder_path = os.path.join(root_directory, new_folder)
    os.makedirs(new_folder_path, exist_ok=True)
    new_path = os.path.join(new_folder_path, filename)
    shutil.move(fn, new_path)


def get_decimal_from_dms(dms, ref):
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0

    if ref in ['S', 'W']:
        degrees = -degrees
        minutes = -minutes
        seconds = -seconds

    return round(degrees + minutes + seconds, 5)

def get_coordinates(geotags):
    lat = get_decimal_from_dms(geotags['GPSLatitude'], geotags['GPSLatitudeRef'])
    lon = get_decimal_from_dms(geotags['GPSLongitude'], geotags['GPSLongitudeRef'])

    return (lat,lon)

def process_images(directory):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
                path = os.path.join(root, filename)
                date_taken = watermark_with_exif(path)
                path = rename_image(path, date_taken)  # Update the path after renaming
                move_image(path, date_taken, directory)  # Then move the image

    # After processing all images, call the function from script 2 for each subdirectory
    for subdirectory in os.listdir(directory):
        subdirectory_path = os.path.join(directory, subdirectory)
        if os.path.isdir(subdirectory_path):
            create_kml(subdirectory_path)



def create_kml(folder_path):
    kml_doc = KML.kml(KML.Document())  # Create a Document element inside the KML root element

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".jpg") or filename.lower().endswith(".png"):
            image_path = os.path.join(folder_path, filename)
            image_path = os.path.normpath(image_path)  # Normalize the path to use the correct platform-specific separator
            image_path = image_path.replace("\\", "/")  # Replace backslashes with forward slashes
            image = Image.open(image_path)
            exif = image._getexif()
            try:
                geotags = get_geotagging(exif)
                coordinates = get_coordinates(geotags)
                placemark = KML.Placemark(
                    KML.name(filename),
                    KML.LookAt(
                        KML.longitude(coordinates[1]),
                        KML.latitude(coordinates[0]),
                        KML.range(1000),  # Adjust this value to change the initial zoom level
                        KML.tilt(0),
                        KML.heading(0),
                    ),
                    KML.Point(
                        KML.coordinates(f"{coordinates[1]},{coordinates[0]}")
                    ),
                    KML.description(
                        '<img style="max-width:500px;" src="file:///{}">'.format(image_path)
                    )
                )
                kml_doc.Document.append(placemark)
            except ValueError as e:
                print(f"Skipping {filename}: {e}")

    kml_str = etree.tostring(kml_doc, pretty_print=True).decode()

    # Get the folder name and create the KML file name
    folder_name = os.path.basename(folder_path)
    kml_file_name = f"{folder_name}_locations.kml"
    kml_file_path = os.path.join(folder_path, kml_file_name)

    with open(kml_file_path, "w") as f:
        f.write(kml_str)

    print(f"KML file has been written to {kml_file_path}")

 
# Call the function with the path to your directory
process_images(r"C:\\Users\\Alexander.Hutcheson\\OneDrive - Michael Baker International\\Desktop\\Misc\\scratch\\BreakupPhotos")
