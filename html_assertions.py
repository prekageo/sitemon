def assert_by_id(node, id, tag=None, attribs={}):
  """
  Asserts the presence of a specific node in an HTML document.
  node -- the root node of the HTML document
  id -- the id of the node looked for
  tag -- if given, will match the tag of the node found with this value
  attribs -- the node found should have the given attributes
  """

  try:
    element = node.get_element_by_id(id)
    if tag != None and element.tag != tag:
      raise Exception('Tag mismatch. Expected "%s". Got "%s".' % (tag,
          element.tag))
    for attrib in attribs:
      if element.attrib.get(attrib) != attribs[attrib]:
        raise Exception('Attribute "%s" mismatch. Expected "%s". Got "%s".' %
            (attrib,attribs[attrib],element.attrib.get(attrib)))

  except KeyError:
    raise Exception('Node with ID "%s" not found in document.' % id)

def assert_by_xpath(node, xpath):
  """
  Asserts the presence of at least one node that matches the given XPath.
  node -- the root node of the HTML document
  xpath -- the XPath expression
  """

  if len(node.xpath(xpath)) == 0:
    raise Exception('XPath "%s" not found in document.' % xpath)
