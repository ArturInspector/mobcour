import logging
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import threading

logger = logging.getLogger(__name__)
# Database init, there are many useless methods and rows, in future version it will be rework.
class Database:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
            return cls._instance

    def __init__(self, db_path: str = "courier_bot.db"):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных
        """
        if hasattr(self, 'initialized'):
            return
            
        try:
            self.db_path = db_path
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Создаем таблицы
            self._create_tables()
            
            # Выполняем миграцию
            try:
                self.migrate_database()
            except Exception as e:
                logger.warning(f"Ошибка при миграции базы данных: {e}")
                logger.info("Продолжаем работу с текущей структурой базы данных")
            

            self.add_user_id_column()
            
            # Обновляем существующих пользователей
            self.update_existing_users()
            
            self.initialized = True
            logger.info(f"База данных успешно инициализирована: {db_path}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise

    def _validate_order_data(self, order_data: Dict[str, Any]) -> bool:
        """
        Валидация данных заказа
        
        Args:
            order_data: Данные заказа для проверки
            
        Returns:
            bool: True если данные валидны, False в противном случае
        """
        try:
            # Проверка обязательных полей
            required_fields = ['time', 'address', 'price', 'distance']
            if not all(field in order_data for field in required_fields):
                logger.warning(f"Отсутствуют обязательные поля: {required_fields}")
                return False
            
            # Проверка типов данных
            if not isinstance(order_data['price'], (int, float)) or order_data['price'] < 0:
                logger.warning(f"Некорректная цена: {order_data['price']}")
                return False
                
            if not isinstance(order_data['distance'], (int, float)) or order_data['distance'] < 0:
                logger.warning(f"Некорректное расстояние: {order_data['distance']}")
                return False
                
            # Проверка формата времени
            try:
                datetime.strptime(order_data['time'], '%H:%M')
            except ValueError:
                logger.warning(f"Некорректный формат времени: {order_data['time']}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Ошибка при валидации данных заказа: {e}")
            return False

    def _convert_order_data_types(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Конвертация типов данных заказа
        
        Args:
            order_data: Исходные данные заказа
            
        Returns:
            Dict[str, Any]: Данные с правильными типами
        """
        try:
            converted = order_data.copy()
            
            # Конвертация цены
            if isinstance(converted['price'], str):
                converted['price'] = float(converted['price'].replace('₽', '').strip())
                
            # Конвертация расстояния
            if isinstance(converted['distance'], str):
                converted['distance'] = float(converted['distance'].replace('км', '').strip())
                
            return converted
        except Exception as e:
            logger.error(f"Ошибка при конвертации типов данных: {e}")
            return order_data

    def _create_tables(self):
        """Создает необходимые таблицы в базе данных"""
        try:
            with self.conn:
                # Создаем таблицу пользователей
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        transport TEXT,
                        current_service TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Создаем таблицу заказов
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        time TEXT,
                        address TEXT,
                        price REAL,
                        distance REAL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                
                # Создаем таблицу временных заказов
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS temporary_orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        time TEXT,
                        address TEXT,
                        price REAL,
                        distance REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                
                # Создаем таблицу смен
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        service TEXT,
                        start_time TIMESTAMP,
                        end_time TIMESTAMP,
                        earnings REAL,
                        order_count INTEGER,
                        weather TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Создаем таблицу для хранения советов ИИ
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS ai_advice (
                        advice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        advice_type TEXT,
                        advice_text TEXT,
                        related_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Создаем индексы для оптимизации
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_orders_user_id ON temporary_orders(user_id)")
                self.conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
                
                logger.info("Таблицы успешно созданы")
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц: {e}")
            raise
        
    def get_or_create_user(self, user_id: int, username: str) -> Dict[str, Any]:
        """
        Получает или создает пользователя в базе данных
        
        Args:
            user_id: Telegram ID пользователя
            username: Имя пользователя
            
        Returns:
            Dict с данными пользователя
        """
        try:
            # Проверяем существование пользователя
            cursor = self.conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            user = cursor.fetchone()
            
            if user:
                # Обновляем время последней активности
                self.conn.execute(
                    "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (user_id,)
                )
                logger.debug(f"Обновлено время активности пользователя {user_id}")
            else:
                # Создаем нового пользователя
                self.conn.execute(
                    """
                    INSERT INTO users (user_id, username, last_active)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (user_id, username)
                )
                logger.info(f"Создан новый пользователь: {user_id} ({username})")
            
            # Получаем данные пользователя (как существующего, так и нового)
            cursor = self.conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            return dict(cursor.fetchone())
            
        except Exception as e:
            logger.error(f"Ошибка при получении/создании пользователя: {e}")
            raise
        
    def get_user_sessions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получение списка смен пользователя с расчетом времени работы
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество смен для получения
            
        Returns:
            Список словарей с данными о сменах
        """
        try:
            self.cursor.execute(
                '''
                SELECT 
                    session_id,
                    user_id,
                    service,
                    start_time,
                    end_time,
                    earnings,
                    order_count,
                    weather,
                    created_at,
                    CASE 
                        WHEN start_time IS NOT NULL AND end_time IS NOT NULL 
                        THEN (julianday(end_time) - julianday(start_time)) * 24
                        ELSE 0 
                    END as total_hours,
                    CASE 
                        WHEN start_time IS NOT NULL AND end_time IS NOT NULL 
                        AND (julianday(end_time) - julianday(start_time)) * 24 > 0 
                        THEN earnings / ((julianday(end_time) - julianday(start_time)) * 24)
                        ELSE 0 
                    END as avg_earnings_per_hour
                FROM sessions 
                WHERE user_id = ? 
                ORDER BY start_time DESC 
                LIMIT ?
                ''',
                (user_id, limit)
            )
            sessions = self.cursor.fetchall()
            
            # Преобразуем Row в dict и округляем числовые значения
            result = []
            for session in sessions:
                session_dict = dict(session)
                # Округляем значения до 2 знаков после запятой
                if 'total_hours' in session_dict:
                    session_dict['total_hours'] = round(session_dict['total_hours'], 2)
                if 'avg_earnings_per_hour' in session_dict:
                    session_dict['avg_earnings_per_hour'] = round(session_dict['avg_earnings_per_hour'], 2)
                result.append(session_dict)
            
            return result
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении смен пользователя: {e}")
            return []
        
    def add_session(self, user_id: int, service: str, start_time: str) -> Optional[int]:
        """
        Добавление новой смены
        
        Args:
            user_id: ID пользователя
            service: Сервис доставки
            start_time: Время начала смены
            
        Returns:
            ID созданной смены или None в случае ошибки
        """
        try:
            self.cursor.execute(
                'INSERT INTO sessions (user_id, service, start_time) VALUES (?, ?, ?)',
                (user_id, service, start_time)
            )
            self.conn.commit()
            
            session_id = self.cursor.lastrowid
            logger.info(f"Добавлена новая смена: {session_id} для пользователя {user_id}")
            return session_id
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении смены: {e}")
            return None
            
    def end_session(self, session_id: int, earnings: float, order_count: int) -> bool:
        """
        Завершение смены
        
        Args:
            session_id: ID смены
            earnings: Заработок за смену
            order_count: Количество заказов за смену
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute(
                'UPDATE sessions SET end_time = ?, earnings = ?, order_count = ? WHERE session_id = ?',
                (end_time, earnings, order_count, session_id)
            )
            self.conn.commit()
            
            logger.info(f"Смена {session_id} успешно завершена. Заработок: {earnings}, заказов: {order_count}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при завершении смены: {e}")
            return False
            
    def update_session(self, session_id: int, **kwargs) -> bool:
        """
        Обновление данных смены
        
        Args:
            session_id: ID смены
            **kwargs: Данные для обновления (end_time, earnings, order_count, weather, service)
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            if not kwargs:
                logger.warning("Пустые данные для обновления смены")
                return False
                
            set_clause = ', '.join(f'{k} = ?' for k in kwargs.keys())
            values = list(kwargs.values())
            values.append(session_id)
            
            self.cursor.execute(
                f'UPDATE sessions SET {set_clause} WHERE session_id = ?',
                values
            )
            self.conn.commit()
            
            logger.debug(f"Смена {session_id} успешно обновлена: {kwargs}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении смены: {e}")
            return False
            
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение данных смены
        
        Args:
            session_id: ID смены
            
        Returns:
            Словарь с данными смены или None в случае ошибки
        """
        try:
            self.cursor.execute(
                'SELECT * FROM sessions WHERE session_id = ?',
                (session_id,)
            )
            session = self.cursor.fetchone()
            
            if not session:
                logger.warning(f"Смена с ID {session_id} не найдена")
                return None
                
            return dict(session)
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении смены: {e}")
            return None

    def get_user_transport(self, user_id: int) -> Optional[str]:
        """
        Получение транспорта пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Тип транспорта или None
        """
        try:
            self.cursor.execute(
                'SELECT transport FROM users WHERE id = ?',
                (user_id,)
            )
            result = self.cursor.fetchone()
            
            if not result:
                logger.warning(f"Пользователь с ID {user_id} не найден")
                return None
                
            return result['transport']
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении транспорта пользователя: {e}")
            return None

    def get_last_session_id(self, user_id: int) -> Optional[int]:
        """
        Получение ID последней сессии пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            ID последней сессии или None
        """
        try:
            self.cursor.execute(
                'SELECT session_id FROM sessions WHERE user_id = ? ORDER BY start_time DESC LIMIT 1',
                (user_id,)
            )
            result = self.cursor.fetchone()
            
            if not result:
                logger.debug(f"У пользователя {user_id} нет сессий")
                return None
                
            return result['session_id']
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении ID последней сессии: {e}")
            return None

    def update_user_service(self, user_id: int, service: str) -> bool:
        """
        Обновление сервиса пользователя
        
        Args:
            user_id: ID пользователя
            service: Название сервиса
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            self.cursor.execute(
                'UPDATE users SET current_service = ? WHERE user_id = ?',
                (service, user_id)
            )
            self.conn.commit()
            
            logger.info(f"Сервис пользователя {user_id} обновлен на {service}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении сервиса пользователя: {e}")
            return False

    def update_user_transport(self, user_id: int, transport: str) -> bool:
        """
        Обновление транспорта пользователя
        
        Args:
            user_id: ID пользователя
            transport: Тип транспорта
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            self.cursor.execute(
                'UPDATE users SET transport = ? WHERE user_id = ?',
                (transport, user_id)
            )
            self.conn.commit()
            
            logger.info(f"Транспорт пользователя {user_id} обновлен на {transport}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении транспорта пользователя: {e}")
            return False

    def get_user_service(self, user_id: int) -> Optional[str]:
        """
        Получение сервиса пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Название сервиса или None
        """
        try:
            self.cursor.execute(
                'SELECT current_service FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = self.cursor.fetchone()
            
            if not result:
                logger.warning(f"Пользователь с ID {user_id} не найден")
                return None
                
            return result['current_service']
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении сервиса пользователя: {e}")
            return None
    
    def add_order(self, user_id: int, session_id: Optional[int], order_data: Dict[str, Any]) -> Optional[int]:
        """
        Добавление нового заказа
        
        Args:
            user_id: ID пользователя
            session_id: ID смены (может быть None)
            order_data: Данные заказа (time, address, price, distance)
            
        Returns:
            ID созданного заказа или None в случае ошибки
        """
        try:
            self.cursor.execute(
                '''
                INSERT INTO orders 
                (user_id, session_id, time, address, price, distance) 
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    user_id, 
                    session_id, 
                    order_data.get('time'), 
                    order_data.get('address'), 
                    order_data.get('price'), 
                    order_data.get('distance')
                )
            )
            self.conn.commit()
            
            order_id = self.cursor.lastrowid
            logger.info(f"Добавлен новый заказ: {order_id} для пользователя {user_id}")
            return order_id
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении заказа: {e}")
            return None
    
    def get_orders_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """
        Получение заказов по ID смены
        
        Args:
            session_id: ID смены
            
        Returns:
            Список словарей с данными заказов
        """
        try:
            self.cursor.execute(
                'SELECT * FROM orders WHERE session_id = ? ORDER BY created_at',
                (session_id,)
            )
            orders = self.cursor.fetchall()
            
            return [dict(order) for order in orders]
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении заказов для смены {session_id}: {e}")
            return []
    
    def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получение заказов по ID пользователя
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество заказов
            
        Returns:
            Список словарей с данными заказов
        """
        try:
            self.cursor.execute(
                'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
                (user_id, limit)
            )
            orders = self.cursor.fetchall()
            
            return [dict(order) for order in orders]
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении заказов для пользователя {user_id}: {e}")
            return []
    
    def update_order(self, order_id: int, **kwargs) -> bool:
        """
        Обновление данных заказа
        
        Args:
            order_id: ID заказа
            **kwargs: Данные для обновления (time, address, price, distance)
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            if not kwargs:
                logger.warning("Пустые данные для обновления заказа")
                return False
                
            set_clause = ', '.join(f'{k} = ?' for k in kwargs.keys())
            values = list(kwargs.values())
            values.append(order_id)
            
            self.cursor.execute(
                f'UPDATE orders SET {set_clause} WHERE order_id = ?',
                values
            )
            self.conn.commit()
            
            logger.debug(f"Заказ {order_id} успешно обновлен: {kwargs}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении заказа: {e}")
            return False
    
    def delete_order(self, order_id: int) -> bool:
        """
        Удаление заказа
        
        Args:
            order_id: ID заказа
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            self.cursor.execute(
                'DELETE FROM orders WHERE order_id = ?',
                (order_id,)
            )
            self.conn.commit()
            
            logger.info(f"Заказ {order_id} успешно удален")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при удалении заказа: {e}")
            return False
    
    def add_ai_advice(self, user_id: int, advice_type: str, advice_text: str, related_data: Optional[str] = None) -> Optional[int]:
        """
        Добавление совета ИИ
        
        Args:
            user_id: ID пользователя
            advice_type: Тип совета (order, daily, etc.)
            advice_text: Текст совета
            related_data: Связанные данные в формате JSON
            
        Returns:
            ID созданной записи совета или None в случае ошибки
        """
        try:
            self.cursor.execute(
                '''
                INSERT INTO ai_advice 
                (user_id, advice_type, advice_text, related_data) 
                VALUES (?, ?, ?, ?)
                ''',
                (user_id, advice_type, advice_text, related_data)
            )
            self.conn.commit()
            
            advice_id = self.cursor.lastrowid
            logger.info(f"Добавлен новый совет ИИ: {advice_id} для пользователя {user_id}")
            return advice_id
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении совета ИИ: {e}")
            return None
    
    def get_user_advice(self, user_id: int, advice_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Получение советов ИИ для пользователя
        
        Args:
            user_id: ID пользователя
            advice_type: Тип совета (если None, то все типы)
            limit: Максимальное количество советов
            
        Returns:
            Список словарей с советами
        """
        try:
            if advice_type:
                self.cursor.execute(
                    '''
                    SELECT * FROM ai_advice 
                    WHERE user_id = ? AND advice_type = ? 
                    ORDER BY created_at DESC LIMIT ?
                    ''',
                    (user_id, advice_type, limit)
                )
            else:
                self.cursor.execute(
                    '''
                    SELECT * FROM ai_advice 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC LIMIT ?
                    ''',
                    (user_id, limit)
                )
                
            advice = self.cursor.fetchall()
            return [dict(a) for a in advice]
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении советов ИИ для пользователя {user_id}: {e}")
            return []
    
    def get_connection(self):
        """
        Получает соединение с базой данных
        """
        return self.conn

    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Получает статистику пользователя
        """
        try:
            # Получаем основную статистику
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total_shifts,
                    COALESCE(SUM(earnings), 0) as total_earnings,
                    COALESCE(SUM(order_count), 0) as total_orders,
                    COALESCE(AVG(earnings), 0) as avg_earnings,
                    COALESCE(AVG(order_count), 0) as avg_orders,
                    COALESCE(MAX(earnings), 0) as max_earnings,
                    COALESCE(MIN(earnings), 0) as min_earnings,
                    COALESCE(SUM((julianday(end_time) - julianday(start_time)) * 24), 0) as total_hours,
                    COALESCE(AVG((julianday(end_time) - julianday(start_time)) * 24), 0) as avg_shift_duration
                FROM sessions 
                WHERE user_id = ? AND end_time IS NOT NULL
            """, (user_id,))
            
            stats = self.cursor.fetchone()
            
            if not stats:
                return {
                    'total_shifts': 0,
                    'total_earnings': 0,
                    'total_orders': 0,
                    'avg_earnings': 0,
                    'avg_orders': 0,
                    'max_earnings': 0,
                    'min_earnings': 0,
                    'total_hours': 0,
                    'avg_shift_duration': 0
                }
            
            # Преобразуем результат в словарь
            stats_dict = dict(stats)
            
            # Убеждаемся, что все значения не None
            for key in stats_dict:
                if stats_dict[key] is None:
                    stats_dict[key] = 0
            
            return stats_dict
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя: {e}")
            return None

    def get_detailed_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Получает детальную статистику пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с детальной статистикой
        """
        try:
            logger.debug(f"Запрос детальной статистики для пользователя {user_id}")
            
            # Получаем базовую статистику
            basic_stats = self.get_user_statistics(user_id)
            logger.debug(f"Получена базовая статистика: {basic_stats}")
            
            # Получаем статистику по времени суток
            time_stats = {}
            cursor = self.conn.execute("""
                SELECT 
                    CASE 
                        WHEN CAST(strftime('%H', time) AS INTEGER) BETWEEN 6 AND 11 THEN 'morning'
                        WHEN CAST(strftime('%H', time) AS INTEGER) BETWEEN 12 AND 17 THEN 'day'
                        WHEN CAST(strftime('%H', time) AS INTEGER) BETWEEN 18 AND 23 THEN 'evening'
                        ELSE 'night'
                    END as time_of_day,
                    COUNT(*) as count
                FROM orders 
                WHERE user_id = ? 
                GROUP BY time_of_day
            """, (user_id,))
            
            for row in cursor.fetchall():
                time_stats[row['time_of_day']] = row['count']
            
            logger.debug(f"Статистика по времени суток: {time_stats}")
            
            # Получаем статистику по дням недели
            day_stats = {}
            cursor = self.conn.execute("""
                SELECT 
                    strftime('%w', created_at) as day_of_week,
                    COUNT(*) as count
                FROM orders 
                WHERE user_id = ? 
                GROUP BY day_of_week
            """, (user_id,))
            
            for row in cursor.fetchall():
                day_stats[row['day_of_week']] = row['count']
            
            logger.debug(f"Статистика по дням недели: {day_stats}")
            
            # Формируем итоговую статистику
            detailed_stats = {
                **basic_stats,
                'time_stats': time_stats,
                'day_stats': day_stats
            }
            
            logger.info(f"Сформирована детальная статистика для пользователя {user_id}")
            return detailed_stats
            
        except Exception as e:
            logger.error(f"Ошибка при получении детальной статистики: {e}")
            return {
                'total_orders': 0,
                'total_earnings': 0,
                'avg_earnings': 0,
                'total_distance': 0,
                'avg_distance': 0,
                'time_stats': {},
                'day_stats': {}
            }
            
    def save_temporary_order(self, user_id: int, order_data: Dict[str, Any]) -> Optional[int]:
        """
        Сохраняет заказ во временную таблицу для последующего подтверждения
        
        Args:
            user_id: ID пользователя
            order_data: Данные заказа (time, address, price, distance)
            
        Returns:
            ID созданного временного заказа или None в случае ошибки
        """
        try:
            # Создаем временную таблицу, если её нет
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    time TEXT,
                    address TEXT,
                    price REAL,
                    distance REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            self.conn.commit()
            
            # Вставляем данные во временную таблицу
            self.cursor.execute(
                '''
                INSERT INTO temp_orders 
                (user_id, time, address, price, distance) 
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    user_id, 
                    order_data.get('time'), 
                    order_data.get('address'), 
                    order_data.get('price'), 
                    order_data.get('distance')
                )
            )
            self.conn.commit()
            
            order_id = self.cursor.lastrowid
            logger.info(f"Создан временный заказ #{order_id} для пользователя {user_id}")
            return order_id
        except sqlite3.Error as e:
            logger.error(f"Ошибка при сохранении временного заказа: {e}")
            return None

    def update_order_field(self, order_id: int, field: str, value: Any) -> bool:
        """
        Обновляет конкретное поле заказа (постоянного или временного)
        
        Args:
            order_id: ID заказа
            field: Название поля (time, address, price, distance)
            value: Новое значение поля
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            # Проверяем, есть ли заказ в постоянной таблице
            self.cursor.execute(
                'SELECT 1 FROM orders WHERE order_id = ?',
                (order_id,)
            )
            exists_in_orders = self.cursor.fetchone() is not None
            
            # Проверяем, есть ли заказ во временной таблице
            self.cursor.execute(
                'SELECT 1 FROM temp_orders WHERE order_id = ?',
                (order_id,)
            )
            exists_in_temp = self.cursor.fetchone() is not None
            
            # Обновляем заказ в соответствующей таблице
            if exists_in_orders:
                table_name = 'orders'
            elif exists_in_temp:
                table_name = 'temp_orders'
            else:
                logger.warning(f"Заказ #{order_id} не найден ни в одной таблице")
                return False
            
            # Составляем запрос для обновления
            query = f'UPDATE {table_name} SET {field} = ? WHERE order_id = ?'
            self.cursor.execute(query, (value, order_id))
            self.conn.commit()
            
            logger.debug(f"Поле {field} заказа #{order_id} обновлено в таблице {table_name}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении поля заказа: {e}")
            return False

    def delete_temporary_order(self, order_id: int) -> bool:
        """
        Удаляет временный заказ
        
        Args:
            order_id: ID временного заказа
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            self.cursor.execute(
                'DELETE FROM temp_orders WHERE order_id = ?',
                (order_id,)
            )
            self.conn.commit()
            
            affected_rows = self.cursor.rowcount
            if affected_rows > 0:
                logger.info(f"Временный заказ #{order_id} успешно удален")
                return True
            else:
                logger.warning(f"Временный заказ #{order_id} не найден")
                return False
        except sqlite3.Error as e:
            logger.error(f"Ошибка при удалении временного заказа: {e}")
            return False

    def save_order(self, user_id: int, order_data: Dict[str, Any]) -> Optional[int]:
        """
        Сохраняет заказ в постоянную таблицу
        
        Args:
            user_id: ID пользователя
            order_data: Данные заказа
            
        Returns:
            ID сохраненного заказа или None в случае ошибки
        """
        try:
            # Валидация данных
            if not self._validate_order_data(order_data):
                logger.warning(f"Некорректные данные заказа: {order_data}")
                return None
                
            # Конвертация типов
            order_data = self._convert_order_data_types(order_data)
            
            # Получаем текущую сессию пользователя
            session_id = self.get_last_session_id(user_id)
            
            # Сохраняем заказ
            self.cursor.execute(
                '''
                INSERT INTO orders 
                (user_id, session_id, time, address, price, distance, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    user_id, 
                    session_id, 
                    order_data['time'], 
                    order_data['address'], 
                    order_data['price'], 
                    order_data['distance'],
                    'pending'
                )
            )
            self.conn.commit()
            
            order_id = self.cursor.lastrowid
            logger.info(f"Заказ #{order_id} успешно сохранен для пользователя {user_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении заказа: {e}")
            self.conn.rollback()
            return None

    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает данные заказа по его ID (ищет сначала в постоянной таблице, потом во временной)
        
        Args:
            order_id: ID заказа
            
        Returns:
            Словарь с данными заказа или None если заказ не найден
        """
        try:
            # Ищем в постоянной таблице
            self.cursor.execute(
                'SELECT * FROM orders WHERE order_id = ?',
                (order_id,)
            )
            order = self.cursor.fetchone()
            
            if order:
                return dict(order)
            
            # Если не нашли, ищем во временной таблице
            self.cursor.execute(
                'SELECT * FROM temp_orders WHERE order_id = ?',
                (order_id,)
            )
            temp_order = self.cursor.fetchone()
            
            if temp_order:
                return dict(temp_order)
            
            logger.warning(f"Заказ #{order_id} не найден ни в одной таблице")
            return None
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении заказа: {e}")
            return None
            
    def close(self):
        """Закрытие соединения с базой данных"""
        if hasattr(self, 'conn'):
            self.conn.close()
            logger.debug("Соединение с базой данных закрыто")

    def migrate_database(self):
        """
        Выполняет миграцию базы данных
        """
        try:
            logger.info("Начало миграции базы данных")
            
            with self.conn:
                # Проверяем версию базы данных
                self.cursor.execute("PRAGMA user_version")
                current_version = self.cursor.fetchone()[0]
                
                if current_version == 0:
                    # Первая миграция
                    self._migrate_to_v1()
                    self.cursor.execute("PRAGMA user_version = 1")
                elif current_version == 1:
                    # Вторая миграция
                    self._migrate_to_v2()
                    self.cursor.execute("PRAGMA user_version = 2")
                elif current_version == 2:
                    # Третья миграция
                    self._migrate_to_v3()
                    self.cursor.execute("PRAGMA user_version = 3")
                    
            logger.info("Миграция базы данных успешно завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при миграции базы данных: {e}")
            raise

    def _migrate_to_v1(self):
        """Первая миграция базы данных"""
        try:
            # Создаем временную таблицу пользователей
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users_new (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    transport TEXT,
                    current_service TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Копируем данные из старой таблицы
            self.conn.execute("""
                INSERT INTO users_new (id, username, transport, current_service, created_at, last_active)
                SELECT 
                    id,
                    username,
                    transport,
                    current_service,
                    created_at,
                    COALESCE(last_active, CURRENT_TIMESTAMP) as last_active
                FROM users
            """)
            
            # Удаляем старую таблицу
            self.conn.execute("DROP TABLE IF EXISTS users")
            
            # Переименовываем новую таблицу
            self.conn.execute("ALTER TABLE users_new RENAME TO users")
            
            logger.info("Миграция к версии 1 завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при миграции к версии 1: {e}")
            raise

    def _migrate_to_v2(self):
        """Вторая миграция базы данных"""
        try:
            # Добавляем новые колонки в таблицу orders
            self.conn.execute("""
                ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pending'
            """)
            
            # Создаем индексы для оптимизации
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            
            logger.info("Миграция к версии 2 завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при миграции к версии 2: {e}")
            raise

    def _migrate_to_v3(self):
        """Третья миграция базы данных"""
        try:
            # Исправляем название колонки в таблице sessions
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions_new (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    earnings REAL,
                    order_count INTEGER,
                    weather TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Копируем данные из старой таблицы
            self.conn.execute("""
                INSERT INTO sessions_new (
                    session_id, user_id, service, start_time, end_time,
                    earnings, order_count, weather, created_at
                )
                SELECT 
                    session_id,
                    user_id,
                    service,
                    start_time,
                    end_time,
                    earnings,
                    order_count,
                    weather,
                    created_at
                FROM sessions
            """)
            
            # Удаляем старую таблицу
            self.conn.execute("DROP TABLE IF EXISTS sessions")
            
            # Переименовываем новую таблицу
            self.conn.execute("ALTER TABLE sessions_new RENAME TO sessions")
            
            # Добавляем колонку session_id в таблицу orders
            self.conn.execute("""
                ALTER TABLE orders ADD COLUMN session_id INTEGER REFERENCES sessions(session_id)
            """)
            
            logger.info("Миграция к версии 3 завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при миграции к версии 3: {e}")
            raise

    def add_user_id_column(self):
        """Добавляет столбец user_id в таблицу users"""
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN user_id INTEGER;")
            self.conn.commit()
            logger.info("Столбец user_id успешно добавлен в таблицу users")
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении столбца user_id: {e}")

    def update_existing_users(self):
        """Обновляет существующих пользователей, добавляя user_id"""
        try:
            # Получаем всех пользователей, у которых user_id еще не установлен
            cursor = self.conn.execute("SELECT id, username FROM users WHERE user_id IS NULL")
            users = cursor.fetchall()
            
            for user in users:
                user_id = user['id']  # Здесь предполагается, что id - это Telegram ID
                username = user['username']
                
                # Обновляем user_id для этого пользователя
                self.conn.execute(
                    "UPDATE users SET user_id = ? WHERE id = ?",
                    (user_id, user['id'])
                )
                logger.info(f"Обновлен user_id для пользователя {username} (ID: {user['id']})")
            
            self.conn.commit()
            logger.info("Обновление существующих пользователей завершено")
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении существующих пользователей: {e}")