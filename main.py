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
from selenium.common.exceptions import (
    NoAlertPresentException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ADD_BUTTON = '//*[@id="timeSheet_head"]/div/a'
ENTRY_ROWS = "//tr[starts-with(@id, 'timeSheetEntry')]"
# Ô tích "Erase Entry" trong hộp thoại sửa entry
ERASE_CHECKBOX = (
    "//input[@type='checkbox' and (@id='erase' or @name='erase')]"
    " | //label[contains(normalize-space(.), 'Erase Entry')]//input[@type='checkbox']"
    " | //input[@type='checkbox' and @id=//label[contains(normalize-space(.),"
    " 'Erase Entry')]/@for]"
)
# Nút sửa trong từng dòng entry (thử lần lượt các kiểu thường gặp của Kimai)
EDIT_LINKS = (
    ".//a[contains(@onclick, 'editRecord')]",
    ".//img[contains(translate(@title, 'EDIT', 'edit'), 'edit')]/ancestor::a[1]",
    ".//img[contains(@src, 'edit')]/ancestor::a[1]",
)
POLL = 0.1  # Kiểm tra trang mỗi 0.1 giây thay vì ngủ cố định
SETTLE = 0.3  # Nghỉ rất ngắn để trang kịp xử lý sự kiện JavaScript


def wait_for(driver, timeout, condition):
    return WebDriverWait(driver, timeout, poll_frequency=POLL).until(condition)


def get_timeout(config):
    # time_sleep_duration giờ là thời gian chờ TỐI ĐA; xong sớm thì đi tiếp ngay
    return max(float(config.get("time_sleep_duration", 10)), 10)


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


def to_minutes(value):
    """'08:30' / '8:30:00' -> số phút trong ngày; None nếu không đọc được."""
    try:
        hour, minute = value.strip().split(":")[:2]
        return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        return None


def read_day_entries(driver, date_value):
    """Các entry đang hiển thị của một ngày: [{'id', 'start', 'end'}] (start/end = phút)."""
    entries = []
    for row in driver.find_elements("xpath", ENTRY_ROWS):
        cells = row.find_elements("xpath", "./td")
        if len(cells) >= 4 and normalize_text(cells[1].text) == date_value:
            entries.append(
                {
                    "id": row.get_attribute("id"),
                    "start": to_minutes(cells[2].text),
                    "end": to_minutes(cells[3].text),
                }
            )
    return entries


def plan_day(entries, slots):
    """So sánh entry hiện có với các khung giờ cần điền của một ngày.

    - Entry khớp đúng một khung giờ: giữ lại (mỗi khung chỉ giữ 1 entry).
    - Entry trùng lặp hoặc chồng giờ với khung cần điền: xóa.
    - Entry không đụng khung giờ nào (ví dụ OT buổi tối): để nguyên.
    Trả về (danh sách entry cần xóa, danh sách khung giờ còn thiếu cần thêm).
    """
    kept = set()
    to_delete = []
    for entry in entries:
        start, end = entry["start"], entry["end"]
        if start is None or end is None:
            continue
        exact = next(
            (i for i, (s, e) in enumerate(slots) if (s, e) == (start, end) and i not in kept),
            None,
        )
        if exact is not None:
            kept.add(exact)
        elif any(start < e and s < end for s, e in slots):
            to_delete.append(entry)
    missing = [i for i in range(len(slots)) if i not in kept]
    return to_delete, missing


def format_minutes(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def open_add_dialog(driver, timeout):
    wait_for(driver, timeout, EC.element_to_be_clickable(("xpath", ADD_BUTTON))).click()
    wait_for(driver, timeout, EC.visibility_of_element_located(("xpath", PROJECT_SELECT)))


def wait_activity_ready(driver, timeout, activity):
    """Chờ danh sách activity tải xong theo project vừa chọn."""
    if activity:
        wanted = normalize_text(activity)

        def condition(d):
            return any(t == wanted for _, t in get_options(d, ACTIVITY_SELECT))
    else:

        def condition(d):
            return d.find_elements(
                "xpath", f"{ACTIVITY_SELECT}/option[{DEFAULT_ACTIVITY_INDEX}]"
            )

    try:
        wait_for(driver, timeout, condition)
    except TimeoutException:
        pass  # choose_option sẽ báo lỗi kèm danh sách activity hiện có
    time.sleep(SETTLE)


def submit_form(driver, element):
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
        element,
    )


def accept_alert(driver):
    try:
        driver.switch_to.alert.accept()
    except NoAlertPresentException:
        pass


def wait_dialog_closed(driver, timeout):
    """Chờ hộp thoại thêm/sửa đóng lại sau khi bấm OK."""
    wait_for(driver, timeout, EC.invisibility_of_element_located(("xpath", PROJECT_SELECT)))
    time.sleep(SETTLE)


def fill_entry(driver, timeout, date_value, start_time, end_time, project, activity):
    open_add_dialog(driver, timeout)

    choose_option(driver, PROJECT_SELECT, project, DEFAULT_PROJECT_INDEX)
    wait_activity_ready(driver, timeout, activity)
    choose_option(driver, ACTIVITY_SELECT, activity, DEFAULT_ACTIVITY_INDEX)

    send_keys_to_field(driver, '//*[@id="start_day"]', date_value)
    send_keys_to_field(driver, '//*[@id="end_day"]', date_value)
    send_keys_to_field(driver, '//*[@id="start_time"]', start_time)
    send_keys_to_field(driver, '//*[@id="end_time"]', end_time)
    submit_form(driver, driver.find_element("xpath", '//*[@id="end_time"]'))
    accept_alert(driver)
    wait_dialog_closed(driver, timeout)
    print(f"Đã điền {date_value} {normalize_time(start_time)}-{normalize_time(end_time)}")


def login(config):
    driver = create_driver(config["url"], config["driver"])
    timeout = get_timeout(config)

    username_field = wait_for(
        driver, timeout, EC.presence_of_element_located(("xpath", '//*[@id="kimaiusername"]'))
    )
    password_field = driver.find_element("xpath", '//*[@id="kimaipassword"]')
    username_field.send_keys(config["username"])
    password_field.send_keys(config["p" + "assword"])
    password_field.submit()

    wait_for(driver, timeout, EC.element_to_be_clickable(("xpath", ADD_BUTTON)))
    time.sleep(SETTLE)  # Chờ danh sách entry hiển thị
    return driver


def fill_timesheet(config):
    timeout = get_timeout(config)
    project = config.get("project", "")
    activity = config.get("activity", "")
    holiday_dates = parse_holidays(config.get("holidays", []))

    current_date = datetime.strptime(config["start_day"], "%d.%m.%Y").replace(tzinfo=UTC)
    last_date = datetime.strptime(config["end_day"], "%d.%m.%Y").replace(tzinfo=UTC)

    slot_times = [
        (config["start_time_morning"], config["end_time_morning"]),
        (config["start_time_afternoon"], config["end_time_afternoon"]),
    ]
    slots = [(to_minutes(start), to_minutes(end)) for start, end in slot_times]
    if any(start is None or end is None or start >= end for start, end in slots):
        raise ValueError("Giờ bắt đầu/kết thúc không hợp lệ (định dạng HH:MM:SS).")

    driver = login(config)

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

        # Kiểm tra trước: xóa entry trùng lặp / chồng giờ, giữ entry đã đúng
        to_delete, missing = plan_day(read_day_entries(driver, date_value), slots)
        for entry in to_delete:
            print(
                f"Xóa entry trùng/chồng giờ {date_value} "
                f"{format_minutes(entry['start'])}-{format_minutes(entry['end'])}"
            )
            erase_entry(driver, timeout, driver.find_element("id", entry["id"]))

        for index in missing:
            start_time, end_time = slot_times[index]
            fill_entry(
                driver,
                timeout,
                date_value,
                start_time,
                end_time,
                project,
                activity,
            )
        if not to_delete and not missing:
            print(f"Ngày {date_value} đã đủ, bỏ qua")

        current_date += timedelta(days=1)


def fetch_options(config):
    """Đăng nhập, đọc danh sách project và activity tương ứng, lưu vào options.json."""
    timeout = get_timeout(config)
    driver = login(config)

    def activity_html(d):
        return d.find_element("xpath", ACTIVITY_SELECT).get_attribute("innerHTML")

    try:
        open_add_dialog(driver, timeout)
        project_names = [text for _, text in get_options(driver, PROJECT_SELECT)]
        projects = []
        for name in project_names:
            before = activity_html(driver)
            choose_option(driver, PROJECT_SELECT, name, DEFAULT_PROJECT_INDEX)
            try:  # Chờ activity đổi theo project (tối đa 3 giây nếu giống project trước)
                wait_for(driver, 3, lambda d: activity_html(d) != before)
            except TimeoutException:
                pass
            time.sleep(SETTLE)
            activities = [text for _, text in get_options(driver, ACTIVITY_SELECT)]
            projects.append({"name": name, "activities": activities})
            print(f"{name}: {len(activities)} activity")
    finally:
        driver.quit()

    with OPTIONS_PATH.open("w", encoding="utf-8") as f:
        json.dump({"projects": projects}, f, indent=4, ensure_ascii=False)
    print(f"Đã lưu {len(projects)} project vào {OPTIONS_PATH.name}")


def parse_delete_days(values):
    """Nhận danh sách ngày 'DD.MM.YYYY' hoặc khoảng 'DD.MM.YYYY-DD.MM.YYYY'."""
    days = []
    for value in values:
        for part in value.replace(",", " ").split():
            start, _, end = part.partition("-")
            try:
                first = datetime.strptime(start, "%d.%m.%Y")
                last = datetime.strptime(end or start, "%d.%m.%Y")
            except ValueError as exc:
                raise ValueError(
                    f"Ngày cần xóa không hợp lệ: {part!r} "
                    "(DD.MM.YYYY hoặc DD.MM.YYYY-DD.MM.YYYY)"
                ) from exc
            while first <= last:
                days.append(first.strftime("%d.%m.%Y"))
                first += timedelta(days=1)
    return list(dict.fromkeys(days))


def find_rows_of_day(driver, date_value):
    rows = []
    for row in driver.find_elements("xpath", ENTRY_ROWS):
        cells = row.find_elements("xpath", "./td")
        if len(cells) >= 4 and normalize_text(cells[1].text) == date_value:
            rows.append(row)
    return rows


def find_edit_link(row):
    for xpath in EDIT_LINKS:
        links = row.find_elements("xpath", xpath)
        if links:
            return links[0]
    raise RuntimeError("Không tìm thấy nút sửa (edit) trong dòng entry.")


def erase_entry(driver, timeout, row):
    """Mở hộp thoại sửa của entry, tích 'Erase Entry' rồi bấm OK."""
    find_edit_link(row).click()
    checkbox = wait_for(
        driver, timeout, EC.element_to_be_clickable(("xpath", ERASE_CHECKBOX))
    )
    if not checkbox.is_selected():
        checkbox.click()
    submit_form(driver, checkbox)
    accept_alert(driver)
    # Chờ danh sách entry tải lại (dòng vừa xóa biến mất)
    def row_gone(_driver):
        try:
            return not row.is_displayed()
        except StaleElementReferenceException:
            return True

    wait_for(driver, timeout, row_gone)
    time.sleep(SETTLE)


def delete_days(config, days):
    timeout = get_timeout(config)
    driver = login(config)
    total = 0
    for date_value in days:
        deleted = 0
        for _ in range(50):  # Giới hạn an toàn
            try:
                rows = find_rows_of_day(driver, date_value)
                if not rows:
                    break
                erase_entry(driver, timeout, rows[0])
                deleted += 1
            except StaleElementReferenceException:
                time.sleep(SETTLE)  # Danh sách vừa tải lại, đọc lại
        if deleted:
            print(f"Đã xóa {deleted} entry ngày {date_value}")
        else:
            print(f"Không có entry nào ngày {date_value} trong danh sách đang hiển thị")
        total += deleted
    print(f"Tổng cộng đã xóa {total} entry")


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
    parser.add_argument(
        "--delete",
        nargs="+",
        metavar="NGAY",
        help="Xóa toàn bộ entry của các ngày (DD.MM.YYYY hoặc DD.MM.YYYY-DD.MM.YYYY)",
    )
    args = parser.parse_args(argv)

    config = load_config()
    if args.delete:
        delete_days(config, parse_delete_days(args.delete))
    elif args.fetch_options:
        fetch_options(config)
    else:
        fill_timesheet(config)


if __name__ == "__main__":
    main()
