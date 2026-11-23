import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Khi đóng gói thành .exe (PyInstaller), file cấu hình nằm cạnh file .exe
FROZEN = getattr(sys, "frozen", False)
PROJECT_DIR = (
    Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
)
CONFIG_PATH = PROJECT_DIR / "account.json"
OPTIONS_PATH = PROJECT_DIR / "options.json"

# Tránh lỗi in tiếng Việt khi console không hỗ trợ UTF-8
if sys.stdout is not None:
    sys.stdout.reconfigure(errors="replace")

PROJECT_SELECT = '//*[@id="add_edit_timeSheetEntry_projectID"]'
ACTIVITY_SELECT = '//*[@id="add_edit_timeSheetEntry_activityID"]'
# Vị trí mặc định (cách cũ) khi chưa cấu hình "project"/"activity" theo tên
DEFAULT_PROJECT_INDEX = 1
DEFAULT_ACTIVITY_INDEX = 10


def ensure_venv():
    venv_dir = PROJECT_DIR / ".venv"
    requirements_file = PROJECT_DIR / "requirements.txt"
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


if not FROZEN:
    ensure_venv()
from selenium import webdriver
from selenium.webdriver.common.keys import Keys


def create_driver(url, type_driver):
    if type_driver == "chrome":
        driver = webdriver.Chrome()
    elif type_driver == "edge":
        driver = webdriver.Edge()
    else:
        raise ValueError(f"Driver không hỗ trợ: {type_driver!r} (chrome hoặc edge)")
    driver.get(url)
    return driver


def send_keys_to_field(driver, field_xpath, value):
    field = driver.find_element("xpath", field_xpath)
    field.click()  # Click to focus on the field
    field.send_keys(Keys.CONTROL + "a")  # Select all existing text
    field.send_keys(value)


def normalize_time(value):
    return value.strip()[:5]


def normalize_text(value):
    return " ".join((value or "").split())


def get_options(driver, select_xpath):
    """Trả về danh sách (element, text) của các option có chữ trong một select."""
    options = driver.find_elements("xpath", f"{select_xpath}//option")
    return [(o, normalize_text(o.text)) for o in options if normalize_text(o.text)]


def choose_option(driver, select_xpath, name, default_index):
    """Chọn option theo tên hiển thị; nếu không cấu hình tên thì chọn theo vị trí mặc định."""
    if not name:
        driver.find_element("xpath", f"{select_xpath}/option[{default_index}]").click()
        return

    wanted = normalize_text(name)
    options = get_options(driver, select_xpath)
    for option, text in options:
        if text == wanted:
            option.click()
            return
    available = ", ".join(text for _, text in options)
    raise ValueError(f"Không tìm thấy {wanted!r}. Các lựa chọn hiện có: {available}")


def parse_holidays(holidays):
    """Chuyển danh sách ngày nghỉ lễ (DD.MM.YYYY) thành set các date."""
    parsed = set()
    for value in holidays or []:
        try:
            parsed.add(datetime.strptime(value.strip(), "%d.%m.%Y").date())
        except ValueError as exc:
            raise ValueError(
                f"Ngày nghỉ lễ không hợp lệ: {value!r} (định dạng DD.MM.YYYY)"
            ) from exc
    return parsed


def get_existing_entries(driver):
    rows = driver.find_elements("xpath", "//tr[starts-with(@id, 'timeSheetEntry')]")
    entries = set()
    for row in rows:
        cells = row.find_elements("xpath", "./td")
        if len(cells) >= 4:
            entries.add(
                (
                    normalize_text(cells[1].text),
                    normalize_time(cells[2].text),
                    normalize_time(cells[3].text),
                )
            )
    return entries


def open_add_dialog(driver, time_sleep_duration):
    add_button = driver.find_element("xpath", '//*[@id="timeSheet_head"]/div/a')
    add_button.click()
    time.sleep(time_sleep_duration)


