import lxml.html
import sys

print sys.argv[1]
print sys.argv[2]
print lxml.html.fromstring(open(sys.argv[1], 'r').read()).xpath(sys.argv[2])
