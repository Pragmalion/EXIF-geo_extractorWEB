import base64
from datetime import datetime
import io
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

GPS_INFO_TAG_ID = 34853
THUMBNAIL_SIZE = (150, 150)


def get_all_exif_data(image):
    """
    Извлекает все EXIF-теги из изображения и делает их читаемыми.
    """
    exif_data = image.getexif()
    if not exif_data:
        return None

    all_tags = {}
    for tag_id, value in exif_data.items():
        # Пропускаем указатель на GPS-блок, т.к. мы его обработаем отдельно
        if tag_id == GPS_INFO_TAG_ID:
            continue

        tag_name = TAGS.get(tag_id, tag_id)

        # Декодируем байтовые строки для чистого вывода
        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8', errors='ignore').strip('\x00')
            except Exception:
                pass  # Оставляем как есть, если декодирование не удалось

        # Преобразуем числовые коды в понятные строки (например, для ResolutionUnit)
        if tag_name == 'ResolutionUnit' and value == 2: value = 'Дюймы'
        if tag_name == 'ResolutionUnit' and value == 3: value = 'Сантиметры'

        all_tags[str(tag_name)] = str(value)

    return all_tags


def get_gps_ifd(image):
    exif_data = image.getexif()
    if not exif_data: return None
    gps_ifd = exif_data.get_ifd(GPS_INFO_TAG_ID)
    if not gps_ifd: return None
    decoded_gps_data = {}
    for key, val in gps_ifd.items():
        tag_name = GPSTAGS.get(key, key)
        decoded_gps_data[tag_name] = val
    return decoded_gps_data


def dms_to_decimal(dms, ref):
    try:
        degrees, minutes, seconds = float(dms[0]), float(dms[1]) / 60.0, float(dms[2]) / 3600.0
        if ref in ['S', 'W']: return -(degrees + minutes + seconds)
        return degrees + minutes + seconds
    except (ValueError, TypeError, IndexError, ZeroDivisionError):
        return None


def get_coordinates(gps_data):
    if not gps_data: return None, None
    try:
        lat_dms, lat_ref = gps_data['GPSLatitude'], gps_data['GPSLatitudeRef']
        lon_dms, lon_ref = gps_data['GPSLongitude'], gps_data['GPSLongitudeRef']
        latitude, longitude = dms_to_decimal(lat_dms, lat_ref), dms_to_decimal(lon_dms, lon_ref)
        if latitude is None or longitude is None: return None, None
        return latitude, longitude
    except KeyError:
        return None


def create_thumbnail_data_uri(image):
    image.thumbnail(THUMBNAIL_SIZE)
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_str}"


def process_image(image_path):
    """
    Полный цикл обработки: возвращает словарь со всеми данными, включая DateTimeOriginal.
    """
    try:
        image = Image.open(image_path)
        image_copy = image.copy()  # Работаем с копией, чтобы не изменять оригинал

        all_exif = get_all_exif_data(image_copy)
        gps_data = get_gps_ifd(image_copy)
        coordinates = get_coordinates(gps_data)
        thumbnail_uri = create_thumbnail_data_uri(image_copy)

        datetime_original_obj = None
        if all_exif and 'DateTimeOriginal' in all_exif:
            # Формат DateTimeOriginal часто "YYYY:MM:DD HH:MM:SS"
            # Для strptime нужно "YYYY-MM-DD HH:MM:SS"
            dt_str = all_exif['DateTimeOriginal'].replace(':', '-', 2)
            try:
                datetime_original_obj = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass  # Не удалось распарсить дату

        result = {
            "all_exif": all_exif,
            "coordinates": coordinates,
            "thumbnail_uri": thumbnail_uri,
            "datetime_original": datetime_original_obj  # Дата и время
        }

        return result

    except Exception as e:
        print(f"Error processing image: {e}")  # Для отладки
        return None