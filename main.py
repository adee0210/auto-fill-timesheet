import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from selenium.webdriver.common.by import By


def ensure_venv():
    project_dir = Path(__file__).resolve().parent
    venv_dir = project_dir / ".venv"
    requirements_file = project_dir / "requirements.txt"
    venv_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    if Path(sys.executable).resolve() != venv_python.resolve():
        if not venv_python.exists():
            subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "-r", str(requirements_file)]
        )
        os.execv(
            str(venv_python),
            [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        )


ensure_venv()

from selenium import webdriver
from selenium.webdriver.common.keys import Keys


def create_driver(url, type_driver):
    if type_driver == "chrome":
        driver = webdriver.Chrome()
    elif type_driver == "edge":
        driver = webdriver.Edge()
    driver.get(url)
    return driver


def send_keys_to_field(driver, field_xpath, value):
    field = driver.find_element("xpath", field_xpath)
    field.click()  # Click to focus on the field
    field.send_keys(Keys.CONTROL + "a")  # Select all existing text
    field.send_keys(value)


def normalize_time(value):
    return value.strip()[:5]


def get_existing_entries(driver):
    rows = driver.find_elements("xpath", "//tr[starts-with(@id, 'timeSheetEntry')]")
    entries = set()
    for row in rows:
        cells = row.find_elements("xpath", "./td")
        if len(cells) >= 4:
            entries.add(
                (
                    " ".join(cells[1].text.split()),
                    normalize_time(cells[2].text),
                    normalize_time(cells[3].text),
                )
            )
    return entries


def fill_entry(driver, time_sleep_duration, date_value, start_time, end_time):
    add_button = driver.find_element("xpath", '//*[@id="timeSheet_head"]/div/a')
    add_button.click()
    time.sleep(time_sleep_duration)

    # xpath //*[@id="add_edit_timeSheetEntry_projectID"]/option[1]
    project_option = driver.find_element(
        "xpath", '//*[@id="add_edit_timeSheetEntry_projectID"]/option[1]'
    )
    project_option.click()
    time.sleep(time_sleep_duration)

    activity_option = driver.find_element(
        "xpath", '//*[@id="add_edit_timeSheetEntry_activityID"]/option[10]'
    )
    activity_option.click()
    time.sleep(time_sleep_duration)

    send_keys_to_field(driver, '//*[@id="start_day"]', date_value)
    send_keys_to_field(driver, '//*[@id="end_day"]', date_value)
    send_keys_to_field(driver, '//*[@id="start_time"]', start_time)
    send_keys_to_field(driver, '//*[@id="end_time"]', end_time)
    time.sleep(time_sleep_duration)

    ok_button = driver.find_element(By.CSS_SELECTOR, "#formbuttons > input.btn_ok")

    ok_button.click()
    time.sleep(time_sleep_duration)


def login_and_fill_form(
    url,
    username,
    password,
    time_sleep_duration,
    start_day,
    end_day,
    start_time_morning,
    end_time_morning,
    start_time_afternoon,
    end_time_afternoon,
    driver,
):
    # fill login start day to end day and start time to end time
    driver = create_driver(url, driver)
    time.sleep(time_sleep_duration)  # Wait for the page to load
    # xpath //*[@id="kimaiusername"]
    username_field = driver.find_element("xpath", '//*[@id="kimaiusername"]')

    # xpath pass //*[@id="kimaipassword"]
    password_field = driver.find_element("xpath", '//*[@id="kimaipassword"]')

    # enter value user name_field.send_keys("admin")
    username_field.send_keys(username)
    password_field.send_keys(password)

    # enter password to login
    password_field.submit()

    time.sleep(time_sleep_duration)  # Wait for the page to load
    # fill form start day to end day and start time to end time

    current_date = datetime.strptime(start_day, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    last_date = datetime.strptime(end_day, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    existing_entries = get_existing_entries(driver)

    while current_date <= last_date:
        # current_date.weekday() < 5:  # Only fill for weekdays (Monday to Friday)
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        date_value = current_date.strftime("%d.%m.%Y")
        for start_time, end_time in (
            (start_time_morning, end_time_morning),
            (start_time_afternoon, end_time_afternoon),
        ):
            entry = (
                date_value,
                normalize_time(start_time),
                normalize_time(end_time),
            )
            if entry in existing_entries:
                continue

            fill_entry(
                driver,
                time_sleep_duration,
                date_value,
                start_time,
                end_time,
            )
            existing_entries.add(entry)

        current_date += timedelta(days=1)


with open("account.json", "r") as f:
    config = json.load(f)

login_and_fill_form(
    driver=config["driver"],
    url=config["url"],
    username=config["username"],
    password=config["password"],
    time_sleep_duration=config["time_sleep_duration"],
    start_day=config["start_day"],
    end_day=config["end_day"],
    start_time_morning=config["start_time_morning"],
    end_time_morning=config["end_time_morning"],
    start_time_afternoon=config["start_time_afternoon"],
    end_time_afternoon=config["end_time_afternoon"],
)
