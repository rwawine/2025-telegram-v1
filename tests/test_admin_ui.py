"""UI tests for admin panel using Selenium."""

import os
import sys
import time
import unittest
from unittest.mock import patch

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from web.app import create_app


class AdminUITestCase(unittest.TestCase):
    """Test case for admin panel UI using Selenium."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Настройка Chrome в headless режиме
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Инициализация драйвера
        cls.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Создание тестового приложения
        # Создаем тестовую конфигурацию
        from dataclasses import dataclass
        
        @dataclass
        class TestConfig:
            secret_key: str = "test_secret_key"
            max_file_size: int = 16 * 1024 * 1024
            database_path: str = ":memory:"
            admin_username: str = "admin"
            admin_password: str = "password"
        
        config = TestConfig()
        cls.app = create_app(config, testing=True)
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['SERVER_NAME'] = 'localhost:5000'
        
        # Запуск Flask приложения в отдельном потоке
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        
        # Запуск сервера
        import threading
        cls.server_thread = threading.Thread(target=cls.app.run)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        
        # Даем время на запуск сервера
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        """Tear down test environment."""
        cls.driver.quit()
        cls.app_context.pop()

    def setUp(self):
        """Set up before each test."""
        # Логин в админку
        self.driver.get('http://localhost:5000/admin/login')
        
        # Мокаем функцию проверки пароля
        with patch('web.auth.check_password', return_value=True):
            username_input = self.driver.find_element(By.ID, 'username')
            password_input = self.driver.find_element(By.ID, 'password')
            submit_button = self.driver.find_element(By.XPATH, '//button[@type="submit"]')
            
            username_input.send_keys('admin')
            password_input.send_keys('password')
            submit_button.click()
            
            # Ждем перенаправления на дашборд
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//h1[contains(text(), "Dashboard")]'))
            )

    def test_sidebar_navigation(self):
        """Test sidebar navigation buttons."""
        # Проверяем все ссылки в боковой панели
        sidebar_links = [
            ('Dashboard', '/admin/dashboard'),
            ('Participants', '/admin/participants'),
            ('Lottery', '/admin/lottery'),
            ('Broadcasts', '/admin/broadcasts'),
            ('Support Tickets', '/admin/support-tickets'),
            ('Settings', '/admin/settings')
        ]
        
        for link_text, expected_url in sidebar_links:
            # Находим и кликаем по ссылке
            link = self.driver.find_element(By.XPATH, f'//a[contains(text(), "{link_text}")]')
            link.click()
            
            # Проверяем URL после клика
            WebDriverWait(self.driver, 10).until(
                lambda driver: expected_url in driver.current_url
            )
            
            # Проверяем, что страница загрузилась корректно
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f'//h1[contains(text(), "{link_text}")]'))
            )

    def test_dashboard_cards(self):
        """Test dashboard stat cards."""
        # Переходим на дашборд
        self.driver.get('http://localhost:5000/admin/dashboard')
        
        # Проверяем наличие статистических карточек
        stat_cards = [
            'Total Participants',
            'Approved',
            'Pending',
            'Rejected'
        ]
        
        for card_title in stat_cards:
            # Проверяем наличие карточки
            card = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f'//p[contains(text(), "{card_title}")]'))
            )
            # Проверяем, что у карточки есть числовое значение
            card_parent = card.find_element(By.XPATH, './..')
            card_value = card_parent.find_element(By.XPATH, './/h4')
            self.assertTrue(card_value.text.strip().isdigit() or card_value.text.strip() == '0')

    def test_lottery_buttons(self):
        """Test lottery page buttons."""
        # Переходим на страницу лотереи
        self.driver.get('http://localhost:5000/admin/lottery')
        
        # Проверяем наличие кнопки создания розыгрыша
        create_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "Create Lottery")]'))
        )
        
        # Кликаем по кнопке создания
        create_button.click()
        
        # Проверяем, что открылось модальное окно
        modal = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, 'createEditModal'))
        )
        
        # Проверяем наличие полей формы
        self.assertTrue(modal.find_element(By.ID, 'lottery_name').is_displayed())
        self.assertTrue(modal.find_element(By.ID, 'lottery_description').is_displayed())
        self.assertTrue(modal.find_element(By.ID, 'winner_count').is_displayed())
        
        # Закрываем модальное окно
        close_button = modal.find_element(By.XPATH, './/button[@class="btn-close"]')
        close_button.click()
        
        # Ждем закрытия модального окна
        WebDriverWait(self.driver, 10).until(
            EC.invisibility_of_element_located((By.ID, 'createEditModal'))
        )

    def test_broadcasts_buttons(self):
        """Test broadcasts page buttons."""
        # Переходим на страницу рассылок
        self.driver.get('http://localhost:5000/admin/broadcasts')
        
        # Проверяем наличие кнопки создания рассылки
        create_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "Create Broadcast")]'))
        )
        
        # Кликаем по кнопке создания
        create_button.click()
        
        # Проверяем, что открылось модальное окно
        modal = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, 'createEditModal'))
        )
        
        # Проверяем наличие полей формы
        self.assertTrue(modal.find_element(By.ID, 'message_text').is_displayed())
        self.assertTrue(modal.find_element(By.ID, 'media_file').is_displayed())
        self.assertTrue(modal.find_element(By.ID, 'media_caption').is_displayed())
        
        # Закрываем модальное окно
        close_button = modal.find_element(By.XPATH, './/button[@class="btn-close"]')
        close_button.click()
        
        # Ждем закрытия модального окна
        WebDriverWait(self.driver, 10).until(
            EC.invisibility_of_element_located((By.ID, 'createEditModal'))
        )


if __name__ == '__main__':
    unittest.main()