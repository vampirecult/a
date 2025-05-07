import sys
import threading
import io
import time
import csv
import requests
import json
import random

import webbrowser
from datetime import datetime
from urllib.request import urlopen, Request
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QProgressBar, QFileDialog
)
from PyQt5.QtGui import QPixmap, QFont, QTextCursor, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

with open('settings.json', 'r', encoding='utf-8') as f:
    SETTINGS = json.load(f)

CHROME_DRIVER_PATH = SETTINGS['CHROME_DRIVER_PATH']
BOT_TOKEN = SETTINGS['BOT_TOKEN']
CHAT_ID = SETTINGS['CHAT_ID']

USER_AGENTS = SETTINGS['USER_AGENTS']


def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    response = requests.post(url, data=payload)
    return response.status_code == 200

def send_file_to_telegram(file_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    payload = {"chat_id": CHAT_ID}
    files = {'document': open(file_path, 'rb')}
    response = requests.post(url, data=payload, files=files)
    return response.status_code == 200


class ParserThread(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, url, headless):
        super().__init__()
        self.url = url
        self.headless = headless
        self.request_count = 0  # Счетчик запросов для смены User-Agent

    def get_random_user_agent(self):
        """Функция для выбора случайного User-Agent после каждых 100 запросов."""
        self.request_count += 1
        if self.request_count % 100 == 0:  # Меняем User-Agent после 100 запросов
            return random.choice(USER_AGENTS)
        return random.choice(USER_AGENTS)

    def run(self):
        try:
            chrome_options = Options()

            user_agent = self.get_random_user_agent()  # Получаем User-Agent
            self.log.emit(f"🌐 Используем User-Agent: {user_agent}")  # Логирование выбранного User-Agent
            chrome_options.add_argument(f"user-agent={user_agent}")
            if self.headless:
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--disable-gpu")
            else:
                chrome_options.add_argument("--start-maximized")

            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--mute-audio")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
              
            self.log.emit("🚀 Открытие браузера...")
            driver = webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=chrome_options)
            time.sleep(random.uniform(0.8, 3.0))


            self.log.emit(f"🌍 Переход по ссылке: {self.url}")
            driver.get(self.url)
            time.sleep(2)

            self.log.emit("📜 Прокрутка страницы...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            time.sleep(random.uniform(0.8, 3.0))


            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span.NftItemNameContent__name"))
            )
            time.sleep(random.uniform(0.8, 3.0))


            numbers = driver.find_elements(By.CSS_SELECTOR, "span.NftItemNameContent__name")
            self.log.emit(f"📄 Найдено {len(numbers)} номеров")
            time.sleep(random.uniform(0.8, 3.0))


            seen_owner_links = set()
            seen_usernames = set()
            processed_owners = {}
            results = []
            numbers_with_links = []

            count = 1  # Добавляем счетчик

            for number_el in numbers:
                try:
                    number = number_el.text.strip().replace(" ", "")
                    if not number.startswith("+888"):
                        continue
                    self.log.emit(f"🔗 #{count} Поиск ссылки владельца для {number}")  # Логируем с порядковым номером
                    time.sleep(random.uniform(0.8, 3.0))


                    parent_tr = number_el.find_element(By.XPATH, "./ancestor::tr")
                    owner_link_el = parent_tr.find_element(By.XPATH, ".//a[contains(@href, '/user/')]")
                    owner_link = owner_link_el.get_attribute("href")

                    self.log.emit(f"✅ #{count} Владелец найден {owner_link} для {number}")  # Логируем с порядковым номером
                    time.sleep(random.uniform(0.8, 3.0))


                    if owner_link in processed_owners and number in processed_owners[owner_link]:
                        self.log.emit(f"♻️ Повторка: {number} для {owner_link}")
                        continue

                    numbers_with_links.append((number, owner_link))
                    count += 1  # Увеличиваем счетчик
                except Exception as e:
                    self.log.emit(f"⚠️ Ошибка при сборе ссылки: {e}")
                    time.sleep(random.uniform(0.8, 3.0))


            for idx, (number, owner_link) in enumerate(numbers_with_links, start=1):
                try:
                    self.progress.emit(int(idx / len(numbers_with_links) * 100))
                    self.log.emit(f"🔗 Открываю профиль #{idx}: {owner_link}")
                    driver.get(owner_link)
                    time.sleep(random.uniform(0.8, 3.0))


                    if owner_link in seen_owner_links:
                        self.log.emit(f"♻️ Профиль уже обработан: {owner_link}")
                        continue

                    telegram_blocks = driver.find_elements(By.XPATH, "//div[contains(text(), 'Telegram Usernames')]")
                    time.sleep(random.uniform(0.8, 3.0))


                    if not telegram_blocks:
                        formatted_result = f"t.me/{number} | {owner_link} | нет юзернеймов"
                        self.log.emit(f"🚫 Нет юзернеймов для {owner_link}")
                        seen_owner_links.add(owner_link)
                        results.append(formatted_result)
                        continue

                    try:
                        checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox']")
                        if not checkbox.is_selected():
                            checkbox.click()
                            self.log.emit("✅ Чекбокс активирован!")
                    except Exception:
                        pass
                    time.sleep(random.uniform(0.8, 3.0))


                    usernames_elements = driver.find_elements(By.XPATH, "//span[contains(text(), '@')]")
                    usernames = list(set(user.text.strip() for user in usernames_elements))
                    usernames = [u for u in usernames if u not in seen_usernames]
                    seen_usernames.update(usernames)

                    if usernames:
                        self.log.emit(f"✅ Найдены юзернеймы для {owner_link}: {', '.join(usernames)}")
                        formatted_result = f"t.me/{number} | {owner_link} | {','.join(usernames)}"
                    else:
                        self.log.emit(f"🚫 Нет новых юзернеймов для {owner_link}")
                        formatted_result = f"t.me/{number} | {owner_link} | нет юзернеймов"

                    seen_owner_links.add(owner_link)

                    if owner_link not in processed_owners:
                        processed_owners[owner_link] = {number}
                    else:
                        processed_owners[owner_link].add(number)

                    results.append(formatted_result)

                    if idx % 100 == 0:
                        self.log.emit("⏳ Отдых 3 минуты...")
                        time.sleep(180)

                except Exception as e:
                    self.log.emit(f"⚠️ Ошибка при обработке профиля: {e}")
                    time.sleep(random.uniform(0.8, 3.0))


            with open("results.csv", "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Number", "Owner Link", "Usernames"])
                for r in results:
                    writer.writerow(r.split(" | "))

            self.log.emit(f"✅ Сохранено {len(results)} профилей в results.csv")
            time.sleep(random.uniform(0.8, 3.0))


            if results:
                self.log.emit("📨 Отправка файла в Telegram...")
                send_to_telegram("✅ Отпарсил ^_^ Для удобной работы перешлите файл в @fuflyaj1337_bot")
                if send_file_to_telegram("results.csv"):
                    self.log.emit("✅ Файл отправлен в Telegram!")
                else:
                    self.log.emit("❌ Ошибка отправки файла в Telegram")

            driver.quit()

        except Exception as e:
            self.log.emit(f"❌ Ошибка парсинга: {e}")

        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("bashowol parser UwU")
        self.setFixedSize(1000, 700)
        self.setStyleSheet("background-color: #fdf0f9;")

        layout = QVBoxLayout()

        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Введите ссылку для парсинга")
        self.url_entry.setFont(QFont("Arial", 14))
        layout.addWidget(self.url_entry)

        self.headless_check = QCheckBox("Headless режим")
        self.headless_check.setFont(QFont("Arial", 12))
        layout.addWidget(self.headless_check)

        self.start_button = QPushButton("Начать парсинг")
        self.start_button.setFont(QFont("Arial", 14))
        self.start_button.clicked.connect(self.start_parsing)
        layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Arial", 10))
        layout.addWidget(self.log_text)

        self.image_label = QLabel()
        layout.addWidget(self.image_label, alignment=Qt.AlignRight)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.load_image()

    def load_image(self):
        try:
            url = "https://raw.githubusercontent.com/fuflyaj/vamp/main/c24071b9399c9e01a401a3eeb3c4e580.png"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            img_bytes = urlopen(req).read()
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio)
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.moveCursor(QTextCursor.End)

    def start_parsing(self):
        url = self.url_entry.text()
        headless = self.headless_check.isChecked()

        self.parser_thread = ParserThread(url, headless)
        self.parser_thread.log.connect(self.log)
        self.parser_thread.progress.connect(self.progress_bar.setValue)
        self.parser_thread.finished.connect(self.on_finished)

        self.parser_thread.start()

    def on_finished(self):
        self.log("🎉 Парсинг завершен!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