def fill_entry(
    driver, time_sleep_duration, date_value, start_time, end_time, project, activity
):
    open_add_dialog(driver, time_sleep_duration)

    choose_option(driver, PROJECT_SELECT, project, DEFAULT_PROJECT_INDEX)
    time.sleep(time_sleep_duration)  # Chờ danh sách activity tải theo project

    choose_option(driver, ACTIVITY_SELECT, activity, DEFAULT_ACTIVITY_INDEX)
    time.sleep(time_sleep_duration)

    send_keys_to_field(driver, '//*[@id="start_day"]', date_value)
    send_keys_to_field(driver, '//*[@id="end_day"]', date_value)
    send_keys_to_field(driver, '//*[@id="start_time"]', start_time)
    time.sleep(time_sleep_duration)
    end_time_field = driver.find_element("xpath", '//*[@id="end_time"]')
    end_time_field.click()
    end_time_field.send_keys(Keys.CONTROL + "a")
    end_time_field.send_keys(end_time)
    driver.execute_script(
        """
        const field = arguments[0];
        const form = field.form || field.closest("form");
        if (!form) {
            throw new Error("Cannot submit: #end_time is not inside a form.");
        }
        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
        """,
        end_time_field,
    )

    time.sleep(time_sleep_duration)


def login(config):
    driver = create_driver(config["url"], config["driver"])
    time_sleep_duration = config["time_sleep_duration"]
    time.sleep(time_sleep_duration)  # Wait for the page to load

    username_field = driver.find_element("xpath", '//*[@id="kimaiusername"]')
    password_field = driver.find_element("xpath", '//*[@id="kimaipassword"]')
    username_field.send_keys(config["username"])
    password_field.send_keys(config["p" + "assword"])
    password_field.submit()

    time.sleep(time_sleep_duration)  # Wait for the page to load
    return driver


def fill_timesheet(config):
    time_sleep_duration = config["time_sleep_duration"]
    project = config.get("project", "")
    activity = config.get("activity", "")
    holiday_dates = parse_holidays(config.get("holidays", []))

    current_date = datetime.strptime(config["start_day"], "%d.%m.%Y").replace(tzinfo=UTC)
    last_date = datetime.strptime(config["end_day"], "%d.%m.%Y").replace(tzinfo=UTC)

    driver = login(config)
    existing_entries = get_existing_entries(driver)

    while current_date <= last_date:
        # Only fill for weekdays (Monday to Friday)
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        # Bỏ qua các ngày nghỉ lễ được khai báo trong account.json
        if current_date.date() in holiday_dates:
            print(f"Bỏ qua ngày nghỉ lễ: {current_date.strftime('%d.%m.%Y')}")
            current_date += timedelta(days=1)
            continue
        date_value = current_date.strftime("%d.%m.%Y")
        for start_time, end_time in (
            (config["start_time_morning"], config["end_time_morning"]),
            (config["start_time_afternoon"], config["end_time_afternoon"]),
        ):
            entry = (date_value, normalize_time(start_time), normalize_time(end_time))
            if entry in existing_entries:
                continue

            fill_entry(
                driver,
                time_sleep_duration,
                date_value,
                start_time,
                end_time,
                project,
                activity,
            )
            existing_entries.add(entry)

        current_date += timedelta(days=1)


def fetch_options(config):
    """Đăng nhập, đọc danh sách project và activity tương ứng, lưu vào options.json."""
    time_sleep_duration = config["time_sleep_duration"]
    driver = login(config)
    try:
        open_add_dialog(driver, time_sleep_duration)
        project_names = [text for _, text in get_options(driver, PROJECT_SELECT)]
        projects = []
        for name in project_names:
            choose_option(driver, PROJECT_SELECT, name, DEFAULT_PROJECT_INDEX)
            time.sleep(time_sleep_duration)  # Chờ activity tải theo project
            activities = [text for _, text in get_options(driver, ACTIVITY_SELECT)]
            projects.append({"name": name, "activities": activities})
            print(f"{name}: {len(activities)} activity")
    finally:
        driver.quit()

    with OPTIONS_PATH.open("w", encoding="utf-8") as f:
        json.dump({"projects": projects}, f, indent=4, ensure_ascii=False)
    print(f"Đã lưu {len(projects)} project vào {OPTIONS_PATH.name}")


def load_config():
    with CONFIG_PATH.open(encoding="utf-8-sig") as f:
        return json.load(f)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tự động điền timesheet")
    parser.add_argument(
        "--fetch-options",
        action="store_true",
        help="Chỉ lấy danh sách project/activity từ hệ thống và lưu vào options.json",
    )
    args = parser.parse_args(argv)

    config = load_config()
    if args.fetch_options:
        fetch_options(config)
    else:
        fill_timesheet(config)


if __name__ == "__main__":
    main()
