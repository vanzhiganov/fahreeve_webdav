Финальный отчет о проделанной работе
========================================


Общие сведения
--------------

Python WebDAV сервер

Фахреев Эльдар 104

[ссылка на Wiki проекта](http://wiki.cs.hse.ru/Python_WebDAV_%D1%81%D0%B5%D1%80%D0%B2%D0%B5%D1%80_(%D0%BF%D1%80%D0%BE%D0%B5%D0%BA%D1%82))

[ссылка на GitHub](https://github.com/cs-hse-projects/fahreeve_webdav)


Постановка задачи
-----------------

### Условие задачи

Итоговый результат будет представляет из себя webdav сервер, оформленный в виде пакета pip. На основе этого сервера создана виртуальная файловая система для аудио коллекции.


Реализация формальных критериев
-------------------------------

Перечислить список формальных критериев из Wiki проекта, и для каждого критерия -- 
указать реализован ли он. Если в постановку задачи были внесены согласованные с ментором изменения,
то указать, вместо каких критериев эти изменения будут засчитаны.


1. 4 балла. Реализация минимального набора команд WebDAV и тестового сервера. -- реализовано
2. 5 баллов. Реализация полного набора команд, необходимого для доступа к серверу штатными средствами проводника Windows и KDE. реализовано для linux. Было решено не тестировать работу на windows
3. 8 баллов. Реализация виртуальной файловой системы
аудиоколлекции.  -- реализовано
4. 9 баллов. Поддержка записи в виртуальную файловую системы аудиоколлекции с изменением IDv3 тегов в соответсвии с иерархией файловой системы. -- не реализовано
5. Оформление результата работы в виде пакета для pip: +1 балл. -- реализовано


Работа над проектом
-------------------

### Особенности реализации

Описать, как реализован программный продукт.

Используется http.server из стандартной библиотеки python 3. Для него был написан свой HTTPRequestHandler, который поддерживает webdav. Так же был реализован класс для виртуальной файловой системы. Перед стартом сервера, программа сканирует папку и на основе IDv3 тегов формирует виртуальную ФС. При поступлении запросов, сервер использует толко этот класс для работы с ФС. И только когда надо отдать содержимое файла, функция do_GET получает название файла и читает его содержимое с диска. Для конфигурации сервера в консоли реализована работа с ключами.


### Решенные задачи

Описать, с какими трудностями Вы столкнулись в ходе выполнения проекта и как они были преодолены.

В самом начале был написан webdav сервер с поддержкой почти всех методов. Когда начал делать вирутальную файловую систему, то понял, что зря потратил время на полноценную реализацию webdav сервера. Для реализации 3 пункта достаточно было написать методы GET, HEAD, PROPFIND. 


Описание полученного продукта
-----------------------------

### Установка

    pip install musdav

### Использование

создать папку 'files' - дефолтное название  
создать .py файл и вставить в него это:

    from musdav import runserver
    runserver()

запустить файл

    python3 youfile.py --help
