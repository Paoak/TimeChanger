> ## В будничный, рабочий, день появилась острая необходимость в автоматизации некоторого процесса для коллег, в связи с чем и был написан данный скрипт.


# Data Changer v2.3

## Описание
Приложение позволяет обрабатывать изображения в формате JPG и соответствующие JSON файлы, меняя дату и время файлов.
## Функциональность
- Поиск JPG изображений и соответствующих JSON файлов в выбранной директории.
- Выбор очередности обработки пар файлов JPG/JSON.
- Обновление метаданных изображений EXIF (дата создания и дата цифровой обработки).
- Обновление содержимого и свойств JSON файлов.
- Изменение временных меток файлов на основе заданной пользователем даты и времени.
- Переименование изображений и JSON файлов на основании новой даты и времени.
- Поддержка случайного выбора времени в заданном диапазоне.
- Уведомления о ходе обработки и статусе выполнения через лог.

## Использование
**Предполагается, что используется .exe файл.**

1. Укажите путь к папке с файлами.
2. Установите дату и время отсчёта.
3. Задайте шаг в минутах между файлами (число берётся случайным образом из заданного диапазона "От"/"До").
4. При необходимости переопределите очередность обработки в таблице (по умолчанию — от меньшего выдела к большему).
5. Проверьте журнал событий на наличие предупреждений и ошибок.
6. Запустите программу, нажав "Выполнить", и дождитесь её завершения. Результатом будет диалоговое окно с HTML таблицей-отчётом.


## Подробнее
Обратите внимание, что программа чувствительна к сигнатуре названий файлов. Обычно предоставляемые файлы имеют вид: `1_0_10_13_4_20240101_070000_6.json`. Если открыть файл, станет ясна структура названия. Например:

```json
{
  "subrf": 11,
  "subrf_name": "Архангельская область",
  "ln": 1,
  "ln_name": "Обозерское",
  "uln": 0,
  "luch": 10,
  "luch_name": "Турчасовский",
  "kv": 13,
  "vid": 4,
  // ...
  "date": "2024.01.01 07:00:00",
  "tax_id": 6
}
```
Ключевые элементы в названии файла — это 4-й, 5-й, 6-й и 7-й элементы:

4 элемент — квартал (13 в названии файла и "kv": 13 в JSON).
5 элемент — выдел (4 в названии файла и "vid": 4 в JSON).
6 и 7 элементы — дата и время соответственно (20240101_070000 в названии файла и "date":"2024.01.01 07:00:00" в JSON).

> (Выдел - минимальная хозяйственная единица лесного фонда, часть лесного квартала. В один выдел объединяются участки леса, сходные по породному составу, возрасту, полноте, другим показателям.)

Файлы идут парами: изображение (JPG) и выгрузка координат (JSON), поэтому файл JPG также имеет аналогичную сигнатуру. Чтобы изменить время и дату файлов, необходимо также изменить дату/время в свойствах файлов. Для JPG меняются метаданные (EXIF), а для JSON — содержимое.


## Интерфейс представлен в виде диалогового окна, включающего три основных элемента:

### Верхняя часть:

Строка для указания пути к папке с файлами и кнопка для открытия файлового менеджера.
Панель для настройки даты и времени. Дата и время будут отправной точкой для первого файла в очереди. Интервалы "От" и "До" будут использоваться для добавления случайного времени к отправной точке.

### Средняя часть:

Таблица с пятью колонками: "Выдел", "Порядок обработки", "JPG файл", "JSON файл", и "Время на выдел".
Таблица заполняется автоматически после указания пути к папке с файлами. Обработка пар файлов осуществляется от меньшего к большему выделу.

### Нижняя часть:

"Журнал событий", скрытый прогресс-бар, а также кнопки: "Очистить журнал", "Прервать", "Выполнить", "Выход".
В журнале отображается информация о предупреждениях, ходе обработки и ошибки. Кнопка "Очистить журнал" очищает все записи.
Работа программы
Программа принимает на вход путь к папке, в которой хранятся файлы. Она проверяет сигнатуру названия и формирует списки для JPG и JSON файлов, которые сортируются по кварталам и выделам. После этого программа собирает пары файлов, отображая их в таблице.

## Нажатие кнопки "Выполнить" запускает обработку файлов согласно установленным значениям. Ход выполнения отражается в журнале событий, а результат — в виде диалогового окна с HTML таблицей-отчётом, содержащей детали выполнения и возможные ошибки.
