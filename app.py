import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import exif_utils
import folium
from datetime import datetime

# Настройки
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # Ограничение размера файла 200MB


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', message='Файл(ы) не были отправлены.')

        uploaded_files = request.files.getlist('file')  # Получаем СПИСОК файлов

        if not uploaded_files or uploaded_files[0].filename == '':
            return render_template('index.html', message='Файл(ы) не выбраны.')

        # Проверка формата для ВСЕХ файлов
        for file in uploaded_files:
            if not allowed_file(file.filename):
                return render_template('index.html',
                                       message=f'Ошибка: Файл "{file.filename}" имеет неподдерживаемый формат. Поддерживаются только .jpg, .jpeg и .png.')

        # Обработка одного файла
        if len(uploaded_files) == 1:
            file = uploaded_files[0]
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

                if coordinates and coordinates[0] is not None and coordinates[1] is not None:
                    m = folium.Map(location=coordinates, zoom_start=15)
                    html = f"""<div style="text-align: center;"><img src="{thumbnail_uri}" style="width:100%;"><br><br>Ш: {round(coordinates[0], 5)}<br>Д: {round(coordinates[1], 5)}</div>"""
                    iframe = folium.IFrame(html, width=180, height=230)
                    folium.Marker(location=coordinates, popup=folium.Popup(iframe),
                                  tooltip="Показать информацию").add_to(m)
                    map_html = m._repr_html_()

                return render_template('index.html',
                                       message=message,
                                       coordinates=coordinates,
                                       map_html=map_html,
                                       thumbnail_uri=thumbnail_uri,
                                       all_exif=all_exif,
                                       is_single_file=True)  # Флаг для JS и HTML

            else:
                return render_template('index.html',
                                       message='Ошибка: Не удалось обработать файл. Возможно, он поврежден.')

        # Обработка нескольких файлов
        else:  # len(uploaded_files) > 1
            all_processed_data = []  # Список для хранения всех обработанных данных

            for file_obj in uploaded_files:  # file_obj - это FileStorage объект
                filename = secure_filename(file_obj.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file_obj.save(filepath)

                processed_data = exif_utils.process_image(filepath)
                if processed_data:
                    processed_data['original_filename'] = filename  # Добавляем имя файла для отображения
                    all_processed_data.append(processed_data)

                os.remove(filepath)  # Удаляем временный файл

            # Фильтруем только те изображения, у которых есть координаты
            geo_tagged_images = [
                data for data in all_processed_data
                if data and data.get("coordinates") and data["coordinates"][0] is not None
            ]

            if not geo_tagged_images:
                return render_template('index.html',
                                       message='В загруженных файлах не найдено GPS-координат для построения маршрута. Загрузите другие файлы.')

            # Логика сортировки для маршрута
            all_have_datetime = all(img.get('datetime_original') for img in geo_tagged_images)

            sort_message = ""
            # if all_have_datetime:
            #     # если у всех есть дата, сортируем по ней
            #     geo_tagged_images.sort(key=lambda x: x['datetime_original'])
            #     sort_message = "маршрут построен по дате и времени съемки."
            # else:
            #     # иначе - по порядку загрузки (он сохраняется в geo_tagged_images)
            #     sort_message = "маршрут построен по порядку загрузки файлов (не все фото имеют дату съемки)."

            # Генерация карты маршрута
            map_html = None
            route_points = []

            # Центрируем карту по первым координатам, если они есть
            map_center_coords = geo_tagged_images[0]['coordinates']
            m = folium.Map(location=map_center_coords, zoom_start=13)  # Немного уменьшаем зум для маршрута

            for i, data in enumerate(geo_tagged_images):
                coords = data['coordinates']
                thumbnail_uri = data['thumbnail_uri']
                original_filename = data['original_filename']

                # Надпись для маркера (номер + дата, если есть)
                marker_label = f"#{i + 1}"
                if all_have_datetime and data.get('datetime_original'):
                    marker_label += f"<br>{data['datetime_original'].strftime('%Y-%m-%d %H:%M')}"

                # HTML-попап для маркера
                html_popup = f"""
                <div style="text-align: center;">
                    <img src="{thumbnail_uri}" style="width:100%; max-width:150px; border-radius: 5px;">
                    <br><strong>{original_filename}</strong><br>
                    {marker_label}<br>
                    Ш: {round(coords[0], 5)}<br>
                    Д: {round(coords[1], 5)}
                </div>
                """
                iframe = folium.IFrame(html_popup, width=180,
                                       height=270)  # Увеличиваем высоту для большего количества инфо

                folium.Marker(
                    location=coords,
                    popup=folium.Popup(iframe),
                    tooltip=f"Фото {i + 1}: {original_filename}"
                ).add_to(m)

                route_points.append(coords)  # Собираем точки для линии маршрута

            # Добавляем линию маршрута, если точек больше одной
            if len(route_points) > 1:
                folium.PolyLine(route_points, color="red", weight=4, opacity=0.7).add_to(m)

            map_html = m._repr_html_()

            # Рендерим шаблон для нескольких файлов
            return render_template(
                'index.html',
                multiple_results=all_processed_data,  # Список всех обработанных файлов
                map_html=map_html,
                sort_message=sort_message,
                is_single_file=False  # Флаг для JS и HTML
            )

    return render_template('index.html')  # Начальный GET-запрос или ошибка, не требующая конкретного сообщения


if __name__ == '__main__':
    app.run(debug=True)