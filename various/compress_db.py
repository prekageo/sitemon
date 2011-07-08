import sqlite3
import zlib

co=sqlite3.connect('storage.db')

c2=co.cursor()
c2.execute("delete from pages2")
c2.close()

c=co.cursor()
c.execute("select url,timestamp,content from pages")
for url,timestamp,content in c.fetchall():
  compressed = buffer(zlib.compress(content.encode('utf-8')))
  c2=co.cursor()
  c2.execute("insert into pages2 (url,timestamp,content) values (?,?,?)", (url,timestamp,compressed))
  c2.close()
c.close()

c=co.cursor()
c.execute("select pages.url,pages.timestamp,pages.content,pages2.content from pages,pages2 where pages.url=pages2.url and pages.timestamp=pages2.timestamp")
for url,timestamp,content,compressed in c.fetchall():
  a = content
  b = zlib.decompress(compressed).decode('utf-8')
  print a==b
c.close()
co.commit()
