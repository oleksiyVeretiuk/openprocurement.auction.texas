*** Keywords ***

Підготувати клієнт для ${user_index} користувача
    ${user_id}=  Get Variable Value         ${USERS_ids[${user_index}]}
    Open Browser  https://prozorro.sale/    ${BROWSER}  ${user_id}
    Set Window Position                     @{USERS['${user_id}']['position']}
    Set Window Size                         @{USERS['${user_id}']['size']}


Залогуватись ${user_index} користувачем
    ${user_id}=  Get Variable Value               ${USERS_ids[${user_index}]}
    Go to                                         ${USERS['${user_id}']['login_url']}
    Wait Until Page Contains                      Дякуємо за використання електронної торгової системи ProZorro.Продажі
    Highlight Elements With Text On Time          Так
    Capture Page Screenshot
    Click Element                                 confirm
    Wait Until Page Contains                      Очікується початок аукціону
    Highlight Elements With Text On Time          Очікується початок аукціону


Переключити мову для учасника ${user_id}
    Switch Browser  ${user_id}
    sleep                      1s
    Click Element              xpath=(//div[@class='clock-container__burger-icon'])
    Click Element              xpath=(//label[contains(text(),'Українська')])
    Wait Until Page Contains   Крок зростання торгів
    Click Element              xpath=(//label[contains(text(),'Русский')])
    Wait Until Page Contains   Шаг увеличение торгов
    Click Element              xpath=(//label[contains(text(),'English')])
    Wait Until Page Contains   Step auction of Bid
    Click Element              xpath=(//div[@class='clock-container__burger-icon'])
    sleep                      1s


Переключитись на ${user_index} учасника
    ${user_index}=  Evaluate  ${user_index}-1
    ${user_id}=  Get Variable Value  ${USERS_ids[${user_index}]}
    Switch Browser  ${user_id}


Погодитись на запропоновану ставку
    Wait Until Page Contains Element    xpath=(//button[contains(text(),'Accept')])
    ${bid_amount}=  Get Text            xpath=(//h3[@class='approval-mount'])
    Set Suite Variable                  ${bid_amount}
    Click Element                       xpath=(//button[contains(text(),'Accept')])


Обрати ставку з випадаючого меню
    Wait Until Page Contains Element   xpath=(//input[@class='search arrow-false'])
    Click Element                      xpath=(//input[@class='search arrow-false'])
    ${list_values}=  Get WebElements   xpath=(//li[@class='autocomplete-result'])
    ${value}=  Evaluate  random.choice($list_values)  modules=random
    ${bid_amount}=  Get Text           ${value}
    ${bid_amount}=  format_amount     ${bid_amount}
    Set Suite Variable                 ${bid_amount}
    Click Element                      ${value}
    Click Element                      xpath=(//button[contains(text(),'Announce')])
