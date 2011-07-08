import sqlite3

def main():
  conn = sqlite3.connect('storage.db')
  c = conn.cursor()
  c.execute('select distinct url from pages')
  for url, in c.fetchall():
    c2 = conn.cursor()
    c2.execute('select timestamp from pages where url=? order by timestamp desc limit -1 offset 2',(url,))
    timestamp = c2.fetchone()
    c2.close()
    if timestamp == None:
      continue
    timestamp,=timestamp

    c3 = conn.cursor()
    c3.execute('delete from pages where url=? and timestamp<=?',(url,timestamp))
    c3.close()

  c4 = conn.cursor()
  c4.execute('vacuum')
  c4.close()
  conn.commit()

if __name__ == '__main__':
  main()