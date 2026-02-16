import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import exif_utils
import folium

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files: return render_template('index.html', message='Файл не был отправлен.')
        file = request.files['file']
        if file.filename == '': return render_template('index.html', message='Файл не выбран.')

        if not allowed_file(file.filename):
            return render_template('index.html', message='Ошибка: Поддерживаются только файлы форматов .jpg и .jpeg.')

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        result = exif_utils.process_image(filepath)
        os.remove(filepath)

        if result:
            coordinates = result.get("coordinates")
            all_exif = result.get("all_exif")
            thumbnail_uri = result.get("thumbnail_uri")
            map_html = None
            message = None

            if not all_exif:
                message = "Данные не найдены."

            # Создаем карту, только если есть валидные координаты
            if coordinates and coordinates[0] is not None and coordinates[1] is not None:
                m = folium.Map(location=coordinates, zoom_start=15)
                html = f"""<div style="text-align: center;"><img src="{thumbnail_uri}" style="width:100%;"><br><br>Ш: {round(coordinates[0], 5)}<br>Д: {round(coordinates[1], 5)}</div>"""
                iframe = folium.IFrame(html, width=180, height=230)
                folium.Marker(location=coordinates, popup=folium.Popup(iframe), tooltip="Показать информацию").add_to(m)
                map_html = m._repr_html_()

            return render_template('index.html',
                                   message=message,
                                   coordinates=coordinates,
                                   map_html=map_html,
                                   thumbnail_uri=thumbnail_uri,
                                   all_exif=all_exif)
        else:
            return render_template('index.html', message='Ошибка: Не удалось обработать файл. Возможно, он поврежден.')

    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)