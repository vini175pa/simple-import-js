import sublime, sublime_plugin, re, json
from os import path
from .lib.interpreter.SImport import SImport
from .lib.interpreter.Interpreted import Interpreted
from .lib.SimpleImport import SimpleImport


class PendingImport:

  key_str = {
    "files": "Import",
    "modules": "Import Module",
    "containing_files": "Import From",
    "extra_files": "Import"
  }

  def __init__(self, interpreted, options):
    self.interpreted = interpreted
    self.options = options
    self.resolved = False

  def getOptionsArr(self):
    arr = []
    for key in self.options:
      arr = arr + [ "{key}: {value}".format(key=PendingImport.key_str[key], value=option) for option in self.options[key] ]
    return arr

  def getOptionByIndex(self, index):
    i = 0
    for key in self.options:
      length = len(self.options[key])
      if index < length:
        return { "key": key, "value": self.options[key][index]  }
      index = index - length

class SimpleImportCommand(sublime_plugin.TextCommand):

  def run(self, edit, no_replace_mode=False):
    self.NO_REPLACE_MODE = no_replace_mode
    self.project_path = self.view.window().folders()[-1]
    self.view_path = path.dirname(self.view.file_name())
    self.view_dir_relpath = path.relpath(self.view_path, self.project_path)
    self.view_filename = path.basename(self.view.file_name())
    view_syntax = path.basename(self.view.settings().get('syntax')).lower()

    self.interpreter = SimpleImport.getInterpreter(
      # Selected syntax
      view_syntax,
      # Filename
      self.view_filename
    )

    if not self.interpreter:
      print("Simple import does not support '.{0}' syntax yet".format(view_syntax))
      return

    selections = self.view.sel()
    self.view_imports = self.findAllImports()
    self.interpreted_list = []
    self.pending_imports = []
    self.imports_to_insert = []

    for selection in selections:
      if selection.end() == selection.begin():
        region = self.view.word(selection)
        context_region = sublime.Region(self.view.line(selection).begin(), region.end())
      else:
        region = selection
        context_region = selection

      simport = SImport(
        # expression
        self.view.substr(region),
        # context
        self.view.substr(context_region),
        region,
        context_region
      )

      if not len(simport.expression.strip()):
        continue

      interpreted = self.interpreter.interprete(simport)
      self.interpreted_list.append(interpreted)

      query = self.interpreter.getQueryObject(interpreted)

      if query != False:
        pending_import = PendingImport(
          interpreted,
          SimpleImport.query(
            query,
            self.interpreter,
            self.project_path,
            exclude=path.join(path.join(self.view_dir_relpath, self.view_filename))
          )
        )

        self.pending_imports.append(pending_import)


    for pending_import in self.pending_imports:
      options_arr = pending_import.getOptionsArr()

      if len(options_arr) > 1:
        self.view.show_popup_menu(options_arr, self.handleOptionClick)
      else:
        self.handleOptionClick(len(options_arr) - 1)

  def handleOptionClick(self, index):
    for pending_import in self.pending_imports:
      if not pending_import.resolved:
        pending_import.resolved = True
        if index != -1:
          option_obj = pending_import.getOptionByIndex(index)

          # Make every path relative to view file
          if option_obj["key"] != "modules":
            option_obj["value"] = self.parsePath(
              path.normpath(
                path.relpath(
                  option_obj["value"],
                  self.view_dir_relpath
                )
              )
            )

          self.interpreter.onSearchResultChosen(
            pending_import.interpreted,
            option_obj['key'],
            option_obj['value']
          )
        break

    if False not in [ pending.resolved for pending in self.pending_imports ]:
      self.onPendingImportsResolved()

  def onPendingImportsResolved(self):
    for interpreted in self.interpreted_list:
      resolved_interpreted = self.interpreter.resolveSimilarImports(
        interpreted,
        self.view_imports,
        NO_REPLACE_MODE=self.NO_REPLACE_MODE
      )

      if resolved_interpreted not in self.imports_to_insert:
        self.imports_to_insert.append(resolved_interpreted)

    for interpreted in self.imports_to_insert:
      self.handleInsertion(interpreted)

  def handleInsertion(self, interpreted):
    if interpreted.insert_type == Interpreted.IT_INSERT:
      self.view.run_command("insert_at", {
        "characters": interpreted.__str__()
      })
    else:
      self.view.run_command("replace", {
        "characters": interpreted.__str__(),
        "start": interpreted.simport.context_region.begin(),
        "end": interpreted.simport.context_region.end()
      })

  def parsePath(self, path):
    if path[:2] == "./" or path[:3] == "../":
      return path
    else:
      return "./" + path

  def findAllImports(self):
    if not self.interpreter.find_imports_regex:
      return []

    regions = self.view.find_all(self.interpreter.find_imports_regex)
    return [
      self.interpreter.interprete(
        SImport(
          self.view.substr(region),
          self.view.substr(region),
          region,
          region
        )
      )
        for region in regions
    ]

class ReplaceCommand(sublime_plugin.TextCommand):
  def run(self, edit, characters, start=0, end=False):
    if(end == False and end != 0):
      end = self.view.size()
    self.view.replace(edit,sublime.Region(start, end), characters)

class InsertAtCommand(sublime_plugin.TextCommand):
  def run(self, edit, characters, start=0):
    self.view.insert(edit, start, characters)

SimpleImport.loadInterpreters()
