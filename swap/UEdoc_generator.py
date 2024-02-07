#!/usr/local/bin/python

import sys, os, getopt, signal, time, re, sqlite3
import distutils.core
import xml.etree.cElementTree as ET
from bs4 import BeautifulSoup, NavigableString, Tag

# The categories that can be found in the ClassHierarchy/index.html file.
maincategories = {
	"Class": [
		re.compile("^.*class .+$", re.MULTILINE), 
		re.compile("^.*UCLASS.*$", re.MULTILINE)],
	"Struct": [
		re.compile("^.*struct .+$", re.MULTILINE),
		re.compile("^.*USTRUCT.*$", re.MULTILINE)],
	"Union": [
		re.compile("^.*union .+$", re.MULTILINE)]
}

class detail:
	def __init__(self, htmlname, indexname, regexps):
		self.htmlname = htmlname
		self.indexname = indexname
		self.regexps = regexps

# Additional detail categories, that can be found in each of the referenced files.
detailcategories = [
	detail("constructor", "Constructor", []),
	detail("constants", "Constant", []),
	detail("variables", "Variable", []),
	detail("methods", "Method", []),
	detail("operators", "Operator", []),
	detail("functions_0", "Function", []),
	detail("functions_1", "Function", []),
	detail("functions_2", "Function", []),
	# detail("destructor", "Destructor", []),
	detail("typedefs", "Typedefs", []),
	detail("enums", "Enum", []),
	detail("classes", "Class", [])
]

functionItemList=["typedefs","enums","constants","variables","constructor","operators","functions_0","functions_1","functions_2"]
# ShowParentName=["Union","Struct"]
ShowParentName=[]
DontFromIHGetName=["Class"]

def rmMulitSpace(str):
	tvar=str
	tvar=tvar.replace('  ','')
	tvar=tvar.replace(' &gt;','&gt;')
	return tvar

htmlroot = None
docsetpath = None
docpath = None
dbpath = None
db = None
cur = None
count = 0
verbose = 0

def usage():
	print 'Usage: ue4docset.py [options] <htmlroot> <docsetpath>\n'
	print ('\tParses the extracted chm documentation at ' + '\033[4m' + 'htmlroot' + '\033[0m' +
		' and generates a docset at ' + '\033[4m' + 'docsetpath' + '\033[0m' + '.')
	print '\nOptions:'
	print '\t-i\tDocumentation identifier.'
	print '\t-n\tDocumentation display name.'
	print '\t-s\tDocumentation version.'
	print '\t-f\tFallback URL.'
	print '\t-v\tVerbose.'
	print '\nExample:'
	print '\tue4docset.py -n "Unreal Engine" -s "4.0.2" ~/Desktop/HTML ~/Desktop/UE4.docset'

def signal_handler(signal, frame):
    print('\nAborted by user.')
    sys.exit(2)
signal.signal(signal.SIGINT, signal_handler)

# Generate an Info.plist file from the passed, optional parameters.
def generate_plist(opts):
	print "Generating Info.plist"
	identifier = "com.epic.unrealengine4"
	name = "UE4"
	fallbackURL = "https://docs.unrealengine.com/latest/en-US/"
	version = None

	for o, a in opts:
		if o == "-i":
			identifier = a
		elif o == "-n":
			name = a
		elif o == "-s":
			version = a
		elif o == "-f":
			fallbackURL = a

	plistpath = os.path.join(docsetpath, "Contents/Info.plist")
	plist = ET.Element("plist")
	plist.set("version", "1.0")
	root = ET.SubElement(plist, "dict")

	key = ET.SubElement(root, "key")
	key.text = "CFBundleIdentifier"
	string = ET.SubElement(root, "string")
	string.text = identifier

	key = ET.SubElement(root, "key")
	key.text = "CFBundleName"
	string = ET.SubElement(root, "string")
	string.text = name

	if not version is None:
		key = ET.SubElement(root, "key")
		key.text = "CFBundleShortVersionString"
		string = ET.SubElement(root, "string")
		string.text = version
		key = ET.SubElement(root, "key")
		key.text = "CFBundleVersion"
		string = ET.SubElement(root, "string")
		string.text = version

	key = ET.SubElement(root, "key")
	key.text = "DashDocSetFamily"
	string = ET.SubElement(root, "string")
	string.text = "appledoc"

	key = ET.SubElement(root, "key")
	key.text = "DocSetPlatformFamily"
	string = ET.SubElement(root, "string")
	string.text = name

	key = ET.SubElement(root, "key")
	key.text = "DocSetFallbackURL"
	string = ET.SubElement(root, "string")
	string.text = fallbackURL

	key = ET.SubElement(root, "key")
	key.text = "dashIndexFilePath"
	string = ET.SubElement(root, "string")
	string.text = "en-US/API/QuickStart/index.html"

	key = ET.SubElement(root, "key")
	key.text = "isDashDocset"
	value = ET.SubElement(root, "true")

	tree = ET.ElementTree(plist)
	with open(plistpath, "w") as f:
		f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
		f.write('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">')
		tree.write(f, 'utf-8')

