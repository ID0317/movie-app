"""
第7课：SQLite 数据库层
======================
把电影数据从 CSV 搬到 SQLite 数据库，支持完整 CRUD。

新概念速览：
    SQLite   = 轻量级数据库，数据存在 .db 文件里，Python 自带
    表       = Excel 的一页工作表
    行/列    = Excel 的行/列
    SQL      = 操作数据库的语言
    CRUD     = Create(增) / Read(查) / Update(改) / Delete(删)

四大 SQL 句型：
    SELECT   → 查询数据    SELECT * FROM movies WHERE title LIKE '%搜索%'
    INSERT   → 新增数据    INSERT INTO movies VALUES (1, '片名', 9.0, ...)
    UPDATE   → 修改数据    UPDATE movies SET title='新片名' WHERE rank=1
    DELETE   → 删除数据    DELETE FROM movies WHERE rank=1
"""
import sqlite3
import os

# 数据库文件就放在项目目录下
DB_PATH = os.path.join(os.path.dirname(__file__), "movies.db")


def get_conn():
    """
    获取数据库连接。

    row_factory = sqlite3.Row 让查询结果支持 row["列名"] 方式取值，
    而不是只能 row[0], row[1] 按位置取。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# 1. 初始化
# ============================================================

def init_db():
    """
    创建表结构（只在第一次运行时生效）。

    CREATE TABLE IF NOT EXISTS = "如果表不存在就创建"
    这是"幂等"操作：执行 100 次和执行 1 次结果一样。

    列类型说明：
        INTEGER      整数
        TEXT         文本
        REAL         浮点数（小数）
        PRIMARY KEY  主键 = 唯一标识，不会重复
        NOT NULL     不允许为空
        DEFAULT ''   默认值
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            rank          INTEGER PRIMARY KEY,
            title         TEXT    NOT NULL,
            rating        REAL    DEFAULT 0.0,
            rating_people TEXT    DEFAULT '',
            quote         TEXT    DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# 2. 查询 (Read) —— SELECT
# ============================================================

def get_all_movies(search="", sort_by="rank"):
    """
    查所有电影，支持搜索和排序。

    重点语法：
        LIKE       模糊匹配，% 是通配符（匹配任意字符）
        ?          参数占位符，防 SQL 注入
        ORDER BY   排序，ASC=升序  DESC=降序
    """
    conn = get_conn()
    cursor = conn.cursor()

    sql = "SELECT * FROM movies"
    params = []

    if search:
        sql += " WHERE title LIKE ?"
        params.append(f"%{search}%")

    if sort_by == "rating":
        sql += " ORDER BY rating DESC"
    else:
        sql += " ORDER BY rank ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # 把数据库 Row 对象转成普通字典，方便模板使用
    movies = []
    for row in rows:
        movies.append({
            "rank": row["rank"],
            "title": row["title"],
            "rating": row["rating"],
            "rating_people": row["rating_people"],
            "quote": row["quote"],
        })
    return movies


def get_movie(rank):
    """查单部电影"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies WHERE rank = ?", (rank,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "rank": row["rank"],
        "title": row["title"],
        "rating": row["rating"],
        "rating_people": row["rating_people"],
        "quote": row["quote"],
    }


def count_movies():
    """统计总数"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ============================================================
# 3. 新增 (Create) —— INSERT
# ============================================================

def add_movie(title, rating, rating_people, quote):
    """
    新增一部电影。

    rank 自动分配为当前最大排名 + 1。
    返回新电影的 rank。
    """
    conn = get_conn()
    cursor = conn.cursor()

    # 找当前最大 rank
    cursor.execute("SELECT MAX(rank) FROM movies")
    max_rank = cursor.fetchone()[0]
    new_rank = 1 if max_rank is None else max_rank + 1

    cursor.execute(
        "INSERT INTO movies (rank, title, rating, rating_people, quote) "
        "VALUES (?, ?, ?, ?, ?)",
        (new_rank, title, rating, rating_people, quote)
    )
    conn.commit()   # ⚠️ 增删改必须 commit，否则数据不会保存！
    conn.close()
    return new_rank


# ============================================================
# 4. 修改 (Update) —— UPDATE
# ============================================================

