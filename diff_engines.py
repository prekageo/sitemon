""" This module contains difference engines used by the sitemon utility. """

import difflib
import logging
import lxml.html
import mako.template
import os.path
import re
import urlparse

class BaseDiffEngine:
  """
  The BaseDiffEngine class acts as an abstract base class for writing difference
  engines.
  """

  def __init__(self, url):
    """
    Initialize a new difference engine. The URL of the page under comparison is
    stored for latter reference.
    """

    self.url = url

  def changed(self, data):
    """
    This method is called from inside the process method. It signals that there
    are differences encountered.

    data -- HTML that will be outputted next to the URL of the web site. Should
      contain an overview of the changes.
    """

    return {'status':'changed','data':data}

  def unchanged(self):
    """
    This method is called from inside the process method. It signals that there
    are no differences encountered.
    """

    return {'status':'unchanged'}

  def process(self, old, new):
    """
    This method should be overriden and should perform the comparison of the two
    pages given.
    """

    raise Exception("Unimplemented")

class Comparison(BaseDiffEngine):
  """
  The Comparison class implements a simple diff engine that compares the web
  pages line-by-line.
  """

  def process(self, old, new):
    if old == new:
      return self.unchanged()
    else:
      diff = difflib.HtmlDiff(wrapcolumn=80)
      data = diff.make_table(old.splitlines(), new.splitlines(), context=True)
      return self.changed(data)

class ForumDiffEngine(BaseDiffEngine):
  """
  The forum difference engine is a generic engine that compares forum-like pages
  which usually contain a table with rows that represents discussion topics.
  """

  def parse_row(self, row):
    """
    This method should be overriden and should parse a forum table row and
    return a topic description.
    """

    raise Exception("Unimplemented")

  def no_topic(self):
    """
    This method is called from the parse_row method and it signals that the
    current table row is not a topic.
    """

    return None,None

  def topic(self, link, title, timestamp):
    """
    This method is called from the parse_row method and it signals that the
    current table row is a topic with the given attributes.

    link -- a (relative or absolute) URL that points to the topic.
    title -- the topic title.
    timestamp -- a string that contains the timestamp or the post counter of the
      topic.
    """

    #def whitespace_clean(s):
    #  return re.sub(r'\s+', ' ', s.strip())
    key = link
    topic = {
      'link':urlparse.urljoin(self.url,link),
      'title':title,
      'timestamp':timestamp,
    }
    return key,topic

  def parse(self, html):
    """
    This method extracts the forum topics into an easy to compare dictionary.

    html -- the string containing the HTML of the page.
    """

    root = lxml.html.fromstring(html)
    tables = root.xpath(self.xpath)

    def all_children(elements):
      for element in elements:
        for child in element.iterchildren():
          yield child

    results = {}
    for row in all_children(tables):
      key,value = self.parse_row(row)
      if key is None:
        continue
      assert key not in results
      results[key] = value
    return results

  def compare(self, old, new):
    """ Compare two dictionaries and return the differences. """

    results = []
    set_old = set(old)
    for key in new:
      if key in old:
        set_old.remove(key)
        if new[key] != old[key]:
          # Changed topics
          results.append(new[key])
      else:
        # Inserted topics
        results.append(new[key])
    for key in set_old:
      # Deleted topics are ignored. Usually they are just topics that appear in
      # the next page.
      pass
    return len(results)>0,results

  def parse_and_compare(self, old, new):
    """
    Combine the parse and compare methods into one step.

    old -- the old web page.
    new -- the new web page.
    """

    parsed_new = self.parse(new)
    for parsed_new_row in self.parse(old).itervalues():
      logging.debug('Row: %s, Timestamp: %s', parsed_new_row['title'], parsed_new_row['timestamp'])
    changed,diff_results = self.compare(self.parse(old), parsed_new)
    if not changed:
      return self.unchanged()
    else:
      filename = os.path.join(os.path.dirname(__file__),
        'template.forumdiff.html')
      template = mako.template.Template(filename=filename)
      return self.changed(template.render(diff_results=diff_results))

class DiffInvision(ForumDiffEngine):
  def process(self, old, new):
    self.xpath = '//*[@id="forum_table"]'
    return self.parse_and_compare(old, new)

  def parse_row(self, row):
    link = row.cssselect('.topic_title')
    if len(link) == 0:
      return self.no_topic()
    link = link[0]

    return self.topic(link.attrib['href'], link.text, row.xpath('descendant::a[contains(@href,"do=who")]')[0].text)

class DiffVBulletin(ForumDiffEngine):
  def process(self, old, new):
    self.xpath = '//*[@id="threadslist"]/tbody[last()]'
    return self.parse_and_compare(old, new)

  def parse_row(self, row):
    link = row.xpath('descendant::*[starts-with(@id,"thread_title")]')
    if len(link) == 0:
      return self.no_topic()
    link = link[0]

    timestamp = row.xpath('descendant::a[contains(@href,"do=whoposted")]')
    if len(timestamp) == 0:
      return self.no_topic()
    timestamp = timestamp[0]

    return self.topic(link.attrib['href'], link.text, timestamp.text)

class DiffVBulletin4(DiffVBulletin):
  def process(self, old, new):
    self.xpath = '//*[@id="threads" or @id="stickies"]'
    return self.parse_and_compare(old, new)

class DiffPHPBB(ForumDiffEngine):
  def __init__(self, url, xpath):
    self.xpath = xpath
    ForumDiffEngine.__init__(self, url)

  def process(self, old, new):
    return self.parse_and_compare(old, new)

  def parse_row(self, row):
    link = row.cssselect('a.topictitle')
    if len(link) == 0:
      return self.no_topic()
    link = link[0]
    href = re.sub(r'&sid=[0-9a-fA-F]+', '', link.attrib['href'])
    return self.topic(href, link.text, row[4][0].text.strip())

class DiffDNZ(ForumDiffEngine):
  def process(self, old, new):
    self.xpath = '/html/body/form/div[2]/div[2]/table/tr/td[2]/table/tr/td/div/div[2]/div[5]/table/tbody'
    return self.parse_and_compare(old, new)

  def parse_row(self, row):
    link = row[1][0][0][0].xpath('a')
    if len(link) == 0:
      return self.no_topic()
    link = link[0]
    return self.topic(link.attrib['href'], link.text.strip(), row[1][1][0][0].text_content().strip())

class DiffPcmag(ForumDiffEngine):
  def process(self, old, new):
    self.xpath = '/html/body/div/div/div[4]/div/div[3]/div[2]/div[2]/div[4]/div[3]/div/table/tbody'
    return self.parse_and_compare(old, new)

  def parse_row(self, row):
    link = row.cssselect('.views-field-title a')
    if len(link) == 0:
      return self.no_topic()
    link = link[0]
    return self.topic(link.attrib['href'], link.text_content(), row[2].text_content().strip())
