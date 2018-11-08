*** Settings ***

Documentation  A test suite with a tests for simple tender auction.
Suite setup       Prepare Participants Data
Suite teardown    Close all browsers
Resource       resource.robot

*** Test Cases ***
Authorization of the participants
    Долучитись до аукціону 1 учасником
    Долучитись до аукціону 2 учасником

Test language switching
    Перевірити можливість змінити мову

Waiting for start of round 1
    Почекати 1 min до паузи перед 1 раундом
    Перевірити інформацію про тендер
    Почекати 15s до завершення паузи перед 1 раундом

Accept the offer by the first participant
    Переключитись на 1 учасника
    Погодитись на запропоновану ставку

Waiting for start of round 2
    Почекати 2s до паузи перед 2 раундом
    Почекати 15s до завершення паузи перед 2 раундом

Check round 1 results
    Перевірити результати 1 раунду

Increase the offer price by the first participant
    Обрати ставку з випадаючого меню

Waiting for start of round 3
    Почекати 2s до паузи перед 3 раундом
    Почекати 15s до завершення паузи перед 3 раундом

Check round 2 results
    Перевірити результати 2 раунду

Accept the offer by the second participant
    Переключитись на 2 учасника
    Погодитись на запропоновану ставку

Waiting for start of round 4
    Почекати 2s до паузи перед 4 раундом
    Почекати 15s до завершення паузи перед 4 раундом

Check round 3 results
    Перевірити результати 3 раунду

Waiting for end of auction
    Дочекатистись до завершення аукціону

Check the Announcement results section
    Перевірити результати аукціону
