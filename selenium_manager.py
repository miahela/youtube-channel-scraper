from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium import webdriver
import logging
from selenium.common.exceptions import WebDriverException

from config import load_settings


logger = logging.getLogger("app")
logger.setLevel(logging.INFO)  # Set level to INFO

def configure_logger(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for name, level in [("info.log", logging.INFO), ("error.log", logging.ERROR)]:
        path = str((output_dir / name).resolve())
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == path for h in logger.handlers):
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setLevel(level)
            handler.setFormatter(formatter)
            logger.addHandler(handler)


class SeleniumManager:
    def __init__(self, settings=None):
        settings = settings or load_settings()
        configure_logger(settings.output_dir)
        self.logger = logger
        self.logger.info("Initializing Selenium driver...")

        options = Options()
        self.driver = webdriver.Chrome(options=options)
        try:
            self.driver.maximize_window()
        except WebDriverException:
            self.driver.quit()
            raise

        self.wait = WebDriverWait(self.driver, settings.browser_wait)

        self.logger.info("Selenium driver initialized successfully!")

    def open_link(self, href):
        try:
            self.driver.get(href)
        except Exception as e:
            self.logger.error(f"Error opening link: {e}")
            raise

    def refresh(self):
        self.driver.refresh()

    def get_driver(self):
        return self.driver

    def get_elements(self, xpath):
        self.wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath)))
        return self.driver.find_elements(By.XPATH, xpath)

    def get_element(self, xpath):
        self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        return self.driver.find_element(By.XPATH, xpath)

    def click_element(self, xpath):
        self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()

    def fill_field(self, xpath, data):
        field = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        field.send_keys(data)
        field.send_keys(Keys.ENTER)

    def upload_file(self, xpath, file_path):
        file_input = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        file_input.send_keys(file_path)
        ActionChains(self.driver).key_down(Keys.ENTER).perform()

    def quit(self):
        self.driver.quit()
        self.logger.info("Selenium driver closed successfully!")
