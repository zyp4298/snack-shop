import pymysql
pymysql.install_as_MySQLdb()   # 让 Django 用 PyMySQL 连 MySQL（伪装成 MySQLdb）