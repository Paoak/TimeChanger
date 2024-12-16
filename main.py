r"""
pyinstaller --clean --onefile --hidden-import=os --hidden-import=shutil main.py - сборка без ui с консолью
pyinstaller --clean --onefile --noconsole --add-data "shablon.ui;." main.py - сборка с UI без консоли (один файл)/
pyinstaller --clean --onefile --noconsole --add-data "shablon.ui;." --hidden-import win32timezone --name TimeSet main.py  - одним файлом, без консоли, с присвоением имени.

D:\Progging\Python\DEV\timeSet\test - папка с файлами для теста
C:\Users\shelipov.aa\Desktop\тест фото\Кв 15
"""

import json
import os
import re
import sys
import time
import piexif
import random
import cv2
import pywintypes
import win32file
from PIL import Image, ImageFile
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressBar, QTextEdit, QDialog, QTableWidgetItem, QFileDialog, \
    QPushButton, QVBoxLayout, QLabel, QSizePolicy, QDesktopWidget
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QColor, QTextCursor

ImageFile.LOAD_TRUNCATED_IMAGES = True

# Класс наследующий поток
class ImageProcessor(QThread):
    """
    Класс, создающий поток и запускающий основную обработку в функции "run". Экземпляр данного класса создаётся в классе
    YourMainWindowClass, после нажатия на кнопку "применить", вспомогательной функции "start_processing". Далее весь
    процесс выполняется в функциях данного класса. Завершается обработка сигналом, который вызывает HTML таблицу
    (экземпляр класса ReportDialog), для отображения результатов.
    """

    # --------------<editor-fold desc="Инициализация, объявление сигналов, старт потока run()">----------------------------------------------------
    update_message = pyqtSignal(str)  # Сигнал для обновления сообщений
    finished_success = pyqtSignal(int, int, int, int, int, float, list, list)  # Сигнал для успешного завершения
    finished_error = pyqtSignal(str)  # Сигнал для завершения с ошибкой
    interrupted = pyqtSignal()  # Сигнал для прерывания
    update_progress = pyqtSignal(int)  # Сигнал обновления прогресс-бара
    update_folder_path = pyqtSignal()  # Сигнал для обновления пути к папке (для обновления таблицы)
    clear_console_signal = pyqtSignal()  # Сигнал для очистки консоли

    # Инициализация класса с потоком
    def __init__(self, directory, selected_date, start_time, minutes_from, minutes_to, console, files_data):
        """
        Инициализация класса с потоком, создание вспомогательных структур данных, создание флага, для отслеживания
        прерывания работы, создание формата времени, для получения времени отсчёта из пользовательского интерфейса
        другого класса.
        """
        super().__init__()
        self.console = console
        self.directory = directory  # Папка с .jpg и .json
        self.selected_date = selected_date.toPyDate()  # Выбранная дата
        self.start_time = start_time.toPyTime()  # Храним начальное время
        self.current_time = datetime.combine(self.selected_date, self.start_time)  # объединяем дату и время отсчёта
        #print(f"current_time = {self.current_time}")
        self.minutes_from = minutes_from  # Диапазон минут заданных в ui
        self.minutes_to = minutes_to
        self.is_interrupted = False  # Флаг для прерывания работы
        self.total_file_pairs = 0  # Общее количество пар файлов в папке (количество выделов)
        self.total_files_jpg = 0  # Количество найденных jpg файлов
        self.processed_files_jpg = 0  # Количество обработанных jpg файлов
        self.total_json_files = 0  # Количество найденных JSON файлов
        self.processed_json_files = 0  # Количество обработанных JSON файлов
        self.unprocessed_files = []  # Список для хранения файлов, которые не были обработаны (например, если не нашли соответствующий JSON)
        self.files_data = files_data  # Список кортежей (выдел, порядок, jpg_path, json_path, time_for_videl)
        # Инициализация current_time
        # self.current_time = datetime(
        #     selected_date.year(),
        #     selected_date.month(),
        #     selected_date.day(),
        #     start_time.hour(),
        #     start_time.minute(),
        #     start_time.second()
        # )

    # Запуск основного потока класса FileCollectorThread
    def run(self):
        """
        Старт потока класса, после нажатия на кнопку "принять". Получаем из UI класса YourMainWindowClass дату/время, порядок
        очереди для обработки. Время задаётся точкой отсчёта, а так же интервалом между выделами. Интервал берётся
        как случайное число в диапазоне минут, установленных в два спин-бокса(minutesFrom, minutesTo), секунды
        добавляются каждый раз случайным числом от 1 до 59(предусмотрен корректный пересчёт времени, что бы не получилась ситуация,
        когда секунд или минут более 59 в отображении). Файлы обрабатываются согласно установленной очерёдности
        в пользовательском интерфейсе(order).
        """
        try:
            start_time = time.time()  # Сохраняем время начала обработки
            self.clear_console_signal.emit()
            self.total_file_pairs = len(self.files_data)  # Общее количество файлов JPG для обработки
            self.processed_files_jpg = 0  # Инициализация обработанных JPG файлов
            self.processed_json_files = 0  # Инициализация обработанных JSON файлов
            total_videl = set()
            duplicate_videl = set()
            for index, (videl, order, jpg_path, json_path, time_for_videl) in enumerate(self.files_data):
                if self.is_interrupted:  # Проверяем, было ли прервано выполнение
                    self.interrupted.emit()
                    return
                if videl in total_videl:  # Проверка на дублирующиеся выделы
                    duplicate_videl.add(videl)
                else:
                    total_videl.add(videl)
                self.update_message.emit(f"<br>{order} Обработка в заданном порядке очереди, выдел - {videl}:")
                # Разделяем time_for_videl на часы, минуты и секунды
                h, m, s = map(int, time_for_videl.split(':'))  # Преобразование в целые числа
                time_delta = timedelta(hours=h, minutes=m, seconds=s)  # Создаем timedelta из часов, минут и секунд
                self.current_time += time_delta  # Обновляем self.current_time, добавляя time_delta
                new_creation_date = self.current_time  # Устанавливаем новую дату по умолчанию
                if jpg_path and os.path.exists(jpg_path) and 'нет файла или неверное название' not in jpg_path:  # Проверка JPG файла
                    self.total_files_jpg += 1  # Увеличиваем общее количество найденных JPG
                    try:
                        self.update_jpg_exif(jpg_path, new_creation_date, videl)  # Обновление EXIF
                        self.processed_files_jpg += 1  # Увеличиваем счетчик обработанных JPG файлов
                    except Exception as e:
                        msg = f"Ошибка при обработке JPG: {os.path.basename(jpg_path)}.<br>Текст ошибки: {e}"
                        self.unprocessed_files.append(msg)  # Запоминаем ошибку для JPG
                        self.update_message.emit("@" + msg)
                else:
                    msg = f"Не удалось найти JPG для выдела {videl}"
                    self.unprocessed_files.append(msg)  # Запоминаем ошибку для JPG
                    self.update_message.emit("@- " + msg)
                # Проверка JSON файла
                if json_path and os.path.exists(json_path) and 'нет файла или неверное название' not in json_path:
                    self.total_json_files += 1  # Увеличиваем общее количество найденных JSON
                    try:
                        self.update_json_file(json_path, new_creation_date, videl)  # Обновляем JSON файл
                        self.processed_json_files += 1  # Увеличиваем счетчик обработанных JSON файлов
                    except Exception as e:
                        msg = f"Ошибка при обработке JSON: {os.path.basename(json_path)}.<br>Текст ошибки: {e}"
                        self.unprocessed_files.append(msg)  # Запоминаем ошибку для JSON
                        self.update_message.emit("@" + msg)
                else:
                    msg = f"Не удалось найти JSON для выдела {videl}"
                    self.unprocessed_files.append(msg)  # Запоминаем ошибку для JSON
                    self.update_message.emit("@- " + msg)
                #self.current_time += timedelta(minutes=random.randint(self.minutes_from, self.minutes_to), seconds=random.randint(1, 59))  # Увеличиваем текущее время
                # Обновляем прогресс бар
                progress_value = int((index + 1) / self.total_file_pairs * 100)  # Рассчитываем процент выполнения
                self.update_progress.emit(progress_value)
            elapsed_time = time.time() - start_time  # Рассчитываем общее время обработки
            self.update_folder_path.emit()  # Обновляем таблицу
            self.finished_success.emit(self.total_file_pairs, self.total_files_jpg, self.processed_files_jpg,
                                       self.total_json_files, self.processed_json_files, elapsed_time,
                                       self.unprocessed_files, list(duplicate_videl))  # Сигнал завершения процесса
        except Exception as e:
            msg = f"@- Ошибка обработки: {e}"
            self.finished_error.emit(msg)
            self.update_message.emit(msg)
    # --------------</editor-fold>--------------------------------------------------------------------------------------

    # --------------<editor-fold desc="Функции">------------------------------------------------------------------------
    # Обновляем JSON файл: изменяем имя и меняем свойства
    def update_json_file(self, json_path, new_creation_date, videl):
        """
        Функция открывает JSON файл и находит участок, который связан с датой и временем, после чего изменяет их на
        нужные значения. Далее вызываются функции переименовывания файла и изменение даты в его свойствах.
        """
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8-sig') as json_file:  # Читаем содержимое JSON файла
                json_data = json.load(json_file)
            formatted_date = new_creation_date.strftime("%Y.%m.%d %H:%M:%S")  # Меняем формат даты в загруженных данных
            json_data["date"] = formatted_date  # Обновляем поле 'date'
            with open(json_path, 'w', encoding='utf-8') as json_file:  # Сохраняем изменения обратно в файл
                json.dump(json_data, json_file, ensure_ascii=False, separators=(',', ':'))  # Убираем пробелы
            new_file_path = self.rename_file(json_path, new_creation_date, videl)  # Используем rename_file для изменения имени JSON файла
            self.set_file_times(new_file_path, new_creation_date, videl)
        else:
            self.update_message.emit(f"@- JSON файл не найден: {json_path}")

    # Функция изменения мета-данных
    def update_jpg_exif(self, filepath, new_creation_date, videl):
        """
        Функция изменяет EXIF свойства изображения(фотографии), устанавливает в мета-данные дату и время создания, после
        чего вызывает функцию переименовывания.
        """
        ImageFile.LOAD_TRUNCATED_IMAGES = True  # Позволяем загружать усеченные изображения
        image = Image.open(filepath)  # Открытие изображения
        exif_dict = piexif.load(image.info['exif'])  # Загрузка EXIF данных
        formatted_creation_date = new_creation_date.strftime("%Y:%m:%d %H:%M:%S")  # Форматируем дату
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = formatted_creation_date  # Изменяем EXIF данные
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = formatted_creation_date
        exif_bytes = piexif.dump(exif_dict)  # Сохранение изменений
        image.save(filepath, exif=exif_bytes)  # Сохранение изображения
        self.set_file_times(filepath, new_creation_date, videl)  # Установка времени создания
        self.rename_file(filepath, new_creation_date, videl)  # Переименовывание файла

    # Функция для изменения имени файла
    def rename_file(self, filepath, new_creation_date, videl):
        """
        Функция переименовывает название файлов JPG и JSON. Переименование идёт именно заданной сигнатуры.
        6 и 7 части в названии, после знака "_" (5 и 6 для массива, если рассплитить).
        """
        directory, original_filename = os.path.split(filepath)  # Получаем директорию и имя файла
        parts = original_filename.split('_')  # Разбиваем имя файла по '_'
        # Возможно от этой проверки стоит отказаться, так как, данная проверка происходит на этапе постройки таблицы.
        if len(parts) < 7:  # Проверка: должно быть не менее 7 частей, чтобы избежать IndexError и обновление метаданных.
            msg = f"- Файл {original_filename} содержит неподдерживаемую сигнатуру в названии."
            self.update_message.emit(msg)
            self.unprocessed_files.append(msg)
            return  # Выходим из функции
        # Меняем дату и время в имени файла
        new_date_str = new_creation_date.strftime("%Y%m%d")  # Преобразуем дату в формат yyyyMMdd
        new_time_str = new_creation_date.strftime("%H%M%S")  # Преобразуем время в формат hhMMss
        #print(f"new_time_str = {new_time_str}")  # Преобразуем время в формат hhMMss
        parts[5] = new_date_str  # Меняем дату в имени файла
        parts[6] = new_time_str  # Меняем время в имени файла
        new_filename = '_'.join(parts)  # Собираем новую строку
        new_filepath = os.path.join(directory, new_filename)  # Формируем полный путь нового файла
        os.rename(filepath, new_filepath)  # Переименовываем файл
        self.update_message.emit(f"$- {os.path.basename(filepath)}  переименован в: {os.path.basename(new_filepath)}")
        if new_filepath.endswith(".json"):
            return new_filepath

    # Функция изменения свойств создания/изменения файла
    def set_file_times(self, filepath, creation_date, videl):
        """
        Функция устанавливает переданную дату создания в свойства файла.
        """
        if not os.path.exists(filepath):  # Проверяем, существует ли файл по указанному пути
            self.update_message.emit("@- Файл не был найден: {}".format(filepath))
            return
        creation_time = pywintypes.Time(creation_date)  # Преобразование даты в формат FILETIME
        # Открываем файл с правом записи
        handle = win32file.CreateFile(
            filepath,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_ATTRIBUTE_NORMAL,
            None
        )
        win32file.SetFileTime(handle, creation_time, None, creation_time)  # Установка времени создания
        win32file.CloseHandle(handle)  # Закрытие дескриптора

    # Функция переключает флаг прерывания
    def interrupt(self):
        """
        Переключение флага прерывания, для вызова сигнала
        """
        self.is_interrupted = True  # Устанавливаем флаг прерывания
    # --------------</editor-fold>--------------------------------------------------------------------------------------

