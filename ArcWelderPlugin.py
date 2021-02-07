# Copyright (c) 2020 Aldo Hoeben / fieldOfView
# The ArcWelderPlugin for Cura is released under the terms of the AGPLv3 or higher.

from collections import OrderedDict
import json
import tempfile
import os
import stat
import subprocess
import locale
import re

from UM.Extension import Extension
from UM.Application import Application
from UM.Settings.SettingDefinition import SettingDefinition
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Settings.ContainerRegistry import ContainerRegistry
from UM.Logger import Logger
from UM.Platform import Platform

from typing import Dict, List, Any

class ArcWelderPlugin(Extension):
    def __init__(self):
        super().__init__()

        self._application = Application.getInstance()

        self._i18n_catalog = None

        settings_definition_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arcwelder_settings.def.json")
        try:
            with open(settings_definition_path, "r", encoding = "utf-8") as f:
                self._settings_dict = json.load(f, object_pairs_hook = OrderedDict)
        except:
            Logger.logException("e", "Could not load arc welder settings definition")
            return

        if Platform.isWindows():
            arcwelder_executable = "bin/win64/ArcWelder.exe"
        elif Platform.isLinux():
            arcwelder_executable = "bin/linux/ArcWelder"
        elif Platform.isOSX():
            arcwelder_executable = "bin/osx/ArcWelder"

        self._arcwelder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), arcwelder_executable)
        try:
            os.chmod(self._arcwelder_path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR)  # Make sure we have the rights to run this.
        except:
            Logger.logException("e", "Could modify rights of ArcWelder executable")
            return
        version_output = subprocess.check_output([self._arcwelder_path, "--version"]).decode(locale.getpreferredencoding())
        match = re.search("version: (.*)", version_output)
        if match:
            Logger.log("d", "Using ArcWelder %s" % match.group(1))
        else:
            Logger.log("w", "Could not determine ArcWelder version")

        self._application.getPreferences().addPreference("arcwelderplugin/settings_made_visible", False)

        ContainerRegistry.getInstance().containerLoadComplete.connect(self._onContainerLoadComplete)
        self._application.getOutputDeviceManager().writeStarted.connect(self._filterGcode)


    def _onContainerLoadComplete(self, container_id: str) -> None:
        if not ContainerRegistry.getInstance().isLoaded(container_id):
            # skip containers that could not be loaded, or subsequent findContainers() will cause an infinite loop
            return

        try:
            container = ContainerRegistry.getInstance().findContainers(id = container_id)[0]
        except IndexError:
            # the container no longer exists
            return

        if not isinstance(container, DefinitionContainer):
            # skip containers that are not definitions
            return
        if container.getMetaDataEntry("type") == "extruder":
            # skip extruder definitions
            return

        try:
            category = container.findDefinitions(key="blackmagic")[0]
        except IndexError:
            Logger.log("e", "Could not find parent category setting to add settings to")
            return

        for setting_key in self._settings_dict.keys():
            setting_definition = SettingDefinition(setting_key, container, category, self._i18n_catalog)
            setting_definition.deserialize(self._settings_dict[setting_key])

            # add the setting to the already existing blackmagic settingdefinition
            # private member access is naughty, but the alternative is to serialise, nix and deserialise the whole thing,
            # which breaks stuff
            category._children.append(setting_definition)
            container._definition_cache[setting_key] = setting_definition

            self._expanded_categories = self._application.expandedCategories.copy()
            self._updateAddedChildren(container, setting_definition)
            self._application.setExpandedCategories(self._expanded_categories)
            self._expanded_categories.clear()
            container._updateRelations(setting_definition)

        preferences = self._application.getPreferences()
        if not preferences.getValue("arcwelderplugin/settings_made_visible"):
            setting_keys = self._getAllSettingKeys(self._settings_dict)

            visible_settings = preferences.getValue("general/visible_settings")
            visible_settings_changed = False
            for key in setting_keys:
                if key not in visible_settings:
                    visible_settings += ";%s" % key
                    visible_settings_changed = True

            if visible_settings_changed:
                preferences.setValue("general/visible_settings", visible_settings)

            preferences.setValue("arcwelderplugin/settings_made_visible", True)


    def _updateAddedChildren(self, container: DefinitionContainer, setting_definition: SettingDefinition) -> None:
        children = setting_definition.children
        if not children or not setting_definition.parent:
            return

        # make sure this setting is expanded so its children show up  in setting views
        if setting_definition.parent.key in self._expanded_categories:
            self._expanded_categories.append(setting_definition.key)

        for child in children:
            container._definition_cache[child.key] = child
            self._updateAddedChildren(container, child)


    def _getAllSettingKeys(self, definition: Dict[str, Any]) -> List[str]:
        children = []
        for key in definition:
            children.append(key)
            if "children" in definition[key]:
                children.extend(self._getAllSettingKeys(definition[key]))
        return children


    def _filterGcode(self, output_device):
        scene = self._application.getController().getScene()

        global_container_stack = self._application.getGlobalContainerStack()
        if not global_container_stack:
            return

        arcwelder_enable = global_container_stack.getProperty("arcwelder_enable", "value")
        if not arcwelder_enable:
            Logger.log("d", "ArcWelder is not enabled")
            return

        maximum_radius = global_container_stack.getProperty("arcwelder_maximum_radius", "value")
        path_tolerance = global_container_stack.getProperty("arcwelder_tolerance", "value") / 100
        resolution = global_container_stack.getProperty("arcwelder_resolution", "value")
        min_arc_segment = int(global_container_stack.getProperty("arcwelder_min_arc_segment", "value"))
        mm_per_arc_segment = global_container_stack.getProperty("arcwelder_mm_per_arc_segment", "value")
        allow_3d_arcs = global_container_stack.getProperty("arcwelder_allow_3d_arcs", "value")
        g90_influences_extruder = global_container_stack.getProperty("arcwelder_g90_influences_extruder", "value")

        # If the scene does not have a gcode, do nothing
        gcode_dict = getattr(scene, "gcode_dict", {})
        if not gcode_dict: # this also checks for an empty dict
            Logger.log("w", "Scene has no gcode to process")
            return

        dict_changed = False

        layer_separator = ";ARCWELDERPLUGIN_GCODELIST_SEPARATOR\n"
        processed_marker = ";ARCWELDERPROCESSED\n"

        for plate_id in gcode_dict:
            gcode_list = gcode_dict[plate_id]
            if len(gcode_list) < 2:
                Logger.log("w", "Plate %s does not contain any layers", plate_id)
                continue

            if processed_marker in gcode_list[0]:
                Logger.log("d", "Plate %s has already been processed", plate_id)
                continue

            if len(gcode_list) > 0:
                # remove header from gcode, so we can put it back in front after processing
                header = gcode_list.pop(0)
            else:
                header = ""
            joined_gcode = layer_separator.join(gcode_list)

            file_descriptor, temporary_path = tempfile.mkstemp()
            Logger.log("d", "Using temporary file %s", temporary_path)

            with os.fdopen(file_descriptor, 'w', encoding = "utf-8") as temporary_file:
                temporary_file.write(joined_gcode)

            command_arguments = [
                self._arcwelder_path,
                "-m=%f" % maximum_radius,
                "-t=%f" % path_tolerance,
                "-r=%f" % resolution,
            ]

            if min_arc_segment>0 :
                command_arguments.extend([
                    "-s=%f" % mm_per_arc_segment,
                    "-a=%d" % min_arc_segment
                ])

            if allow_3d_arcs :
                command_arguments.append("-z")

            if g90_influences_extruder:
                command_arguments.append("-g")

            command_arguments.append(temporary_path)

            Logger.log("d", "Running ArcWelder with the following options: %s" % command_arguments)
            process_output = subprocess.check_output(command_arguments).decode(locale.getpreferredencoding())
            Logger.log("d", process_output)

            with open(temporary_path, "r", encoding = "utf-8") as temporary_file:
                result_gcode = temporary_file.read()
            os.remove(temporary_path)

            gcode_list = result_gcode.split(layer_separator)
            if header != "":
                gcode_list.insert(0, header) # add header back in front
            gcode_list[0] += processed_marker
            gcode_dict[plate_id] = gcode_list
            dict_changed = True

        if dict_changed:
            setattr(scene, "gcode_dict", gcode_dict)
