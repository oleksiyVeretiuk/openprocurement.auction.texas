*** Settings ***

Documentation  A test suite with a tests for texas auction.
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

Increase the offer price by the first participant
    Переключитись на 1 учасника
    Обрати ставку з випадаючого меню

Waiting for start of round 2
    Почекати 2s до паузи перед 2 раундом
    Почекати 15s до завершення паузи перед 2 раундом

Check the results of round 1
    Перевірити результати 1 раунду

Accept the offer by the first participant
    Погодитись на запропоновану ставку

Waiting for start of round 3
    Почекати 2s до паузи перед 3 раундом
    Почекати 15s до завершення паузи перед 3 раундом

Check the results of round 2
    Перевірити результати 2 раунду

Waiting for end of auction
    Дочекатистись до завершення аукціону

Check the Announcement results section
    Перевірити результати аукціону  Bidder 1