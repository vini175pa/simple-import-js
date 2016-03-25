# If you detect any bug or run into some error, report so it can be fixed at https://github.com/vini175pa/simple-import-js

import sublime, sublime_plugin, re, os, json

IMPORT_ES6_REGEX = "import[\s]+(?P<isFromModule>\{)?[\s]*(?P<names>(([\s]*,[\s]*|[^\s\{\}\.])+))+[\s]*(?P<isFromModule2>\})?[\s]+from[\s]+(\'|\")(?P<module>.+)(\'|\")"

# Regex to ecounter an import or a require by its variable name
# double brackets are turned on one in str.format
ANY_IMPORT = "(import\s+\{{?\s*{name}\s*\}}?\s+from\s+(\"|\'){module}(\"|\')|((var|const|let)\s+)?{name}\s*=\s*require\(\s*[\'|\"]{module}[\'|\"]\s*\)([\s]*\.[\s]*\w+)?)(\s*;)?"

PENDING_STATUS = "pending"
RESOLVED_STATUS = "resolved"

DEFAULT_SETTINGS = {
	"paths" : {},
	"separator" : ";",
	"name_separator" : ":",
	"from_indicator" : "::",
	"excluded_directories" : [],
	"extensions" : [ "js" ],
	"remove_index_from_path": True,
	"search_indicator" : "@",
	"search_ignorecase_indicator" : "!",
	"settings_file"  : ".simple-import.json",
	"search_by_default" : True,
	"search_ignorecase_by_default" : True,
	"es6_by_default" : True
}

class ImportSelection:
	def __init__(self, region, index=0):
		self.region = region
		self.importObjects = []
		self.index = index
		self.status = PENDING_STATUS

	def addImportObj(self, importObj):
		self.importObjects.append(importObj)

	def resolve(self):
		self.status = RESOLVED_STATUS

	def isPending(self):
		return self.status == PENDING_STATUS

	def areImportsPending(self):
		isPending = False
		for x in self.importObjects:
			if x.isPending():
				isPending = True
				break

		return isPending

	def getImportsString(self, forceFull=True):
		string = ""
		for importObj in self.importObjects:
			if not importObj.__str__(forceFull=forceFull) in string:
				if string != "":
					string += "\n"
				string += importObj.__str__(forceFull=forceFull)

		return string

