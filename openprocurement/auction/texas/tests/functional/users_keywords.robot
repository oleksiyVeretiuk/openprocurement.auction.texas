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
    Wait Until Page Contains                      Waiting for start of auction
    Highlight Elements With Text On Time          Waiting for start of auction


Переключитись на ${user_index} учасника
    ${user_index}=  Evaluate  ${user_index}-1
    ${user_id}=  Get Variable Value  ${USERS_ids[${user_index}]}
    Switch Browser  ${user_id}


Погодитись на запропоновану ставку
    Wait Until Page Contains Element    xpath=(//button[contains(text(),'Accept')])
    ${bid_amount}=  Get Text            xpath=(//h3[@class='approval-mount'])
    Set Suite Variable                  ${bid_amount}
    Click Element                       xpath=(//button[contains(text(),'Accept')])


Обрати cтавку з випадаючого меню
    Wait Until Page Contains Element   xpath=(//i[@class='dropdown icon'])
    Click Element                      xpath=(//i[@class='dropdown icon'])
    ${list_values}=  Get WebElements   xpath=(//div[@class='menu visible']/div[@class='item'])
    ${value}=  Evaluate  random.choice($list_values)  modules=random
    ${bid_amount}=  Get Text           ${value}
    Set Suite Variable                 ${bid_amount}
    Click Element                      ${value}
    Click Element                      xpath=(//button[contains(text(),'Announce')])