# Основной класс, создающий интерфейс.
class YourMainWindowClass(QDialog):
    """
    Класс основного окна приложения, наследует от QDialog.
    Обрабатывает взаимодействия пользователя с интерфейсом и управление потоками.
    """

    # --------------<editor-fold desc="Инициализация">------------------------------------------------------------------
    # Инициализация
    def __init__(self, parent=None):
        """
        Инициализация основного окна.
        Задает начальные параметры и связь сигналов-кнопок с обработчиками.
        """
        super(YourMainWindowClass, self).__init__(parent)
        self.setupUi()
        self.is_setting_path = False  # Флаг для избежания повторной обработки
        self.allow_duplicates = True  # Изначально разрешаем дубликаты
        self.current_order_numbers = []  # Инициализируем текущие порядковые номера
        self.current_times = []  # Инициализируем время для выделов

    # Инициализация интерфейса, подключение сигналов.
    def setupUi(self):
        """
        Настройка пользовательского интерфейса.
        Загружает .ui файл и связывает сигналы кнопок с обработчиками.
        """
        if getattr(sys, 'frozen', False):
            ui_file = os.path.join(sys._MEIPASS, 'shablon.ui')
        else:
            ui_file = os.path.join(os.path.dirname(__file__), 'shablon.ui')
        uic.loadUi(ui_file, self)  # Загружаем интерфейс из .ui файла
        # Связка кнопок с обработчиками событий
        self.exitButton.clicked.connect(self.exit_button_click)  # Обработка нажатия на кнопку "Выход"
        self.acceptButton.clicked.connect(self.accept_button_click)  # Обработка нажатия на кнопку "Применить"
        self.browseButton.clicked.connect(self.browse_path)  # Сигнал выбора пути папки с файлами "..."
        self.breakButton.clicked.connect(self.break_button_click)  # Обработка нажатия на кнопку "Прервать"
        self.folderPath.textChanged.connect(self.folder_line_path)  # Обработка изменения текста в QLineEdit
        self.clearLogButton.clicked.connect(self.clearLog)  # Обработка нажатия на кнопку "Очистить"
        self.minutesFrom.valueChanged.connect(self.check_minutes_from)  # Подключаем сигнал для self.minutesFrom
        self.minutesTo.valueChanged.connect(self.check_minutes_to)  # Подключаем сигнал для self.minutesTo
        self.imageTableWidget.verticalHeader().setVisible(False)  # Отключаем вертикальный заголовок
        self.imageTableWidget.itemChanged.connect(self.on_item_changed)  # Сигнал изменения текста в ячейках таблицы
        self.manualTime.stateChanged.connect(self.toggle_manual_time_edit)  # Сигнал для чекбокса manualTime
        #self.timeDiscrLabel.setVisible(False)
        #self.manualTime.setVisible(False)  # Сокрытие чек-бокса с ручным изменением времени.
        self.dropQueue.clicked.connect(self.reset_order_numbers)  # Обработка нажатия на кнопку "Сброс очереди"
        self.progressBar.setVisible(False)
        self.switch_buttons(True)  # Изначально включаем кнопки
        self.console.clear()  # Очищаем текстовое поле
        self.console.setReadOnly(True)  # Запрет на ввод текста в консоль
        self.add_message("*<br>Перед выполнением рекомендуется сделать резервную копию файлов!")
        self.add_message(" ")
        #self.add_message("Успешный запуск.", is_italic=True)  # Сообщение о запуске
        #self.add_message("Выберите путь к папке с подпапками и нажмите 'Применить'...")  # Инструкция пользователю
    # --------------</editor-fold>--------------------------------------------------------------------------------------

    # --------------<editor-fold desc="Сигналы, слоты, функции">---------------------------------------------------------
    # Сигнал кнопки применить
    def accept_button_click(self):
        """
        Обработка нажатия кнопки "Применить".
        Проверяет введенный путь и запускает необходимые процессы.
        """
        self.switch_buttons(False)
        #self.clearLog()
        folder_path = self.folderPath.text().strip()  # Получаем введенный путь к папке
        if not folder_path:  # Если путь не указан
            self.add_message("@<br>Папка не выбрана!")
            self.switch_buttons(True)  # Активируем кнопки
            return
        try:
            if not os.path.exists(folder_path):  # Проверяем, существует ли путь и является ли он папкой
                self.add_message("@<br>Указанный путь не существует!")
                self.switch_buttons(True)
                QMessageBox.critical(self, "Ошибка", "Указанный путь не существует.")
                return
            if not os.path.isdir(folder_path):  # Если не папка
                self.add_message("@<br>Указанный путь не является папкой!")
                self.switch_buttons(True)
                QMessageBox.critical(self, "Ошибка", "Указанный путь не является папкой.")
                return
            # Если путь валиден и является папкой
            self.add_message(f"$<br>Путь указан верно: {folder_path}")  # Выводим сообщение в консоль
            self.progressBar.setVisible(True)  # Показываем прогресс-бар
            self.progressBar.setValue(0)  # Сбрасываем прогресс-бар на 0
            self.start_processing()  # Создание и запуск потока.
        except Exception as e:
            self.add_message(f"@<br>Произошла ошибка: {str(e)}")
            self.switch_buttons(True)  # Активируем кнопки
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {str(e)}")
            return
        # finally:
        #     self.switch_buttons(True)  # Активируем кнопки в конце

    # Создание экземпляра класса ImageProcessor и старт потока.
    def start_processing(self):
        """
        Функция собирает данные из таблицы, формирует их для передачи в поток класса ImageProcessor.
        Затем создаёт image_processor и запускает его.
        """
        files_data = []
        row_count = self.imageTableWidget.rowCount()  # Получаем количество строк в таблице
        for row in range(row_count):
            videl_item = self.imageTableWidget.item(row, 0)  # 'Выдел'
            order_item = self.imageTableWidget.item(row, 1)  # 'Порядок обработки'
            jpg_item = self.imageTableWidget.item(row, 2)  # 'JPG Файл'
            json_item = self.imageTableWidget.item(row, 3)  # 'JSON Файл'
            time_item = self.imageTableWidget.item(row, 4)  # 'Время'
            if order_item is not None:
                videl = int(videl_item.text())  # Получаем номер выдела
                order = int(order_item.text())  # Получаем порядок обработки
                jpg_file = os.path.join(self.folderPath.text(), jpg_item.text()) if jpg_item is not None else None
                json_file = os.path.join(self.folderPath.text(), json_item.text()) if json_item is not None else None
                time_file = time_item.text()
                #print(f"time_file = {time_file}")
                # Проверка существования файлов
                if (jpg_file and 'нет файла или неверное название' not in jpg_file and os.path.exists(jpg_file)) or \
                        (json_file and 'нет файла или неверное название' not in json_file and os.path.exists(json_file)):
                    files_data.append((videl, order, jpg_file if jpg_file else 'нет файла или неверное название',
                                       json_file if json_file else 'нет файла или неверное название', time_file))
        if not files_data:  # Если нет данных для обработки, уведомляем пользователя
            self.add_message("@Нет файлов для обработки!")
            return
        files_data.sort(key=lambda x: x[1])  # Сортировка по очереди обработки
        selected_date = self.dateEdit.date()  # Получение выбранной даты
        start_time = self.timeEdit.time()  # Получение установленного времени
        folder_path = self.folderPath.text()  # Получение пути к папке
        # Создание экземпляра ImageProcessor с корректными параметрами
        self.image_processor = ImageProcessor(
            folder_path,
            selected_date,
            start_time,
            self.minutesFrom.value(),
            self.minutesTo.value(),
            self.console,
            files_data
        )
        self.image_processor.finished_success.connect(self.processing_finished_success)  # Сигнал успешного завершения
        self.image_processor.finished_error.connect(self.processing_finished_error)  # Сигнал завершения с ошибкой
        self.image_processor.interrupted.connect(self.processing_interrupted)  # Сигнал прерывания
        self.image_processor.update_message.connect(self.add_message)  # Подключение сигнала обновления сообщений
        self.image_processor.update_progress.connect(self.update_progress)  # Подключение прогресс-бара
        self.image_processor.update_folder_path.connect(self.update_folder_path)  # Подключение сигнала обновления пути
        self.image_processor.clear_console_signal.connect(self.clearLog)  # Подключаем сигнал очистки
        self.image_processor.start()  # Запуск потока обработки

    # Сигнал кнопки выбора пути к папке с файлами
    def browse_path(self):
        """
        Открывает диалоговое окно для выбора папки.
        Устанавливает выбранный путь в QLineEdit и загружает файлы.
        Включает в себя сигнал заполнения QLineEdit.
        """
        # Открываем диалог выбора папки
        folderPath = QFileDialog.getExistingDirectory(self, "Выберите папку с файлами")
        if folderPath:  # Если папка выбрана
            self.folderPath.setText(folderPath)  # Установка пути к папке
            self.folder_line_path()  # Проверка и загрузка файлов заново

    # Сигнал изменения текста self.folderPath. Проверка пути к папке с файлами
    def folder_line_path(self):
        """
        Проверяет введенный путь на действительность.
        Если путь валиден, вызывает метод для обработки JPG файлов.
        """
        try:
            if self.is_setting_path:  return  # Проверяем, не устанавливается ли путь
            folder_path = self.folderPath.text()  # Получаем текст из QLineEdit
            if os.path.isdir(folder_path):  # Проверяем, является ли путь директория
                self.browse_jpg_files(folder_path)  # Обработка найденных JPG файлов
            else:
                self.imageTableWidget.clear()  # Очищаем список, если путь недействителен
        except Exception as e:
            self.add_message(f"Ошибка в функции folder_line_path: {e}")

    # Настройка и отображение таблицы
    def browse_jpg_files(self, folder_path):
        """
        Ищет JPG файлы и соответствующие JSON файлы в указанной папке, строит и отображает результаты в таблице.
        Также тут происходит настройка таблицы с файлами, запрет на редактирование, растягивание столбцов и пр.
        Дублируемые файлы корректно обрабатываются.
        """
        try:
            self.console.clear()  # Очищаем консоль и уведомляем пользователя о необходимости резервного копирования
            self.add_message("*Перед выполнением рекомендуется сделать резервную копию файлов!")
            # Отключаем сигнал itemChanged для предотвращения рекурсии во время очистки таблицы
            self.imageTableWidget.itemChanged.disconnect(self.on_item_changed)
            self.imageTableWidget.clear()
            self.imageTableWidget.setRowCount(0)
            self.imageTableWidget.setColumnCount(5)  # Устанавливаем количество столбцов в 5
            self.imageTableWidget.setHorizontalHeaderLabels(['Выдел', 'Порядок обработки', 'JPG Файл', 'JSON Файл', 'Время на выдел'])
            header = self.imageTableWidget.horizontalHeader()  # Настраиваем заголовок таблицы
            header.setStretchLastSection(True)  # Растягиваем последний столбец до правого края
            jpgs = []  # Списки для хранения JPG и JSON файлов
            jsons = []
            pairs = []  # Список для пар файлов: (номер выдела, квартал, jpg, json)
            for filename in os.listdir(folder_path):  # Сбор файлов из указанной папки
                file_path = os.path.join(folder_path, filename)  # Получаем полный путь к файлу
                parts = filename.split('_')  # Разделяем имя файла по символу '_'
                if len(parts) < 7:  # Пропускаем файлы с недостаточным количеством частей
                    continue
                key = (parts[3], parts[4])  # (квартал, выдел)
                kvartal = parts[3]  # Получаем номер квартала
                if filename.lower().endswith('.jpg'):  # Проверяем тип файла и добавляем его в соответствующий список
                    jpgs.append((key, kvartal, file_path))  # Сохраняем ключ, квартал и путь
                elif filename.lower().endswith('.json'):
                    jsons.append((key, kvartal, file_path))  # Сохраняем ключ, квартал и путь
            # Сортируем JPG и JSON файлы по кварталам и выделам
            jpgs.sort(key=lambda x: (x[0][0], x[0][1]))
            jsons.sort(key=lambda x: (x[0][0], x[0][1]))
            jpg_index = 0  # Индекс для прохода по jpg
            json_index = 0  # Индекс для прохода по json
            while jpg_index < len(jpgs) or json_index < len(jsons):  # Поиск пар jpg и json файлов
                if jpg_index < len(jpgs) and json_index < len(jsons):
                    jpg_key = jpgs[jpg_index][0]
                    json_key = jsons[json_index][0]
                    if jpg_key == json_key:  # Если ключи совпадают, добавляем в пары
                        pairs.append((jpg_key[1], jpgs[jpg_index][2], jsons[json_index][2]))
                        jpg_index += 1
                        json_index += 1
                    elif jpg_key < json_key:  # Если jpg ключ меньше, json добавляется с сообщением об отсутствии
                        pairs.append((jpg_key[1], jpgs[jpg_index][2], "нет файла или неверное название"))
                        jpg_index += 1
                    else:  # Если json ключ меньше, jpg добавляется с сообщением об отсутствии
                        pairs.append((json_key[1], "нет файла или неверное название", jsons[json_index][2]))
                        json_index += 1
                elif jpg_index < len(jpgs):  # Остались только JPG файлы
                    pairs.append((jpgs[jpg_index][0][1], jpgs[jpg_index][2], "нет файла или неверное название"))
                    jpg_index += 1
                elif json_index < len(jsons):  # Остались только JSON файлы
                    pairs.append((jsons[json_index][0][1],"нет файла или неверное название", jsons[json_index][2]))
                    json_index += 1
            table_data = []  # Формируем данные таблицы
            duplicates = {}  # Для хранения дублирующихся выделов
            name_duplicates = {}  # Для хранения дублирующихся имен файлов
            for videl, jpg_path, json_path in pairs:
                if videl not in duplicates:  # Запоминаем дублирование выделов
                    duplicates[videl] = []
                duplicates[videl].append(jpg_path)  # Добавляем путь к JPG в дубликаты
                jpg_file_name = os.path.basename(jpg_path)  # Получаем имя JPG файла
                name_duplicates.setdefault(jpg_file_name, []).append(jpg_path)  # Запоминаем дублирование по именам
                table_data.append((videl, jpg_path, json_path))  # Добавляем данные в таблицу
            table_data.sort(key=lambda x: int(x[0]))  # Сортируем таблицу по выделу
            self.imageTableWidget.setRowCount(len(table_data))  # Устанавливаем количество строк в таблице
            self.current_order_numbers = []  # Сохраняем текущее состояние порядковых номеров
            self.current_times = []  # Сохраняем значение времени для выделов
            for row_counter, (videl, jpg_path, json_path) in enumerate(table_data):  # Заполняем таблицу данными и проверяем на дубли
                is_duplicate = len(duplicates.get(videl, [])) > 1  # Проверяем наличие дубликатов выделов
                is_name_duplicate = len(name_duplicates.get(os.path.basename(jpg_path), [])) > 1  # Проверяем дубликаты по имени
                self.set_table_item(row_counter, 0, str(videl), is_duplicate=is_duplicate)  # Устанавливаем номер выдела
                order_item = QTableWidgetItem(str(row_counter + 1))  # Порядковый номер
                order_item.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                rnd = timedelta(minutes=random.randint(self.minutesFrom.value(), self.minutesTo.value()), seconds=random.randint(1, 59))  # Получение случайных значений минут
                default_time = QTableWidgetItem(str(rnd))  # Стандартное значение в минутах
                self.imageTableWidget.setItem(row_counter, 1, order_item)  # Устанавливаем порядковый номер
                self.imageTableWidget.item(row_counter, 0).setTextAlignment(QtCore.Qt.AlignCenter)  # Выравнивание по центру
                self.imageTableWidget.item(row_counter, 1).setTextAlignment(QtCore.Qt.AlignCenter)  # Выравнивание по центру
                self.set_table_item(row_counter, 2, os.path.basename(jpg_path), is_duplicate=is_name_duplicate)  # Устанавливаем JPG файл
                self.set_table_item(row_counter, 3, os.path.basename(json_path))  # Устанавливаем JSON файл
                #default_time.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)  # Флаги для столбца "Минуты на выдел"
                default_time.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)  # Флаги для столбца "Минуты на выдел", без редактирования
                self.set_table_item(row_counter, 4, default_time)  # Устанавливаем стандартное значение минут
                self.imageTableWidget.item(row_counter, 4).setTextAlignment(QtCore.Qt.AlignCenter)  # Выравнивание по центру для столбца "Минуты на выдел"
                self.imageTableWidget.item(row_counter, 4).setBackground(QColor(220, 220, 220))  # Устанавливаем серый фон
                #self.imageTableWidget.item(row_counter, 4).setData(QtCore.Qt.UserRole, str(rnd))  # Сохраняем последнее значение в UserRole
                self.current_order_numbers.append(row_counter + 1)  # Сохраняем номер в списке
                self.current_times.append(default_time.text())
                self.imageTableWidget.setRowHeight(row_counter, 15)  # Устанавливаем высоту строки
            self.imageTableWidget.resizeColumnsToContents()  # Автоматическое изменение ширины колонок
            self.imageTableWidget.itemChanged.connect(self.on_item_changed)  # Подключаем сигнал обратно
            self.toggle_manual_time_edit()
            #self.check_minutes_from()  # обновление данных в колонке "Время на выдел"
            self.add_message(f"$Сформирована таблица из папки: {folder_path}")
            messages = []  # Сообщение о дублирующихся выделах
            if len(table_data) == 0:  # Если таблица пустая, уведомляем об этом
                messages.append("Файлы не найдены!")
            duplicate_messages = {}  # Словарь для хранения сообщений по дубликатам и отсутствующим файлам
            missing_messages = {}
            for videl_num, files in duplicates.items():  # Проход по дубликатам
                if len(files) > 1:
                    jpg_file_names = set()  # Используем множество для уникальных имен JPG файлов
                    json_file_names = set()  # Используем множество для уникальных имен JSON файлов
                    for jpg_file in files:
                        if "нет файла или неверное название" not in jpg_file:
                            jpg_file_names.add(os.path.basename(jpg_file))  # Добавляем уникальные имена JPG
                        for videl, jpg_path, json_path in table_data:
                            if jpg_path == jpg_file and videl == videl_num and json_path != "нет файла или неверное название":
                                json_file_names.add(os.path.basename(json_path))  # Добавляем уникальные имена JSON
                    all_file_names = list(jpg_file_names | json_file_names)  # Объединяем множества
                    duplicate_messages[videl_num] = all_file_names  # Сохраняем для последующей обработки
            for videl, jpg_path, json_path in table_data:  # Проход по всем записям в таблице для проверки отсутствующих файлов
                if jpg_path == "нет файла или неверное название":
                    missing_messages.setdefault(videl, []).append("JPG файл отсутствует.")
                if json_path == "нет файла или неверное название":
                    missing_messages.setdefault(videl, []).append("JSON файл отсутствует.")
            for videl_num, files in duplicate_messages.items():  # Формируем сообщения
                messages.append(f"Файлы с одинаковым номером выдела '{videl_num}':<br>- {'<br>- '.join(files)}<br>")
            for videl_num, issues in missing_messages.items():
                messages.append(f"- Для выдела №{videl_num} {'; '.join(issues)}")
            if messages:  # Если найдены сообщения, отображаем их
                self.add_message(f"@<br>Обнаружены предупреждения!")
                self.add_message(f"@Рекомендуется их устранить перед дальнейшей работой:")
                for m in messages:
                    self.add_message(f"{m}")
                self.console.moveCursor(QTextCursor.Start)  # Прокрутка QTextEdit к началу
                self.console.ensureCursorVisible()
        except PermissionError:  # Обработка ошибок доступа
            QMessageBox.warning(self, "Ошибка", "У вас нет прав доступа к этой папке.")
            self.imageTableWidget.itemChanged.connect(self.on_item_changed)
        except Exception as e:  # Обработка других ошибок
            QMessageBox.warning(self, "Ошибка", f"Произошла ошибка: {e}")
            self.add_message(f"Произошла ошибка: {e}")
            self.imageTableWidget.itemChanged.connect(self.on_item_changed)

    # Функция для установки в ячейку текст, флагов и цвета.
    def set_table_item(self, row, column, text, is_duplicate=False, editable=False, lone=False):
        """
        Устанавливает текст в ячейку таблицы, устанавливает флаги и цвет.
        """
        item = QTableWidgetItem(text)  # Создаем новый элемент
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if editable:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)  # Если ячейка редактируемая
        if is_duplicate or lone or text == "нет файла или неверное название":
            item.setBackground(QColor('orange'))  # Подсветка оранжевым для дублирующихся выделов и отсутствующих файлов
        self.imageTableWidget.setItem(row, column, item)  # Устанавливаем элемент в таблицу

    # Сигнал смены значений в ячейках таблицы self.imageTableWidget
    def on_item_changed(self, item):
        """
        Обрабатывает изменения в ячейках таблицы.
        Пересчитывает порядковые номера при изменении значения в столбце 'Порядок обработки'.
        1) Копирование текущих порядковых номеров - создаем копию списка current_order_numbers.
        2) Проверка диапазона - новое значение не должно(не может быть) больше диапазона.
        3) Обновление значений - если новое значение меньше старого, сдвигаем все числа в промежутке от нового до старого значения.
            Если новое значение больше старого, сдвигаем все числа между старым и новым вниз.
        4) Обновление таблицы - после всех изменений обновляем новую позицию порядковых номеров в таблице.
        """
        if item.column() == 1:  # 1 - индекс столбца 'Порядок обработки'
            self.imageTableWidget.itemChanged.disconnect(self.on_item_changed)  # Отключаем сигнал для предотвращения рекурсии
            try:
                new_value_str = item.text()  # Получаем новое значение как строку
                if not new_value_str.isdigit():  # Проверяем, содержит ли строка только цифры
                    self.add_message("@<br>Вводите только целые числа!")
                    QMessageBox.critical(self, "Ошибка", "Вводите только целые числа!")
                    old_value = self.current_order_numbers[item.row()]  # Сохраняем старое значение
                    item.setText(str(old_value))  # Возвращаем старое значение
                    return
                new_value = int(new_value_str)  # Преобразуем строку в целое число
                current_row = item.row()  # Текущая строка
                order_numbers = self.current_order_numbers[:]  # Делаем копию текущих порядковых номеров
                if new_value < 1 or new_value > len(order_numbers):  # Проверка, что новое значение в допустимом диапазоне
                    self.add_message(f"@<br>Значение должно быть в пределах от 1 до {len(order_numbers)}!")
                    QMessageBox.critical(self, "Ошибка", f"Значение должно быть в пределах от 1 до {len(order_numbers)}!")
                    old_value = order_numbers[current_row]  # Сохраняем старое значение
                    item.setText(str(old_value))  # Возвращаем старое значение
                    return
                old_value = order_numbers[current_row]
                if new_value != old_value:  # Если новое значение отличается от старого
                    # Изменяем значения
                    if new_value < old_value:  # Если перемещаем значение вверх очереди
                        for i in range(len(order_numbers)):
                            if new_value <= order_numbers[i] < old_value:
                                order_numbers[i] += 1  # Сдвигаем всё согласно очереди
                    elif new_value > old_value:  # Если перемещаем значение вниз очереди
                        for i in range(len(order_numbers)):
                            if old_value < order_numbers[i] <= new_value:
                                order_numbers[i] -= 1  # Сдвигаем вниз
                order_numbers[current_row] = new_value  # Устанавливаем новое значение
                for index in range(len(order_numbers)):  # Обновляем значения в таблице
                    item_to_update = self.imageTableWidget.item(index, 1)
                    if item_to_update is not None:
                        item_to_update.setText(str(order_numbers[index]))
                self.current_order_numbers = order_numbers  # Обновляем текущее состояние
            except ValueError:
                self.add_message("@<br>Вводите только целые числа!")
                QMessageBox.critical(self, "Ошибка", "Вводите только целые числа!")
                old_value = self.current_order_numbers[item.row()]  # Сохраняем старое значение
                item.setText(str(old_value))  # Возвращаем старое значение
            except Exception as e:
                self.add_message(f"Ошибка в функции пересчёта порядковых номеров on_item_changed:<br>{e}")
            finally:
                self.imageTableWidget.itemChanged.connect(self.on_item_changed)  # Подключаем сигнал обратно
        if item.column() == 4:  # 4 - индекс столбца "Время на выдел"
            value = item.text()
            old_time_value = self.current_times[item.row()]  # Сохраняем старое значение
            if value == '':  # Обработка случая, когда введено пустое значение
                item.setText(str(old_time_value))  # Обновляем текущее состояние
            else:
                if not re.match(r'^\d{0,2}:\d{2}:\d{2}$', value):  # Проверяем, допускается ли значение
                    QMessageBox.warning(self, "Некорректный ввод", "Пожалуйста, введите время в формате HH:mm:ss.")
                    item.setText(str(old_time_value))  # Возвращаем старое значение
                else:
                    self.current_times[item.row()] = value  # Обновляем текущее состояние времени

    # Восстановление исходного положения столбца 'Порядок обработки'
    def reset_order_numbers(self):
        """
        Сбрасывает порядковые номера в столбце 'Порядок обработки' на исходные значения.
        """
        self.imageTableWidget.itemChanged.disconnect(self.on_item_changed)  # Отключаем сигнал для предотвращения рекурсии
        row_count = self.imageTableWidget.rowCount()  # Получаем количество строк в таблице
        for row in range(row_count):
            item = self.imageTableWidget.item(row, 1)  # Получаем ячейку в столбце 'Порядок обработки'
            if item is not None:
                item.setText(str(row + 1))  # Устанавливаем новое значение
        self.current_order_numbers = list(range(1, row_count + 1))  # Обновляем текущее состояние
        self.imageTableWidget.itemChanged.connect(self.on_item_changed)  # Подключаем сигнал обратно

    # Перезагружает данные в таблице
    def update_folder_path(self):
        """
        Сигнал созданный специально для авто-обновления таблицы в self.imageTableWidget после выполнения потока.
        """
        self.switch_buttons(True)
        folder_path = self.folderPath.text()  # Получаем путь к папке
        if os.path.isdir(folder_path):  # Проверяем, что это действительно папка
            self.browse_jpg_files(folder_path)  # Пытаемся снова прочитать файлы

    # Состояние интерфейса в зависимости от процесса
    def switch_buttons(self, mode):
        """
        Включает или отключает кнопки в зависимости от состояния обработки.
        """
        self.breakButton.setEnabled(not mode)  # Активируем/деактивируем кнопку "Прервать"
        self.acceptButton.setEnabled(mode)  # Активируем/деактивируем кнопку "Применить"
        self.clearLogButton.setEnabled(mode)  # Активируем/деактивируем кнопку "Очистить"
        self.browseButton.setEnabled(mode)  # Активируем/деактивируем кнопку выбора папки
        self.openCheckBox.setEnabled(mode)  # Активируем/деактивируем чекбокс
        self.folderPath.setEnabled(mode)  # Активируем/деактивируем поле для ввода пути
        self.dateEdit.setEnabled(mode)  # Активируем/деактивируем выбор даты в QDateEdit
        self.timeEdit.setEnabled(mode)  # ААктивируем/деактивируем выбор времени в QTimeEdit
        self.minutesFrom.setEnabled(mode)  # Активируем/деактивируем выбор диапазона минут в QSpinBox
        self.minutesTo.setEnabled(mode)
        self.imageTableWidget.setEnabled(mode)  # Активируем/деактивируем доступ к таблице QTableWidget
        self.dropQueue.setEnabled(mode)  # Активируем/деактивируем кнопку "Сбросить очередь"
        self.manualTime.setEnabled(mode)

    # Вывод сообщений в журнал событий
    def add_message(self, text):
        """
        Добавляет сообщение в лог (в текстовое поле). Оказывается, в QTextEdit всё выводится в формате HTML, зная
        это, получилось создать результирующую таблицу с итогами.
        """
        clean_text = text.strip()  # Удаляем пробелы в начале и конце строки
        if "@" in clean_text:  # Проверяем наличие "@" в тексте
            formatted_text = f"<font color='brown'>{clean_text[1:]}</font>"  # Убираем первый символ и меняем цвет
        elif "$" in clean_text:
            formatted_text = f"<font color='green'>{clean_text[1:]}</font>"
        elif "*" in clean_text:
            formatted_text = f"<font color='blue'>{clean_text[1:]}</font>"
        else:
            formatted_text = f"<font color='black'>{clean_text}</font>"  # Вручную вводится дефолтный цвет, для избежания коллизий.
        self.console.append(formatted_text)  # Отображение текста в консоли

    # Сигнал для автоматического изменения значений в QSpinBox для избежания ошибки.
    def check_minutes_from(self):
        """
        Сигнал отслеживает значения в спин-боксах, чтобы минимальное не стало больше максимального, для избежания
        ошибок, и обновляет время на выдел для всех строк в таблице.
        """
        minutes_from = self.minutesFrom.value()  # Получаем значения из QSpinBox
        minutes_to = self.minutesTo.value()
        if minutes_from >= minutes_to:  # Проверяем, что minutesFrom больше или равно minutesTo
            self.minutesTo.setValue(minutes_from + 1)
        self.update_time_column(minutes_from, self.minutesTo.value())

    # Сигнал для автоматического изменения значений в QSpinBox для избежания ошибки.
    def check_minutes_to(self):
        """
        Сигнал отслеживает значения в спин-боксах, чтобы минимальное не стало больше максимального, для избежания
        ошибок, и обновляет время на выдел для всех строк в таблице.
        """
        minutes_from = self.minutesFrom.value()  # Получаем значения из QSpinBox
        minutes_to = self.minutesTo.value()
        if minutes_to <= minutes_from:
            self.minutesFrom.setValue(minutes_to - 1)
        self.update_time_column(self.minutesFrom.value(), minutes_to)

    # Обновление после изменения значений в спин-боксах
    def update_time_column(self, minutes_from, minutes_to):
        """
        Обновление колонки "Время на выдел"
        """
        row_count = self.imageTableWidget.rowCount()
        # print(f"minutes_from = {minutes_from}")
        # print(f"minutes_to = {minutes_to}")
        for row_counter in range(row_count):
            if minutes_from == minutes_to:  # Вычисляем временной интервал, проверяя диапазон
                rnd = timedelta(minutes=minutes_from, seconds=random.randint(1, 59))  # Если значения совпадают, установим его как одно значение
            else:
                rnd = timedelta(minutes=random.randint(minutes_from, minutes_to), seconds=random.randint(1, 59))
            time_item = QTableWidgetItem(str(rnd))  # Создаем новый элемент для ячейки
            if self.manualTime.isChecked():
                time_item.setFlags(time_item.flags() | QtCore.Qt.ItemIsEditable)  # Разрешить редактирование
                time_item.setBackground(QColor(255, 255, 255))  # Сбрасываем цвет фона на белый
            else:
                time_item.setFlags(time_item.flags() & ~QtCore.Qt.ItemIsEditable)  # Запретить редактирование
                time_item.setBackground(QColor(220, 220, 220))  # Устанавливаем серый фон
            self.imageTableWidget.setItem(row_counter, 4, time_item)  # Устанавливаем новый элемент для "Время на выдел"
            self.imageTableWidget.item(row_counter, 4).setTextAlignment(QtCore.Qt.AlignCenter)  # Выравнивание по центру

    # Обработчик состояния чекбокса
    def toggle_manual_time_edit(self):
        """
        Обрабатывает изменение состояния чекбокса `manualTime`.
        Включает или отключает редактирование колонки 'Время на выдел'.
        """
        is_manual_time_enabled = self.manualTime.isChecked()  # Проверяем состояние чекбокса
        row_count = self.imageTableWidget.rowCount()  # Получаем количество строк в таблице
        for row in range(row_count):
            item = self.imageTableWidget.item(row, 4)  # Получаем ячейку 'Время на выдел'
            if item is not None:
                if is_manual_time_enabled:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)  # Разрешить редактирование
                    item.setBackground(QColor(255, 255, 255))  # Сбрасываем цвет фона на белый
                else:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)  # Запретить редактирование
                    item.setBackground(QColor(220, 220, 220))  # Устанавливаем серый фон
                self.imageTableWidget.setItem(row, 4, item)  # Перезаписываем ячейку

    # Сигнал кнопки выход
    def exit_button_click(self):
        """
        Закрывает диалоговое окно при нажатии на кнопку "Выход".
        """
        self.reject()  # Закрытие диалогового окна

    # Сигнал кнопки прервать
    def break_button_click(self):
        """
        Обработка нажатия кнопки "Прервать".
        Устанавливает флаг прерывания для потока, если он запущен.
        """
        if hasattr(self, 'image_processor'):
            self.image_processor.interrupt()  # Устанавливаем флаг прерывания
            self.update_folder_path()

    # Очистка журнала событий
    def clearLog(self):
        """
        Очищает текстовое поле для отображения логов и сбрасывает прогресс бар.
        """
        self.console.clear()  # Очищаем текстовое поле
        self.progressBar.setValue(0)  # Сбрасываем значение прогресс бара

    # Открытие папки, после обработки, по чек-боксу
    def open_folder(self, path):
        """
        Открывает текущую, указанную папку с файлами, после успешной обработки, если активирован соответствующий чек-бокс.
        """
        if os.path.isdir(path):
            try:
                os.startfile(path)  # Открытие папки
            except Exception as e:
                self.add_message(f"Произошла ошибка во время открытия папки: {e}")
        else:
            self.add_message(f"Указанный путь не существует или не является директорией: {path}")

    @pyqtSlot(int)
    def update_progress(self, value):
        """
        Обновляет значение прогресс-бара.
        """
        self.progressBar.setValue(value)  # Устанавливаем новое значение прогресс-бара
        if value >= 100:  # Если прогресс завершен
            self.progressBar.setVisible(False)  # Скрываем прогресс-бар
        else:
            self.progressBar.setVisible(True)  # Показываем прогресс-бар

    # Слот завершения с ошибкой.
    @pyqtSlot(str)
    def processing_finished_error(self, error_message):
        """
        Сигнал завершения с ошибкой, обновляет путь в строке с папкой, уведомляет об ошибке.
        """
        #self.clearLog()
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)
        self.update_folder_path()
        self.switch_buttons(True)  # Смена доступности кнопок
        QMessageBox.critical(self, "Ошибка", error_message)
        self.add_message(f"@<br>Во время обработки произошла ошибка:<br>{error_message}")

    # Слот прерывания выполнения.
    @pyqtSlot()
    def processing_interrupted(self):
        """
        Сигнал очищает лог и переключает кнопки, если процесс был прерван
        """
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)
        self.clearLog()  # Очистка лога
        #self.switch_buttons(True)  # Смена доступности кнопок
        self.add_message("@<br>Обработка прервана пользователем!")  # Сообщение о прерывании

    # Слот успешного завершения. Формирование HTML содержимого таблицы и вызов диалогового окна с результатами.
    @pyqtSlot(int, int, int, int, int, float, list, list)
    def processing_finished_success(self, total_files_pairs, total_jpg_files, processed_jpg_files, total_json_files,
                                    processed_json_files, elapsed_time, unprocessed_files, duplicate_files):
        """
        Срабатывает при успешном завершении. Собирает информацию о проделанной работе и формирует HTML таблицу, далее
        создаёт экземпляр класса ReportDialog и показывает пользователю результаты в диалоговом окне.
        """
        try:
            self.progressBar.setValue(0)
            self.progressBar.setVisible(False)
            self.update_folder_path()
            self.switch_buttons(True)
            # Начинаем формировать таблицу
            html_content = """
                            <style>
                                table {
                                    width: 100%;               /* Таблица заполняет 100% ширины */
                                    border-collapse: collapse; /* Убираем пробелы между ячейками */
                                    margin-top: 10px;
                                    font-family: Arial, sans-serif;
                                    table-layout: auto;        /* Автоматическое распределение ширины */
                                }
                                td {
                                    padding: 10px;
                                    text-align: left;          /* Приравниваем текст в ячейках к левому краю по умолчанию */
                                    vertical-align: top;       /* Выравнивание по верхнему краю */
                                    border: 1px solid #ddd;    /* Границы ячеек */
                                    white-space: nowrap;        /* Запрет автопереноса текста */
                                }
                                tr:nth-child(even) {background-color: #f2f2f2;} /* Чередующиеся цвета строк */
                                tr:hover {background-color: #ddd;} /* Цвет при наведении на строку */
                            </style>
                            <table>
                            """
            # Добавляем данные в таблицу
            html_content += f"""
                        <tr>
                            <td><strong>Количество выделов:</strong></td>
                            <td>{total_files_pairs}</td>
                            <td><strong>Время выполнения:</strong></td>
                            <td>{elapsed_time:.2f} секунд</td>
                        </tr>
                        <tr>
                            <td><strong>Найдено файлов .jpg:</strong></td>
                            <td>{total_jpg_files}</td>
                            <td><strong>Обработано файлов .jpg:</strong></td>
                            <td>{processed_jpg_files}</td>
                        </tr>
                        <tr>
                            <td><strong>Найдено файлов .json:</strong></td>
                            <td>{total_json_files}</td>
                            <td><strong>Обработано файлов .json:</strong></td>
                            <td>{processed_json_files}</td>
                        </tr>
                    """
            if duplicate_files:  # Вывод информации о дублированных выделах
                html_content += "<tr><td><strong>Номера дублированных выделов:</strong></td><td colspan='3' style='color: brown; border: 1px solid #ddd;'>" + ", №".join(map(str, duplicate_files)) + "</td></tr>"
            if unprocessed_files:  # Ошибки во время обработки файлов
                numbered_unprocessed_files = "<br>".join(f"{i + 1}. {error}" for i, error in enumerate(unprocessed_files))
                html_content += f"<tr><td><strong>Ошибки во время обработки:</strong></td><td colspan='3' style='color: brown; border: 1px solid #ddd;'>" + numbered_unprocessed_files + "</td></tr>"
            html_content += "</table>"  # Закрываем таблицу
            self.report_dialog = ReportDialog(html_content, self)  # Открываем диалог с отчетом
            self.report_dialog.exec_()  # Показываем диалог и ждем его закрытия
            if self.openCheckBox.isChecked():
                self.open_folder(self.folderPath.text())
        except Exception as e:
            self.add_message(f"@<br>Ошибка в финальном выводе: {e}")
    # --------------</editor-fold>--------------------------------------------------------------------------------------