class Importation:

	@staticmethod
	def wordToModuleName(word):
		return word

	@staticmethod
	def isImportWord(word):
		match = re.match(r'{0}'.format(IMPORT_ES6_REGEX), word.strip())
		return match

	def __init__(self, word, selectionObj, alreadyImported=False, alreadyImportedObject=None, context=None):

		self.status = PENDING_STATUS
		self.searchResults = []
		self.selectionObj = selectionObj
		self.fromModule = False
		self.alternative = False
		self.searchForFiles = False
		self.onlyModel = False
		self.context = context
		self.searchFlags = {
			"caseInsesitive": SimpleImportCommand.settings.get("search_ignorecase_by_default")
		}
		self.alreadyImported = alreadyImported
		self.alreadyImportedObject = alreadyImportedObject

		word = word.strip()

		isImport = Importation.isImportWord(word)
		if isImport:
			isImport = isImport.groupdict()
			self.name = self.parseName(isImport["names"])
			self.module = isImport["module"]
			self.fromModule = isImport["isFromModule"]
			self.alternative = word.split(":")[-1] == "$"
			return
		else:
			word = word.replace(" ", "")

		self.word = word

		if word[0] == "=":
			self.onlyModel = True
			word = word[1:]

		if ":" in word:

			if "::" in word:
				word = re.split("::|:", word)
				self.fromModule = True
			else:
				word = word.split(":")


			if word[-1] == "$":
				self.alternative = True

			if not word[1] or word[1] == "$":
				word[1] = word[0]



			self.name = self.parseName(word[0])
			self.module = self.parseModule(word[1])

		else:

			if(self.context):
				if re.search(r"\=\s*{0}(\s*;\n?)?$".format(word), self.context):
					self.onlyModel = True

			self.name = self.parseName(word)
			self.module = self.parseModule(word)

	def setAlreadyImported(self, alreadyImported, alreadyImportedObject):
		self.alreadyImported = alreadyImported
		self.alreadyImportedObject = alreadyImportedObject

	def isPending(self):
		return self.status == PENDING_STATUS

	def isResolved(self):
		return self.status == RESOLVED_STATUS

	def resolve(self):
		self.status = RESOLVED_STATUS

	def setResults(self, searchResults):
		self.searchResults = searchResults

	def parseName(self, name):
		self.checkSearchForWord(name)

		# Remove some characters
		name = "".join([x for x in name if x not in ["!", "@", "*"]])

		if("/" in name):
			splited = name.split("/")
			name = splited[-1]
			if name == "index":
				name = splited[-2] or names

		if("-" in name):
			words = name.split("-")
			name = words[0]
			for word in words[1:]:
				name += word[0].upper() + word[1:]

		if("." in name):
			name = name.split(".")[0]

		return name

	def parseModule(self, module):
		self.checkSearchForWord(module)

		if(SimpleImportCommand.settings.get("search_indicator") in module):
			module = module.replace(SimpleImportCommand.settings.get("search_indicator"), "")

		if("/" not in module):
			module = module.lower()

		return module

	def checkSearchForWord(self, word):
		indicator = word[:2]
		remove_len = 0
		settings = SimpleImportCommand.settings
		search = settings.get("search_by_default")

		if settings.get("search_indicator") in indicator:
			remove_len += len(settings.get("search_indicator"))
			search = not settings.get("search_by_default")



		if settings.get("search_ignorecase_indicator") in indicator:
			self.searchFlags["caseInsesitive"] = not settings.get("search_ignorecase_by_default")
			remove_len += len(settings.get("search_ignorecase_indicator"))
			search = search and settings.get("search_by_default")


		if search:
			self.searchForFiles = True
			self.searchFor = word[remove_len:]

		return search


	def setModule(self, module, isPath=False):
		if(isPath):
			self.module = self.parsePath(module)
		else:
			self.module = module


	def parsePath(self, path):

		if path[:2] == "./" or path[:3] == "../":
			return path
		else:
			return "./" + path



	def getEs6Import(self, forceFull=False):
		name = self.name
		if self.fromModule:
			name = "{ " + self.name + " }"
		else:
			name = self.name

		if(self.onlyModel and not forceFull):
			return "\"{0}\";".format(self.module)

		return "import {0} from \"{1}\";".format(name, self.module);

	def getRequire(self, forceFull=False):
		if self.fromModule:
			end = ".{0};".format(self.name)
		else:
			end = ";"

		if(self.onlyModel and not forceFull):
			return "require(\"{0}\");".format(self.module)

		return "const {0} = require(\"{1}\"){2}".format(self.name, self.module, end)

	def __str__(self, forceFull=False):
		es6_by_default = SimpleImportCommand.settings.get("es6_by_default")

		if es6_by_default if self.alternative else not es6_by_default :
			return self.getRequire(forceFull)
		else:
			return self.getEs6Import(forceFull)

class ReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters, start=0, end=False):
      if(end == False):
        end = self.view.size()
      self.view.replace(edit,sublime.Region(start, end), characters)

class InsertAtCommand(sublime_plugin.TextCommand):
    def run(self, edit, characters, start=0):
      self.view.insert(edit, start, characters)


