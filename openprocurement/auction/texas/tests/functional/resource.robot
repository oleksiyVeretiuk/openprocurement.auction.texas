*** Settings ***
Library        SeleniumLibrary
Library        Collections
Library        DebugLibrary
Resource       users_keywords.robot
Library        openprocurement.auction.texas.tests.functional.service_keywords

*** Variables ***
${USERS}

*** Keywords ***

Prepare Participants Data
    ${TENDER}=  prepare_tender_data
    Set Global Variable   ${TENDER}
    ${USERS}=  prepare_users_data   ${TENDER}
    ${USERS_ids}=  Convert to List  ${USERS}
    Reverse List  ${USERS_ids}
    Set Global Variable  ${USERS}
    Set Global Variable  ${USERS_ids}
    Log  ${USERS['${USERS_ids[0]}']['login_url']}  WARN
    Log  ${USERS['${USERS_ids[1]}']['login_url']}  WARN


Долучитись до аукціону ${user_index} учасником
  ${user_index}=  Evaluate  ${user_index}-1
  Підготувати клієнт для ${user_index} користувача
  Залогуватись ${user_index} користувачем
  Перевірити інформацію з меню


Перевірити інформацію з меню
    sleep                      1s
    Click Element              xpath=(//div[@class='clock-container__burger-icon'])
    Wait Until Page Contains   Tender Description
    Highlight Elements With Text On Time    Tender Description
    Wait Until Page Contains   Browser ID
    Highlight Elements With Text On Time    Browser ID
    Wait Until Page Contains   Session ID
    Highlight Elements With Text On Time    Session ID
    Wait Until Page Contains   Стартова ціна
    Highlight Elements With Text On Time    Стартова ціна
    Capture Page Screenshot
    Click Element              xpath=(//div[@class='clock-container__burger-icon'])
    sleep                      1s


Перевірити можливість змінити мову
    :FOR    ${user_id}    IN    @{USERS}
    \   Переключити мову для учасника ${user_id}


Перевірити інформацію про тендер
    Page Should Contain   ${TENDER['title']}                    # tender title
    Page Should Contain   ${TENDER['procuringEntity']['name']}  # tender procuringEntity name


Почекати ${timeout} до паузи перед ${round_id} раундом
    Wait Until Page Contains    Waiting for start of round    ${timeout}


Почекати ${timeout} до завершення паузи перед ${round_id} раундом
    Wait Until Page Contains    until the round ends    ${timeout}


Перевірити результати ${index} раунду
    Element Should Contain    xpath=(//div[@class='list-rounds-container']//div[${index}]/div/div[2]/h4)    ${bid_amount}


Дочекатистись до завершення аукціону
    [Arguments]    ${timeout}=4 min
    Wait Until Page Contains      Auction is completed by the licitator   ${timeout}
    Wait Until Page Contains      Sold


Перевірити результати аукціону
    [Arguments]    ${winner}
    Wait Until Page Contains      Announcement
    Element Should Contain    xpath=(//h3[@class='word-winner'])    ${winner}
