import unittest

from backend import database


class DatabaseQueryTests(unittest.TestCase):
    def test_postgres_queries_use_percent_s_placeholders(self):
        sql = "SELECT * FROM users WHERE id = ?"
        self.assertEqual(database._prepare_query(sql, is_postgres=True), "SELECT * FROM users WHERE id = %s")

    def test_sqlite_queries_keep_question_mark_placeholders(self):
        sql = "SELECT * FROM users WHERE id = ?"
        self.assertEqual(database._prepare_query(sql, is_postgres=False), "SELECT * FROM users WHERE id = ?")


if __name__ == "__main__":
    unittest.main()