class SimpleImportCommand(sublime_plugin.TextCommand):

	settings = {}

	def run(self, edit, **args):

		window_vars = self.view.window().extract_variables()

		self.project_root = window_vars['folder'] if "folder" in window_vars else ""
		self.project_path_length = len(self.project_root)

		self.viewPath = "" if not self.view.file_name() else os.path.relpath(self.view.file_name(), self.project_root)
		self.viewRelativeDir = os.path.dirname(self.viewPath) if self.viewPath != "." else ""
		self.filename = os.path.basename(self.viewPath)

		self.loadSettings()

		settings = SimpleImportCommand.settings

		self.insertMode = args.get('insert')
		self.resolveMode = args.get('resolve')




		self.pendingImports = []
		self.selectionObjects = []

		if self.resolveMode:
			self.insertMode = True
			selections = self.resolveAllImports()
		else:
			selections = self.view.sel();

		selectionIndex = 0

		for selection in selections:

			selectionObj =  ImportSelection( (self.view.word(selection)  if not self.resolveMode else selection), selectionIndex)
			self.selectionObjects.append(selectionObj)

			words = re.split("{0}|\n".format(settings["separator"]), self.view.substr(selectionObj.region))


			if not words[-1]:
				words = words[:-1]


			for word in words:

				if not word:
					continue

				word = word.strip()

				context = sublime.Region(self.view.line(selection).begin(), selectionObj.region.end())
				importObj = Importation(word, selectionObj, context=self.view.substr(context))

				selectionObj.addImportObj(importObj)


				if importObj.searchForFiles and not self.resolveMode:
					searchResults = self.searchFiles(importObj.searchFor, **importObj.searchFlags)

					importObj.setResults(searchResults)
					if len(searchResults) > 1:
						self.pendingImports.append(importObj)
						self.view.show_popup_menu(searchResults, self.handleClickItem)
						continue
					elif len(searchResults) == 1:
						importObj.setModule(self.parseModulePath(searchResults[0]), True)
						importObj.resolve()
					else:
						importObj.resolve()
				else:
					importObj.resolve()
			selectionIndex += 1

		for selectionObj in self.selectionObjects:

			self.handleAllImportsForSelection(selectionObj)
			self.resolveSelection(selectionObj)


	def handleAllImportsForSelection(self, selectionObj):
		for importObj in selectionObj.importObjects:
			self.handleImportObj(importObj, selectionObj)

	def handleImportObj(self, importObj, selectionObj):
		if importObj.isPending():
			return

		alreadyImportedObject = self.findAnyImportation(importObj.name, importObj.module)
		alreadyImported = self.isAlreadyImported(alreadyImportedObject)

		importObj.setAlreadyImported(alreadyImported, alreadyImportedObject)

		if importObj.alreadyImported and not importObj.onlyModel:
			self.view.run_command("replace", {"characters": importObj.__str__(forceFull=True), "start": importObj.alreadyImportedObject.begin(), "end": importObj.alreadyImportedObject.end()})
			selectionObj.importObjects.remove(importObj)



	def resolveSelection(self, selectionObj):
		if selectionObj.areImportsPending():
			return

		if not self.resolveMode and len(selectionObj.importObjects) == 1 and (self.insertMode or selectionObj.importObjects[0].alreadyImported):
			region = self.view.word(self.view.sel()[selectionObj.index])
			self.view.run_command("replace", {"characters": selectionObj.importObjects[0].name, "start": region.begin(), "end": region.end()})

		importsString = selectionObj.getImportsString(self.insertMode)



		if importsString != "":
			if self.insertMode or selectionObj != self.selectionObjects[0]:
				importsString += "\n"
			if(self.insertMode):
				self.view.run_command("insert_at", {"characters": importsString})
			else:
				self.view.run_command("replace", {"characters": importsString, "start": selectionObj.region.begin(), "end": selectionObj.region.end()})

		selectionObj.resolve()

		allResolved = True

		for _selectionObj in self.selectionObjects:
			if _selectionObj.isPending():
				allResolved = False
				break

		if allResolved:
			self.onDone()

	def onDone(self):
		goTo = self.view.sel()[-1].end()
		self.view.sel().clear()
		self.view.sel().add(sublime.Region(goTo))
		self.selectionObjects = []


	def resolveAllImports(self):
		packageJSON = self.loadPackageJSON()

		dependencies = dict.keys(packageJSON["dependencies"])

		return self.view.find_all(r"(?<![^\s])({0})(?![^\.|\(|\s])".format("|".join(dependencies)), re.IGNORECASE);




	def loadSettings(self):

		settings = SimpleImportCommand.settings
		settings.update(DEFAULT_SETTINGS)

		sublime_settings = self.view.settings().get("simple-import") or False

		if sublime_settings:
			settings.update(sublime_settings)

		if os.path.isfile(os.path.join(self.project_root, settings["settings_file"])):

			with open(os.path.join(self.project_root, settings["settings_file"])) as data_file:
				try:
					data = json.load(data_file)
				except ValueError:
					print("SIMPLE-IMPORT ERROR :: Error trying to load {0}".format(settings["settings_file"]))
					data = {}

				pData = False
				if "paths" in data:
					for key, value in data["paths"].items():
						pData = self.resolveSettingsForPath(key, value)
						if pData:
							settings.update(pData)
							break

				if not pData:
					settings.update(data)

		return settings

	def loadPackageJSON(self):
		packageJSON = {}

		if os.path.isfile(os.path.join(self.project_root, "package.json")):
			with open(os.path.join(self.project_root, "package.json")) as data_file:
				try:
					packageJSON = json.load(data_file)
				except ValueError:
					print("SIMPLE-IMPORT ERROR :: Error trying to load {0} on project root.".format("package.json"))
					packageJSON = {}

		return packageJSON

	def resolveSettingsForPath(self, key, value, ):
		paths = None
		settings = None
		if isinstance(value, dict):
			settings = value
			if isinstance(key, list):
				paths = key
			else:
				paths = [ key ]
		elif isinstance(value, list):
			return self.resolveSettingsForPath(value[:-1], value[-1])
		else:
			return False

		return settings if re.search("^({0})".format("|".join(paths)), self.viewPath) else False





	def handleClickItem(self, index):
		importObj = self.pendingImports.pop(0)



		if(index == -1):
			importObj.selectionObj.importObjects.remove(importObj)
			self.resolveSelection(importObj.selectionObj)
			return


		importObj.setModule(self.parseModulePath(importObj.searchResults[index]), True)
		importObj.resolve()
		self.handleImportObj(importObj, importObj.selectionObj)
		self.resolveSelection(importObj.selectionObj)




	def findImportation(self, name, module):
		return self.view.find(r"{0}".format(ANY_IMPORT.format(name=name, module=module)), 0);

	def findAnyImportation(self, name, module):
		region = self.findImportation(".+", module)
		if region.begin() == -1:
			region = self.findImportation(name, ".+")
		return region

	def isAlreadyImported(self, word):
		if isinstance(word, sublime.Region):
			region = word
		else:
			region = self.findAnyImportation(".+", word)

		return region.begin() != -1 or region.end() != -1

	def searchFiles(self, search, includeViewFile=False, caseInsesitive=False):

		results = []
		searchWithFolders = False

		settings = SimpleImportCommand.settings

		_search = search.replace("/", "\/");
		_search = _search.replace("*", "");

		if not _search:
			return []

		regex = "({0}{1}|{0}\/index){2}$".format(_search, "(.)*" if search[-1] == "*" else "", "\.({0})".format("|".join(settings.get("extensions"))));

		for dirpath, dirnames, filenames in os.walk(self.project_root, topdown=True):

			crpath = dirpath[self.project_path_length + 1:] + "/" if dirpath != self.project_root else ""

			dirnames[:] = [dirname for dirname in dirnames if ( crpath + dirname  ) not in settings.get("excluded_directories")]


			for filename in filenames:
				if includeViewFile or ( not includeViewFile and crpath + filename != self.viewPath):
					if re.search(regex, crpath + filename,  re.IGNORECASE if caseInsesitive else False):
						results.append(crpath + filename)

		return results

	def parseModulePath(self, path):

		splited = path.split("/")
		filename = path if "/" not in path else splited[-1]

		if "." in filename:
			extension = filename.split(".")[-1]

			if(extension in SimpleImportCommand.settings.get("extensions")):
				path = path[: (len(extension) + 1) * -1 ]

		if "/" in path and SimpleImportCommand.settings.get("remove_index_from_path") and splited[0].strip() != "" and path.endswith("index"):
			path = path[:-6]

		return os.path.relpath(path, self.viewRelativeDir)