def update_movie(rank, title, rating, rating_people, quote):
    """
    修改电影信息。

    ⚠️ WHERE rank=? 绝对不能少！
       没有 WHERE 会把整张表所有行都改了！
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE movies SET title=?, rating=?, rating_people=?, quote=? "
        "WHERE rank=?",
        (title, rating, rating_people, quote, rank)
    )
    conn.commit()
    conn.close()


# ============================================================
# 5. 删除 (Delete) —— DELETE
# ============================================================

def delete_movie(rank):
    """
    删除电影。

    ⚠️ 同样，WHERE 不能少！没 WHERE = 全删光！
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE rank = ?", (rank,))
    conn.commit()
    conn.close()


# ============================================================
# 6. 文章表 —— 新闻聚合功能（第8课新增）
# ============================================================

def init_news_table():
    """
    创建文章表。

    新概念：
        AUTOINCREMENT   自动编号，每插入一行自动 +1
        TIMESTAMP       时间戳，记录精确到秒的时间
        DEFAULT CURRENT_TIMESTAMP  插入时自动填当前时间
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT    NOT NULL,
            url       TEXT    DEFAULT '',
            source    TEXT    DEFAULT '',
            points    INTEGER DEFAULT 0,
            comments  INTEGER DEFAULT 0,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_articles(articles):
    """
    批量保存文章。

    先清空旧数据，再插入新的（每次刷新都是最新榜单）。
    返回保存的数量。
    """
    conn = get_conn()
    cursor = conn.cursor()

    # 清空旧数据
    cursor.execute("DELETE FROM articles")

    # 批量插入
    count = 0
    for a in articles:
        cursor.execute(
            "INSERT INTO articles (title, url, source, points, comments) "
            "VALUES (?, ?, ?, ?, ?)",
            (a["title"], a["url"], a["source"], a.get("points", 0), a.get("comments", 0))
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"[数据库] 已保存 {count} 篇文章")
    return count


def get_articles(limit=50):
    """
    获取文章列表（最新的在前）。
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM articles ORDER BY points DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    articles = []
    for row in rows:
        articles.append({
            "id": row["id"],
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "points": row["points"],
            "comments": row["comments"],
            "scraped_at": row["scraped_at"],
        })
    return articles


def get_last_scrape_time():
    """
    获取最近一次抓取的时间。
    如果表是空的，返回 None。
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(scraped_at) FROM articles")
    result = cursor.fetchone()[0]
    conn.close()
    return result


# ============================================================
# 7. 用户表 —— 登录注册功能（第9课新增）
# ============================================================

def init_users_table():
    """
    创建用户表。

    UNIQUE = 唯一约束，保证用户名不重复。
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL UNIQUE,
            password_hash TEXT   NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def create_user(username, password_hash):
    """
    注册新用户。
    返回 (success, message)
    """
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        return True, "注册成功！"
    except sqlite3.IntegrityError:
        # UNIQUE 约束触发 = 用户名已存在
        return False, "用户名已被注册"
    finally:
        conn.close()


def get_user_by_username(username):
    """
    根据用户名查用户（登录时用）。
    返回 dict 或 None。
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"],
            "password_hash": row["password_hash"]}


def get_user_by_id(user_id):
    """
    根据 ID 查用户（Flask-Login 用）。
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"],
            "password_hash": row["password_hash"]}


# ============================================================
# 8. 辅助：从 CSV 导入（一次性）
# ============================================================

def import_from_csv(csv_path):
    """
    把豆瓣 CSV 数据迁入数据库。

    INSERT OR REPLACE：如果 rank 已存在就覆盖，否则新增。
    """
    import csv
    conn = get_conn()
    cursor = conn.cursor()

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            cursor.execute(
                "INSERT OR REPLACE INTO movies "
                "(rank, title, rating, rating_people, quote) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    int(row["rank"]),
                    row["title"],
                    float(row["rating"]),
                    row["rating_people"],
                    row["quote"],
                )
            )
            count += 1

    conn.commit()
    conn.close()
    print(f"已从 CSV 导入 {count} 部电影")


# ============================================================
# 直接运行本文件会初始化数据库
# ============================================================
if __name__ == "__main__":
    init_db()
    print(f"数据库已就绪：{DB_PATH}")
    print(f"当前电影数：{count_movies()}")
