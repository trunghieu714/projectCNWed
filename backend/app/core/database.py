import time
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from .config import settings
from ..models.entities import Base

def _create_db_engine():
    """
    Tạo engine SQLite hoặc PostgreSQL. Với PostgreSQL (Docker) chờ tối đa ~30 giây để DB khởi động
    xong; chỉ khi vẫn không kết nối được mới dự phòng sang SQLite app.db.
    """
    db_url = settings.DATABASE_URL
    if "postgresql" in db_url:
        last_error = None
        for _ in range(15):
            try:
                pg_engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
                with pg_engine.connect():
                    pass
                return pg_engine
            except Exception as e:
                last_error = e
                time.sleep(2)
        print(f"[WARN] Không thể kết nối PostgreSQL ({db_url}): {last_error}. Tự động chuyển sang SQLite app.db.")
        return create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})
    return create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})

engine = _create_db_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _add_missing_columns():
    """
    DB đã tồn tại từ phiên bản cũ (app.db hoặc volume PostgreSQL của Docker): create_all không thêm
    cột mới vào bảng cũ, nên so sánh model với DB và ALTER TABLE ADD COLUMN cho các cột còn thiếu.
    Kiểu cột được biên dịch theo đúng dialect (SQLite / PostgreSQL).
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default = ""
                if column.default is not None and getattr(column.default, "is_scalar", False):
                    value = column.default.arg
                    if isinstance(value, bool):
                        default = f" DEFAULT {'TRUE' if value else 'FALSE'}" if engine.dialect.name == "postgresql" else f" DEFAULT {int(value)}"
                    elif isinstance(value, (int, float)):
                        default = f" DEFAULT {value}"
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}{default}'))
                print(f"[MIGRATE] Thêm cột {table.name}.{column.name} ({col_type})")

def init_db():
    Base.metadata.create_all(bind=engine)
    try:
        _add_missing_columns()
    except Exception as e:
        print(f"[WARN] Không thể tự động bổ sung cột mới: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