# Try to find out which category (class, struct..) a doc page belongs to, by parsing its the syntax.
def guess_category(syntax):
	for category, regexps in maincategories.iteritems():
		for regexp in regexps:
			if regexp.search(syntax):
				return category
	return None

# Insert an entry into the documentation index database.
def insert_index(name, category, path):
	global verbose
	if not os.path.isfile(os.path.join(docpath, path)):
		if verbose:
			print "Documenation at path " + path + " does not exist. Skipping."
		return
	global count
	if verbose:
		print (str(count) + ": Found " + category + 
			(" " * (15 - len(category))) + name + 
			(" " * (40 - len(name))) + " at " + path)
	cur.execute("INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?,?,?)",(name, category, path))
	count += 1

def rmP(str):
	return str.replace('<p>','').replace('</p>','')

def getPageItemName(pagesoup):
	if len(pagesoup.find_all(id='hierarchy')) is 0:
		pageMetaList=pagesoup.find_all(name="meta")
		retName=pagesoup.title.text[:pagesoup.title.text.find('|')-1]
		for index in pageMetaList:
			if index.get('property') is not None and index.get('property') == 'og:title':
				retName = index.get('content')
	else:
		all_hierarchy=pagesoup.find_all(id='hierarchy')
		for all_hierarchy_index in all_hierarchy:
			hierarchy_label_cell=all_hierarchy_index.find_all(class_='hierarchy-label-cell')
			for index in hierarchy_label_cell[::-1]:
				isBreak=False
				for index_2 in index.contents:
					if index_2.find("td",attrs={"class":"hierarchy-label-cell"}) is None and index_2.get('href') is None:
						retName=rmP(index_2.text)
						isBreak=True
						break
				if isBreak:
					break
				else:
					continue
	return retName

# Find all the additional categories of a specific type (methods, variables, etc.) in a class doc page.
def parse_file_detail(abspath, soup, detail,soupPageName):
	try:
		# 	print soup.title.text[:soup.title.text.find("|")];
		for normalrow in soup.find(id=detail.htmlname).find_all(class_="normal-row"):
			namecell=normalrow.find_all(class_="name-cell")[len(normalrow.find_all(class_="name-cell"))-1]
			IndexName=""
			if namecell.a:
				name = namecell.a.text
				relpath = namecell.a['href']
				thepath = os.path.relpath(os.path.normpath(os.path.join(os.path.dirname(abspath), relpath)), htmlroot)
				if detail.htmlname in functionItemList:
					CurrClassName=soupPageName;
					IndexName=CurrClassName+"::"+name
				else:
					CurrClassName=soupPageName;
					childpage=open(thepath)
					childSoup=BeautifulSoup(childpage);
					IndexName=CurrClassName+"::"+getPageItemName(childSoup)
			else:
				# Index no html variable/Function
				itemName=namecell.text
				if detail.htmlname in ShowParentName or detail.htmlname in functionItemList:
					className=soup.title.text[:soup.title.text.find("|")-1];
					thepath = os.path.relpath(os.path.normpath(os.path.join(os.path.dirname(abspath))), htmlroot)+"\\index.html"
					IndexName=className+"::"+itemName.split()[0]
			if IndexName != "":
				insert_index(rmMulitSpace(IndexName), detail.indexname, thepath)
	except Exception: pass

