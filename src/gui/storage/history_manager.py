"""
转录历史记录管理器

使用 SQLite 数据库存储转录历史记录

数据库位置:
    - confighistory.db

表结构:
    transcription_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        audio_source TEXT NOT NULL,
        audio_path TEXT,
        duration REAL NOT NULL,
        text TEXT NOT NULL,
        model_name TEXT,
        config_snapshot TEXT
    )
"""

import sqlite3
import logging
import os
import json
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
import threading

from src.gui.models.history_models import TranscriptionRecord

logger = logging.getLogger(__name__)


class HistoryManager:
    """转录历史记录管理器

    使用 SQLite 数据库存储转录历史记录
    """

    def __init__(self):
        """初始化历史记录管理器"""
        self.db_path = self._get_db_path()
        self._lock = threading.RLock()  # 可重入锁，支持线程安全
        self._init_database()
        logger.info(f"History database: {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器

        确保连接正确关闭，提供线程安全的数据库访问

        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        conn = None
        try:
            with self._lock:
                conn = sqlite3.connect(
                    str(self.db_path),
                    timeout=30.0,  # 30秒超时
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row  # 默认使用Row对象
                conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
                conn.execute("PRAGMA journal_mode = WAL")  # 使用WAL模式提高并发性能
                yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @contextmanager
    def _transaction(self, conn):
        """事务上下文管理器

        确保事务正确提交或回滚

        Args:
            conn: 数据库连接对象
        """
        try:
            conn.execute("BEGIN IMMEDIATE")  # 立即获取写锁
            yield conn
            conn.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise

    def _get_db_path(self) -> Path:
        """获取数据库文件路径

        Returns:
            Path: 数据库文件路径
        """
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent

        config_dir = project_root / "config"

        config_dir.mkdir(parents=True, exist_ok=True)

        return config_dir / 'history.db'

    def _init_database(self) -> None:
        """初始化数据库（创建表）"""
        try:
            with self._get_connection() as conn:
                with self._transaction(conn):
                    cursor = conn.cursor()

                    # 创建历史记录表
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS transcription_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp TEXT NOT NULL,
                            audio_source TEXT NOT NULL,
                            audio_path TEXT,
                            duration REAL NOT NULL,
                            text TEXT NOT NULL,
                            model_name TEXT,
                            config_snapshot TEXT
                        )
                    ''')

                    # 创建索引（加速查询）
                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_timestamp
                        ON transcription_history(timestamp DESC)
                    ''')

                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_audio_source
                        ON transcription_history(audio_source)
                    ''')

                    logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def add_record(self, record: TranscriptionRecord) -> int:
        """添加转录记录

        Args:
            record: 转录记录对象

        Returns:
            int: 插入记录的ID
        """
        try:
            with self._get_connection() as conn:
                with self._transaction(conn):
                    cursor = conn.cursor()

                    # 序列化config_snapshot为JSON字符串
                    config_snapshot_json = json.dumps(record.config_snapshot) if record.config_snapshot else '{}'

                    cursor.execute('''
                        INSERT INTO transcription_history
                        (timestamp, audio_source, audio_path, duration, text, model_name, config_snapshot)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        record.timestamp.isoformat() if record.timestamp else datetime.now().isoformat(),
                        record.audio_source.value if record.audio_source else '',
                        record.audio_path,
                        record.duration,
                        record.text,
                        record.model_name,
                        config_snapshot_json
                    ))

                    record_id = cursor.lastrowid
                    logger.info(f"Record added: ID={record_id}")
                    return record_id

        except Exception as e:
            logger.error(f"Failed to add record: {e}")
            raise

    def get_all_records(self, limit: int = 100, offset: int = 0) -> List[TranscriptionRecord]:
        """获取所有记录（时间倒序）

        Args:
            limit: 返回记录数量限制
            offset: 偏移量（分页）

        Returns:
            List[TranscriptionRecord]: 记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM transcription_history
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))

                rows = cursor.fetchall()
                records = [self._row_to_record(row) for row in rows]
                logger.debug(f"Retrieved {len(records)} records")
                return records

        except Exception as e:
            logger.error(f"Failed to get records: {e}")
            return []

    def search_records(self, query: str, limit: int = 100) -> List[TranscriptionRecord]:
        """搜索记录（全文搜索）

        Args:
            query: 搜索关键词
            limit: 返回记录数量限制

        Returns:
            List[TranscriptionRecord]: 匹配的记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 简单的LIKE搜索（未来可升级为FTS全文搜索）
                cursor.execute('''
                    SELECT * FROM transcription_history
                    WHERE text LIKE ? OR model_name LIKE ? OR audio_path LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))

                rows = cursor.fetchall()
                records = [self._row_to_record(row) for row in rows]
                logger.debug(f"Search found {len(records)} records")
                return records

        except Exception as e:
            logger.error(f"Failed to search records: {e}")
            return []

    def filter_by_source(self, audio_source: str, limit: int = 100) -> List[TranscriptionRecord]:
        """按音频源类型过滤

        Args:
            audio_source: 音频源类型
            limit: 返回记录数量限制

        Returns:
            List[TranscriptionRecord]: 过滤后的记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM transcription_history
                    WHERE audio_source = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (audio_source, limit))

                rows = cursor.fetchall()
                records = [self._row_to_record(row) for row in rows]
                logger.debug(f"Filtered {len(records)} records by source: {audio_source}")
                return records

        except Exception as e:
            logger.error(f"Failed to filter records: {e}")
            return []

    def get_record_by_id(self, record_id: int) -> Optional[TranscriptionRecord]:
        """根据ID获取记录

        Args:
            record_id: 记录ID

        Returns:
            Optional[TranscriptionRecord]: 记录对象，不存在返回None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM transcription_history WHERE id = ?', (record_id,))
                row = cursor.fetchone()

                if row:
                    return self._row_to_record(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get record: {e}")
            return None

    def delete_record(self, record_id: int) -> bool:
        """删除记录

        Args:
            record_id: 记录ID

        Returns:
            bool: 是否成功删除
        """
        try:
            with self._get_connection() as conn:
                with self._transaction(conn):
                    cursor = conn.cursor()

                    cursor.execute('DELETE FROM transcription_history WHERE id = ?', (record_id,))
                    deleted = cursor.rowcount > 0

                    if deleted:
                        logger.info(f"Record deleted: ID={record_id}")
                    else:
                        logger.warning(f"Record not found: ID={record_id}")

                    return deleted

        except Exception as e:
            logger.error(f"Failed to delete record: {e}")
            return False

    def delete_records_before(self, date: datetime) -> int:
        """删除指定日期之前的所有记录

        Args:
            date: 日期阈值

        Returns:
            int: 删除的记录数量
        """
        try:
            with self._get_connection() as conn:
                with self._transaction(conn):
                    cursor = conn.cursor()

                    cursor.execute('''
                        DELETE FROM transcription_history
                        WHERE timestamp < ?
                    ''', (date.isoformat(),))

                    deleted_count = cursor.rowcount

                    if deleted_count > 0:
                        logger.info(f"Deleted {deleted_count} records before {date.isoformat()}")

                    return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete old records: {e}")
            return 0

    def get_record_count(self) -> int:
        """获取记录总数

        Returns:
            int: 记录总数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM transcription_history')
                count = cursor.fetchone()[0]

                return count

        except Exception as e:
            logger.error(f"Failed to get record count: {e}")
            return 0

    def get_records_by_date_range(self, start_date: datetime, end_date: datetime,
                                 limit: int = 100) -> List[TranscriptionRecord]:
        """获取指定日期范围内的记录

        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回记录数量限制

        Returns:
            List[TranscriptionRecord]: 记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM transcription_history
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (start_date.isoformat(), end_date.isoformat(), limit))

                rows = cursor.fetchall()
                records = [self._row_to_record(row) for row in rows]
                logger.debug(f"Retrieved {len(records)} records in date range")
                return records

        except Exception as e:
            logger.error(f"Failed to get records by date range: {e}")
            return []

    def _row_to_record(self, row: sqlite3.Row) -> TranscriptionRecord:
        """将数据库行转换为TranscriptionRecord对象

        Args:
            row: 数据库行对象

        Returns:
            TranscriptionRecord: 记录对象
        """
        from src.audio.models import AudioSourceType

        # 反序列化config_snapshot
        config_snapshot = {}
        if row['config_snapshot']:
            try:
                config_snapshot = json.loads(row['config_snapshot'])
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in config_snapshot for record {row['id']}")

        return TranscriptionRecord(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            audio_source=AudioSourceType(row['audio_source']) if row['audio_source'] else None,
            audio_path=row['audio_path'],
            duration=row['duration'],
            text=row['text'],
            model_name=row['model_name'],
            config_snapshot=config_snapshot
        )

    def backup_database(self, backup_path: str) -> bool:
        """备份数据库

        Args:
            backup_path: 备份文件路径

        Returns:
            bool: 是否成功备份
        """
        try:
            import shutil
            shutil.copy2(str(self.db_path), backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False

    def vacuum_database(self) -> bool:
        """优化数据库（VACUUM操作）

        Returns:
            bool: 是否成功优化
        """
        try:
            with self._get_connection() as conn:
                conn.execute('VACUUM')
                logger.info("Database vacuumed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False