# Класс создаёт дополнительное диалоговое окно для отчёта.
class ReportDialog(QDialog):
    """
    Класс настраивает и создаёт диалоговое окно, в которое будет передана HTML таблица для финального вывода.
    """

    # --------------<editor-fold desc="Инициализация">------------------------------------------------------------------
    # Инициализация класса
    def __init__(self, report_content, parent=None):
        """
        Инициализация диалогового окна, показывающего отчёт об обработке. Принимает в параметры HTML таблицу.
        """
        super(ReportDialog, self).__init__(parent)
        self.setWindowTitle("Отчёт об обработке")
        self.setMinimumSize(450, 120)  # Устанавливаем минимальный размер окна
        self.setMaximumSize(1200, 700)  # Устанавливаем максимальный размер окна (ширина, высота)
        layout = QVBoxLayout()  # Главный вертикальный LAYOUT для диалога
        label = QLabel("Отчёт об обработке:")  # Заголовок
        layout.addWidget(label)
        self.textEdit = QTextEdit()  # Поле для отображения HTML-контента
        self.textEdit.setReadOnly(True)  # Делаем текстовое поле только для чтения
        self.textEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Поле для растяжения
        layout.addWidget(self.textEdit)
        self.closeButton = QPushButton("Закрыть")  # Кнопка "Закрыть"
        self.closeButton.clicked.connect(self.accept)  # Закрываем диалог
        layout.addWidget(self.closeButton)
        self.setLayout(layout)  # Устанавливаем layout для диалога
        self.textEdit.setHtml(report_content)  # Устанавливаем HTML
        QTimer.singleShot(0, self.update_table_dimensions)  # Используем QTimer, чтобы установить размеры после инициализации

    # Установка размеров и центрирование диалогового окна
    def update_table_dimensions(self):
        """
        Вспомогательная функция, спустя задержку QTimer.singleShot обновляет размеры диалогового окна, в зависимости
        от количества содержимого в HTML таблице. Заданы пороги минимального и максимального значения окна,
        что позволяет регулировать размер. Так же, вызываемое окно центрированно на экране пользователя.
        """
        # Получаем размеры таблицы после обновления содержимого
        table_width = self.textEdit.document().size().width()  # Ширина таблицы
        table_height = self.textEdit.document().size().height()  # Высота таблицы
        # print(f"Ширина таблицы: {table_width}, Высота таблицы: {table_height}")  # Вывод размеров таблицы
        # Устанавливаем размеры диалогового окна на основе размеров таблицы, преобразовав их в целые числа
        new_width = min(max(450, int(table_width) + 60), 1200)  # Устанавливаем ширину, ограниченную максимумом
        new_height = min(max(120, int(table_height) + 75), 700)  # Устанавливаем высоту, ограниченную максимумом
        self.resize(new_width, new_height)  # Устанавливаем размер диалогового окна
        # Центрируем окно на экране
        desktop = QDesktopWidget().availableGeometry()  # Получаем доступные размеры рабочего стола
        x = (desktop.width() - self.width()) // 2  # Вычисляем позицию по оси X
        y = (desktop.height() - self.height()) // 2  # Вычисляем позицию по оси Y
        self.move(x, y)  # Перемещаем диалоговое окно в центр экрана
    # --------------</editor-fold>--------------------------------------------------------------------------------------

# --------------<editor-fold desc="Точка входа в приложение">-----------------------------------------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)  # Создание экземпляра QApplication
    dlg = YourMainWindowClass()  # Создание экземпляра диалога
    dlg.show()  # Отображение диалога
    sys.exit(app.exec_())  # Запуск приложения

# Точка входа в приложение
if __name__ == "__main__":
    main()  # Запуск функции main при запуске скрипта
# --------------</editor-fold>------------------------------------------------------------------------------------------