# parse file member and index.
# Go through the doc page of a class/struct and parse all the methods, variables etc..
def parse_file_details(abspath, soup,soupPageName):
	for detail in detailcategories:
		parse_file_detail(abspath, soup, detail,soupPageName)

# Parse a class/struct doc page. Find its name in the H1 tag, guess its category based on the syntax.
def parse_file(abspath):
	try:
		page = open(abspath)
		soup = BeautifulSoup(page);

		name = soup.find(id="H1TitleId").text

		cattext = soup.find(class_='simplecode_api').text
		category = guess_category(cattext)
		if category is not None and name is not None:
			thepath = os.path.relpath(abspath, htmlroot)
			if category in DontFromIHGetName:
				IndexName=name
			else:
				IndexName=getPageItemName(soup)
			insert_index(rmMulitSpace(IndexName), category, thepath)
			parse_file_details(abspath, soup,IndexName)

	except Exception: pass

def print_progress(progress):
	global verbose
	if not verbose:
		p = int(progress * 100)
		sys.stdout.write('\r')
		sys.stdout.write("[%-50s] %d%% " % ('='*(p/2), p))
		sys.stdout.flush()

# Go thought all the links of an index file (ClassHierarchy/index.html) and parse all linked doc pages.
def scrape_index_file(abspath):
	# print "Scraping file at " + abspath
	page = open(abspath)
	soup = BeautifulSoup(page)
	links = soup.find_all('a')
	for idx, link in enumerate(links):
		print_progress(float(idx) / float(len(links)))
		relpath = link['href']
		if not relpath.startswith('javascript') and not relpath.startswith('http'):
			foundpath = os.path.normpath(os.path.join(os.path.dirname(abspath), relpath))
			parse_file(foundpath)
	print_progress(1.0)
	print ''

def scrape_folder(abspath):
	for dirName, subdirList, fileList in os.walk(abspath):
		for fileName in fileList:
			parse_file(os.path.join(dirName, fileName))

def parse_struct_union_parent_name(soup):
	links = soup.find("link",rel="alternate")
	if links is not None:
		parentlinks=links['href']
		lastItem=parentlinks.split('/')
		return lastItem[len(lastItem)-3]

def main():
	global htmlroot
	global docsetpath, docpath, dbpath
	global db, cur
	global verbose
	try:
		opts, args = getopt.getopt(sys.argv[1:], "vi:n:s:f:")
		if len(args) < 2:
			usage()
			sys.exit(2)

		htmlroot = args[0]
		if not os.path.isdir(os.path.join(htmlroot, 'en-US')):
			print 'Error: Extracted CHM documentation not found. Did you specify the correct path?',
			print 'It should contain a number of files with a # prefix and a folder called INT'
			sys.exit(2)

		docsetpath = args[1]
		docsetname, docsetext = os.path.splitext(docsetpath)
		if not docsetext == '.docset':
			print 'Error: docsetpath argument should specify the path of the docset file.',
			print 'E.g. ~/Desktop/UE4.docset'
			sys.exit(2)

		for o, a in opts:
			if o == "-v":
				verbose = 1

	except getopt.GetoptError as err:
	        print str(err)
	        usage()
	        sys.exit(2)

	docpath = os.path.join(docsetpath, "Contents/Resources/Documents")
	if not os.path.exists(docpath):
		os.makedirs(docpath)

	dbpath = os.path.join(docsetpath, "Contents/Resources/docSet.dsidx")
	print 'Copying documentation from ' + htmlroot + ' to ' + docpath + '.'
	print 'This may take a few minutes.'
	distutils.dir_util.copy_tree(htmlroot, docpath)

	chmroot = os.path.join(htmlroot, 'en-US/API')
	classlistpath = os.path.join(chmroot, 'ClassHierarchy/')
	classlistindex = os.path.join(classlistpath, 'index.html')

	generate_plist(opts)

	db = sqlite3.connect(dbpath)
	cur = db.cursor()

	try: cur.execute('DROP TABLE searchIndex;')
	except: pass

	cur.execute('CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT);')
	cur.execute('CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path);')

	print 'Indexing documentation'
	#time.sleep(3)

	scrape_index_file(classlistindex)
	#scrape_folder(chmroot)

	db.commit()
	db.close()


start_time = time.time();
main();
print "Generation took", time.time() - start_time, "seconds."