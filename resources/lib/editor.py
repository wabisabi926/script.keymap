# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Thomas Amland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import xbmc
import xbmcaddon
from threading import Timer
from collections import OrderedDict
from xbmcgui import Dialog, WindowXMLDialog
from resources.lib.actions import ACTIONS, WINDOWS, FREQUENT_CATEGORY
from resources.lib.actions import (
    load_custom_actions, add_custom_action, delete_custom_action
)
from resources.lib.utils import tr, settings

KODIMONITOR = xbmc.Monitor()

class Editor(object):
    def __init__(self, defaultkeymap, userkeymap):
        """Create the editor object."""
        self.defaultkeymap = defaultkeymap
        self.userkeymap = userkeymap
        self.dirty = False

    def start(self):
        while not KODIMONITOR.abortRequested():
            # Select context menu
            idx = Dialog().select(tr(30007), list(WINDOWS.values()))
            if idx == -1:
                break
            window = list(WINDOWS.keys())[idx]

            while not KODIMONITOR.abortRequested():
                # Select category menu
                idx = Dialog().select(tr(30008), list(ACTIONS.keys()))
                if idx == -1:
                    break
                category = list(ACTIONS.keys())[idx]
                is_frequent_category = (category == tr(FREQUENT_CATEGORY))

                while not KODIMONITOR.abortRequested():
                    # Select action menu
                    current_keymap = self._current_keymap(window, category)
                    labels = ["%s - %s" % (name, key)
                              for _, key, name in current_keymap]
                    
                    # Add custom operations management entry only in Frequent category
                    if is_frequent_category:
                        labels.append(tr(34001))  # Custom operations (add/delete)
                    
                    idx = Dialog().select(tr(30009), labels)
                    if idx == -1:
                        break
                    
                    # Handle custom operations management in Frequent category
                    if is_frequent_category and idx == len(current_keymap):
                        new_action = self._custom_operations_manager()
                        if new_action:
                            # Auto-bind the newly added custom action
                            newkey = KeyListener.record_key()
                            if newkey:
                                if self._long_press():
                                    newkey += ' + longpress'
                                self.userkeymap.append((window, new_action, newkey))
                                self.dirty = True
                        continue
                    
                    action, current_key, _ = current_keymap[idx]
                    old_mapping = (window, action, current_key)

                    # Check if this specific action is a user-added custom one
                    from resources.lib.actions import _custom_actions_cache
                    is_custom_action = any(item["action"] == action for item in _custom_actions_cache)

                    # Ask what to do
                    options = [tr(30011), tr(30012)]
                    if is_custom_action:
                        options.append(tr(34003))  # Only for user-added custom actions
                    idx2 = Dialog().select(tr(30000), options)
                    if idx2 == -1:
                        continue
                    elif idx2 == 1:
                        # Remove key mapping
                        if old_mapping in self.userkeymap:
                            self.userkeymap.remove(old_mapping)
                            self.dirty = True
                    elif idx2 == 2:
                        # Delete custom action entirely (only option 2 when is_custom_action)
                        delete_custom_action(action)
                        if old_mapping in self.userkeymap:
                            self.userkeymap.remove(old_mapping)
                        self.dirty = True
                        self._refresh_actions()
                        continue
                    elif idx2 == 0:
                        # Edit key
                        newkey = KeyListener.record_key()
                        if newkey is None:
                            continue
                        if self._long_press():
                            newkey += ' + longpress'

                        new_mapping = (window, action, newkey)
                        if old_mapping in self.userkeymap:
                            self.userkeymap.remove(old_mapping)
                        self.userkeymap.append(new_mapping)
                        if old_mapping != new_mapping:
                            self.dirty = True

    def _refresh_actions(self):
        load_custom_actions()
        global ACTIONS
        import resources.lib.actions as _actions_mod
        ACTIONS = _actions_mod.ACTIONS

    def _custom_operations_manager(self):
        """Add one new custom operation, return its action string or None."""
        name = Dialog().input(tr(34004))
        if not name or not name.strip():
            return None
        action_str = Dialog().input(tr(34005))
        if not action_str or not action_str.strip():
            return None
        add_custom_action(name.strip(), action_str.strip())
        self._refresh_actions()
        return action_str.strip()

    def _current_keymap(self, window, category):
        actions = OrderedDict([(action, "")
                              for action in ACTIONS[category].keys()])
        names = ACTIONS[category].copy()
        
        for w, a, k in self.defaultkeymap:
            if w == window:
                if a in actions.keys():
                    actions[a] = k
        for w, a, k in self.userkeymap:
            if w == window:
                if a in actions.keys():
                    actions[a] = k
        
        return [(action, key, names[action]) for action, key in actions.items()]

    def _long_press(self):
        if settings('longpress') == 'true':
            lp = Dialog().yesno(tr(30013), tr(30014))
            if lp:
                return True
        return False



class KeyListener(WindowXMLDialog):
    TIMEOUT = 5

    def __new__(cls):
        gui_api = tuple(map(int, xbmcaddon.Addon(
            'xbmc.gui').getAddonInfo('version').split('.')))
        file_name = "DialogNotification.xml" if gui_api >= (
            5, 11, 0) else "DialogKaiToast.xml"
        return super(KeyListener, cls).__new__(cls, file_name, "")

    def __init__(self):
        """Initialize key variable."""
        self.key = None

    def onInit(self):
        try:
            self.getControl(401).addLabel(tr(30002))
            self.getControl(402).addLabel(tr(30010) % self.TIMEOUT)
        except AttributeError:
            self.getControl(401).setLabel(tr(30002))
            self.getControl(402).setLabel(tr(30010) % self.TIMEOUT)

    def onAction(self, action):
        code = action.getButtonCode()
        self.key = None if code == 0 else str(code)
        self.close()

    @staticmethod
    def record_key():
        dialog = KeyListener()
        timeout = Timer(KeyListener.TIMEOUT, dialog.close)
        timeout.start()
        dialog.doModal()
        timeout.cancel()
        key = dialog.key
        del dialog
        return key
