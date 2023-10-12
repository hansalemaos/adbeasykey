import functools
import os.path
import platform
import random
import re
import subprocess
import base64
import sys
import tempfile
import time
from copy import deepcopy
from functools import partial
from typing import Literal

from kthread_sleep import sleep

import kthread
import requests
from detachedproc import DetachedPopen
from fullpath83replace import absolut_wpath_to_83
from punktdict import PunktDict, dictconfig

dictconfig.allow_nested_attribute_creation = False
dictconfig.allow_nested_key_creation = False
dictconfig.convert_all_dicts_recursively = True


module_cfg = sys.modules[__name__]

module_cfg.ADB_LIST_ALL_KEYBOARDS = f"ime list -a"
module_cfg.ADB_ENABLE_KEYBOARD = f"ime enable %s"
module_cfg.ADB_DISABLE_KEYBOARD = f"ime disable %s"
module_cfg.ADB_SET_KEYBOARD = f"ime set %s"
module_cfg.ADB_IS_KEYBOARD_SHOWN = f"dumpsys input_method"
module_cfg.ADB_GET_DEFAULT_KEYBOARD = f"settings get secure default_input_method"
module_cfg.ADB_KEYBOARD_NAME = "com.android.adbkeyboard/.AdbIME"
module_cfg.ADB_KEYBOARD_COMMAND = f"am broadcast -a ADB_INPUT_B64 --es msg %s"
module_cfg.ADB_SELECTED_INPUT_METHOD = (
    f"cmd settings put secure selected_input_method_subtype 0"
)
module_cfg.ADB_SHOW_IME_WITH_HARD_KEYBOARD = (
    f"cmd settings put secure show_ime_with_hard_keyboard 1"
)

valid_input_devices = Literal[
    "dpad",
    "keyboard",
    "mouse",
    "touchpad",
    "gamepad",
    "touchnavigation",
    "joystick",
    "touchscreen",
    "stylus",
    "trackball",
    "",
]


class PressKey:
    def __init__(
        self, fu, adb_path, device_serial, event, description, longpress=False
    ):
        self.fu = fu
        self.adb_path = adb_path
        self.device_serial = device_serial
        self.event = event
        self.description = description
        self.longpress = " --longpress" if longpress else ""

    def __repr__(self):
        return self.description

    def __str__(self):
        return self.description

    def __call__(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def dpad(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input dpad keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def keyboard(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input keyboard keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def mouse(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input mouse keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def touchpad(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input touchpad keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def gamepad(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input gamepad keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def touchnavigation(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input touchnavigation keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def joystick(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input joystick keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def touchscreen(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input touchscreen keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def stylus(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input stylus keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )

    def trackball(self, *args, **kwargs):
        return self.fu(
            self.adb_path,
            self.device_serial,
            f"input trackball keyevent {self.event}{self.longpress}",
            *args,
            **kwargs,
        )


module_cfg.key_events = {
    "ACTION_DOWN": {
        "as_int": 0,
        "as_hex": "0x00000000",
        "description": "getAction() value: the key has been pressed down.",
        "added": 1,
        "deprecated": None,
    },
    "ACTION_MULTIPLE": {
        "as_int": 2,
        "as_hex": "0x00000002",
        "description": "This constant was deprecated\n      in API level 29.\n    No longer used by the input system.\n getAction() value: multiple duplicate key events have\n occurred in a row, or a complex string is being delivered.  If the\n key code is not KEYCODE_UNKNOWN then the\n getRepeatCount() method returns the number of times\n the given key code should be executed.\n Otherwise, if the key code is KEYCODE_UNKNOWN, then\n this is a sequence of characters as returned by getCharacters().",
        "added": 1,
        "deprecated": 29,
    },
    "ACTION_UP": {
        "as_int": 1,
        "as_hex": "0x00000001",
        "description": "getAction() value: the key has been released.",
        "added": 1,
        "deprecated": None,
    },
    "FLAG_CANCELED": {
        "as_int": 32,
        "as_hex": "0x00000020",
        "description": "When associated with up key events, this indicates that the key press\n has been canceled.  Typically this is used with virtual touch screen\n keys, where the user can slide from the virtual key area on to the\n display: in that case, the application will receive a canceled up\n event and should not perform the action normally associated with the\n key.  Note that for this to work, the application can not perform an\n action for a key until it receives an up or the long press timeout has\n expired.",
        "added": 5,
        "deprecated": None,
    },
    "FLAG_CANCELED_LONG_PRESS": {
        "as_int": 256,
        "as_hex": "0x00000100",
        "description": "Set when a key event has FLAG_CANCELED set because a long\n press action was executed while it was down.",
        "added": 5,
        "deprecated": None,
    },
    "FLAG_EDITOR_ACTION": {
        "as_int": 16,
        "as_hex": "0x00000010",
        "description": 'This mask is used for compatibility, to identify enter keys that are\n coming from an IME whose enter key has been auto-labelled "next" or\n "done".  This allows TextView to dispatch these as normal enter keys\n for old applications, but still do the appropriate action when\n receiving them.',
        "added": 3,
        "deprecated": None,
    },
    "FLAG_FALLBACK": {
        "as_int": 1024,
        "as_hex": "0x00000400",
        "description": "Set when a key event has been synthesized to implement default behavior\n for an event that the application did not handle.\n Fallback key events are generated by unhandled trackball motions\n (to emulate a directional keypad) and by certain unhandled key presses\n that are declared in the key map (such as special function numeric keypad\n keys when numlock is off).",
        "added": 11,
        "deprecated": None,
    },
    "FLAG_FROM_SYSTEM": {
        "as_int": 8,
        "as_hex": "0x00000008",
        "description": "This mask is set if an event was known to come from a trusted part\n of the system.  That is, the event is known to come from the user,\n and could not have been spoofed by a third party component.",
        "added": 3,
        "deprecated": None,
    },
    "FLAG_KEEP_TOUCH_MODE": {
        "as_int": 4,
        "as_hex": "0x00000004",
        "description": "This mask is set if we don't want the key event to cause us to leave\n touch mode.",
        "added": 3,
        "deprecated": None,
    },
    "FLAG_LONG_PRESS": {
        "as_int": 128,
        "as_hex": "0x00000080",
        "description": "This flag is set for the first key repeat that occurs after the\n long press timeout.",
        "added": 5,
        "deprecated": None,
    },
    "FLAG_SOFT_KEYBOARD": {
        "as_int": 2,
        "as_hex": "0x00000002",
        "description": "This mask is set if the key event was generated by a software keyboard.",
        "added": 3,
        "deprecated": None,
    },
    "FLAG_TRACKING": {
        "as_int": 512,
        "as_hex": "0x00000200",
        "description": "Set for ACTION_UP when this event's key code is still being\n tracked from its initial down.  That is, somebody requested that tracking\n started on the key down and a long press has not caused\n the tracking to be canceled.",
        "added": 5,
        "deprecated": None,
    },
    "FLAG_VIRTUAL_HARD_KEY": {
        "as_int": 64,
        "as_hex": "0x00000040",
        "description": 'This key event was generated by a virtual (on-screen) hard key area.\n Typically this is an area of the touchscreen, outside of the regular\n display, dedicated to "hardware" buttons.',
        "added": 5,
        "deprecated": None,
    },
    "KEYCODE_0": {
        "as_int": 7,
        "as_hex": "0x00000007",
        "description": "Key code constant: '0' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_1": {
        "as_int": 8,
        "as_hex": "0x00000008",
        "description": "Key code constant: '1' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_11": {
        "as_int": 227,
        "as_hex": "0x000000e3",
        "description": "Key code constant: '11' key.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_12": {
        "as_int": 228,
        "as_hex": "0x000000e4",
        "description": "Key code constant: '12' key.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_2": {
        "as_int": 9,
        "as_hex": "0x00000009",
        "description": "Key code constant: '2' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_3": {
        "as_int": 10,
        "as_hex": "0x0000000a",
        "description": "Key code constant: '3' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_3D_MODE": {
        "as_int": 206,
        "as_hex": "0x000000ce",
        "description": "Key code constant: 3D Mode key.\n Toggles the display between 2D and 3D mode.",
        "added": 14,
        "deprecated": None,
    },
    "KEYCODE_4": {
        "as_int": 11,
        "as_hex": "0x0000000b",
        "description": "Key code constant: '4' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_5": {
        "as_int": 12,
        "as_hex": "0x0000000c",
        "description": "Key code constant: '5' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_6": {
        "as_int": 13,
        "as_hex": "0x0000000d",
        "description": "Key code constant: '6' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_7": {
        "as_int": 14,
        "as_hex": "0x0000000e",
        "description": "Key code constant: '7' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_8": {
        "as_int": 15,
        "as_hex": "0x0000000f",
        "description": "Key code constant: '8' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_9": {
        "as_int": 16,
        "as_hex": "0x00000010",
        "description": "Key code constant: '9' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_A": {
        "as_int": 29,
        "as_hex": "0x0000001d",
        "description": "Key code constant: 'A' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_ALL_APPS": {
        "as_int": 284,
        "as_hex": "0x0000011c",
        "description": "Key code constant: Show all apps",
        "added": 28,
        "deprecated": None,
    },
    "KEYCODE_ALT_LEFT": {
        "as_int": 57,
        "as_hex": "0x00000039",
        "description": "Key code constant: Left Alt modifier key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_ALT_RIGHT": {
        "as_int": 58,
        "as_hex": "0x0000003a",
        "description": "Key code constant: Right Alt modifier key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_APOSTROPHE": {
        "as_int": 75,
        "as_hex": "0x0000004b",
        "description": "Key code constant: ''' (apostrophe) key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_APP_SWITCH": {
        "as_int": 187,
        "as_hex": "0x000000bb",
        "description": "Key code constant: App switch key.\n Should bring up the application switcher dialog.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_ASSIST": {
        "as_int": 219,
        "as_hex": "0x000000db",
        "description": "Key code constant: Assist key.\n Launches the global assist activity.  Not delivered to applications.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_AT": {
        "as_int": 77,
        "as_hex": "0x0000004d",
        "description": "Key code constant: '@' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_AVR_INPUT": {
        "as_int": 182,
        "as_hex": "0x000000b6",
        "description": "Key code constant: A/V Receiver input key.\n On TV remotes, switches the input mode on an external A/V Receiver.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_AVR_POWER": {
        "as_int": 181,
        "as_hex": "0x000000b5",
        "description": "Key code constant: A/V Receiver power key.\n On TV remotes, toggles the power on an external A/V Receiver.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_B": {
        "as_int": 30,
        "as_hex": "0x0000001e",
        "description": "Key code constant: 'B' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_BACK": {
        "as_int": 4,
        "as_hex": "0x00000004",
        "description": "Key code constant: Back key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_BACKSLASH": {
        "as_int": 73,
        "as_hex": "0x00000049",
        "description": "Key code constant: '\\' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_BOOKMARK": {
        "as_int": 174,
        "as_hex": "0x000000ae",
        "description": "Key code constant: Bookmark key.\n On some TV remotes, bookmarks content or web pages.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_BREAK": {
        "as_int": 121,
        "as_hex": "0x00000079",
        "description": "Key code constant: Break / Pause key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_BRIGHTNESS_DOWN": {
        "as_int": 220,
        "as_hex": "0x000000dc",
        "description": "Key code constant: Brightness Down key.\n Adjusts the screen brightness down.",
        "added": 18,
        "deprecated": None,
    },
    "KEYCODE_BRIGHTNESS_UP": {
        "as_int": 221,
        "as_hex": "0x000000dd",
        "description": "Key code constant: Brightness Up key.\n Adjusts the screen brightness up.",
        "added": 18,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_1": {
        "as_int": 188,
        "as_hex": "0x000000bc",
        "description": "Key code constant: Generic Game Pad Button #1.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_10": {
        "as_int": 197,
        "as_hex": "0x000000c5",
        "description": "Key code constant: Generic Game Pad Button #10.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_11": {
        "as_int": 198,
        "as_hex": "0x000000c6",
        "description": "Key code constant: Generic Game Pad Button #11.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_12": {
        "as_int": 199,
        "as_hex": "0x000000c7",
        "description": "Key code constant: Generic Game Pad Button #12.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_13": {
        "as_int": 200,
        "as_hex": "0x000000c8",
        "description": "Key code constant: Generic Game Pad Button #13.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_14": {
        "as_int": 201,
        "as_hex": "0x000000c9",
        "description": "Key code constant: Generic Game Pad Button #14.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_15": {
        "as_int": 202,
        "as_hex": "0x000000ca",
        "description": "Key code constant: Generic Game Pad Button #15.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_16": {
        "as_int": 203,
        "as_hex": "0x000000cb",
        "description": "Key code constant: Generic Game Pad Button #16.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_2": {
        "as_int": 189,
        "as_hex": "0x000000bd",
        "description": "Key code constant: Generic Game Pad Button #2.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_3": {
        "as_int": 190,
        "as_hex": "0x000000be",
        "description": "Key code constant: Generic Game Pad Button #3.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_4": {
        "as_int": 191,
        "as_hex": "0x000000bf",
        "description": "Key code constant: Generic Game Pad Button #4.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_5": {
        "as_int": 192,
        "as_hex": "0x000000c0",
        "description": "Key code constant: Generic Game Pad Button #5.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_6": {
        "as_int": 193,
        "as_hex": "0x000000c1",
        "description": "Key code constant: Generic Game Pad Button #6.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_7": {
        "as_int": 194,
        "as_hex": "0x000000c2",
        "description": "Key code constant: Generic Game Pad Button #7.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_8": {
        "as_int": 195,
        "as_hex": "0x000000c3",
        "description": "Key code constant: Generic Game Pad Button #8.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_9": {
        "as_int": 196,
        "as_hex": "0x000000c4",
        "description": "Key code constant: Generic Game Pad Button #9.",
        "added": 12,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_A": {
        "as_int": 96,
        "as_hex": "0x00000060",
        "description": "Key code constant: A Button key.\n On a game controller, the A button should be either the button labeled A\n or the first button on the bottom row of controller buttons.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_B": {
        "as_int": 97,
        "as_hex": "0x00000061",
        "description": "Key code constant: B Button key.\n On a game controller, the B button should be either the button labeled B\n or the second button on the bottom row of controller buttons.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_C": {
        "as_int": 98,
        "as_hex": "0x00000062",
        "description": "Key code constant: C Button key.\n On a game controller, the C button should be either the button labeled C\n or the third button on the bottom row of controller buttons.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_L1": {
        "as_int": 102,
        "as_hex": "0x00000066",
        "description": "Key code constant: L1 Button key.\n On a game controller, the L1 button should be either the button labeled L1 (or L)\n or the top left trigger button.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_L2": {
        "as_int": 104,
        "as_hex": "0x00000068",
        "description": "Key code constant: L2 Button key.\n On a game controller, the L2 button should be either the button labeled L2\n or the bottom left trigger button.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_MODE": {
        "as_int": 110,
        "as_hex": "0x0000006e",
        "description": "Key code constant: Mode Button key.\n On a game controller, the button labeled Mode.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_R1": {
        "as_int": 103,
        "as_hex": "0x00000067",
        "description": "Key code constant: R1 Button key.\n On a game controller, the R1 button should be either the button labeled R1 (or R)\n or the top right trigger button.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_R2": {
        "as_int": 105,
        "as_hex": "0x00000069",
        "description": "Key code constant: R2 Button key.\n On a game controller, the R2 button should be either the button labeled R2\n or the bottom right trigger button.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_SELECT": {
        "as_int": 109,
        "as_hex": "0x0000006d",
        "description": "Key code constant: Select Button key.\n On a game controller, the button labeled Select.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_START": {
        "as_int": 108,
        "as_hex": "0x0000006c",
        "description": "Key code constant: Start Button key.\n On a game controller, the button labeled Start.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_THUMBL": {
        "as_int": 106,
        "as_hex": "0x0000006a",
        "description": "Key code constant: Left Thumb Button key.\n On a game controller, the left thumb button indicates that the left (or only)\n joystick is pressed.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_THUMBR": {
        "as_int": 107,
        "as_hex": "0x0000006b",
        "description": "Key code constant: Right Thumb Button key.\n On a game controller, the right thumb button indicates that the right\n joystick is pressed.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_X": {
        "as_int": 99,
        "as_hex": "0x00000063",
        "description": "Key code constant: X Button key.\n On a game controller, the X button should be either the button labeled X\n or the first button on the upper row of controller buttons.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_Y": {
        "as_int": 100,
        "as_hex": "0x00000064",
        "description": "Key code constant: Y Button key.\n On a game controller, the Y button should be either the button labeled Y\n or the second button on the upper row of controller buttons.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_BUTTON_Z": {
        "as_int": 101,
        "as_hex": "0x00000065",
        "description": "Key code constant: Z Button key.\n On a game controller, the Z button should be either the button labeled Z\n or the third button on the upper row of controller buttons.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_C": {
        "as_int": 31,
        "as_hex": "0x0000001f",
        "description": "Key code constant: 'C' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_CALCULATOR": {
        "as_int": 210,
        "as_hex": "0x000000d2",
        "description": "Key code constant: Calculator special function key.\n Used to launch a calculator application.",
        "added": 15,
        "deprecated": None,
    },
    "KEYCODE_CALENDAR": {
        "as_int": 208,
        "as_hex": "0x000000d0",
        "description": "Key code constant: Calendar special function key.\n Used to launch a calendar application.",
        "added": 15,
        "deprecated": None,
    },
    "KEYCODE_CALL": {
        "as_int": 5,
        "as_hex": "0x00000005",
        "description": "Key code constant: Call key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_CAMERA": {
        "as_int": 27,
        "as_hex": "0x0000001b",
        "description": "Key code constant: Camera key.\n Used to launch a camera application or take pictures.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_CAPS_LOCK": {
        "as_int": 115,
        "as_hex": "0x00000073",
        "description": "Key code constant: Caps Lock key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_CAPTIONS": {
        "as_int": 175,
        "as_hex": "0x000000af",
        "description": "Key code constant: Toggle captions key.\n Switches the mode for closed-captioning text, for example during television shows.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_CHANNEL_DOWN": {
        "as_int": 167,
        "as_hex": "0x000000a7",
        "description": "Key code constant: Channel down key.\n On TV remotes, decrements the television channel.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_CHANNEL_UP": {
        "as_int": 166,
        "as_hex": "0x000000a6",
        "description": "Key code constant: Channel up key.\n On TV remotes, increments the television channel.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_CLEAR": {
        "as_int": 28,
        "as_hex": "0x0000001c",
        "description": "Key code constant: Clear key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_COMMA": {
        "as_int": 55,
        "as_hex": "0x00000037",
        "description": "Key code constant: ',' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_CONTACTS": {
        "as_int": 207,
        "as_hex": "0x000000cf",
        "description": "Key code constant: Contacts special function key.\n Used to launch an address book application.",
        "added": 15,
        "deprecated": None,
    },
    "KEYCODE_COPY": {
        "as_int": 278,
        "as_hex": "0x00000116",
        "description": "Key code constant: Copy key.",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_CTRL_LEFT": {
        "as_int": 113,
        "as_hex": "0x00000071",
        "description": "Key code constant: Left Control modifier key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_CTRL_RIGHT": {
        "as_int": 114,
        "as_hex": "0x00000072",
        "description": "Key code constant: Right Control modifier key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_CUT": {
        "as_int": 277,
        "as_hex": "0x00000115",
        "description": "Key code constant: Cut key.",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_D": {
        "as_int": 32,
        "as_hex": "0x00000020",
        "description": "Key code constant: 'D' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DEL": {
        "as_int": 67,
        "as_hex": "0x00000043",
        "description": "Key code constant: Backspace key.\n Deletes characters before the insertion point, unlike KEYCODE_FORWARD_DEL.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DEMO_APP_1": {
        "as_int": 301,
        "as_hex": "0x0000012d",
        "description": "Key code constant: Demo Application key #1.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_DEMO_APP_2": {
        "as_int": 302,
        "as_hex": "0x0000012e",
        "description": "Key code constant: Demo Application key #2.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_DEMO_APP_3": {
        "as_int": 303,
        "as_hex": "0x0000012f",
        "description": "Key code constant: Demo Application key #3.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_DEMO_APP_4": {
        "as_int": 304,
        "as_hex": "0x00000130",
        "description": "Key code constant: Demo Application key #4.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_DPAD_CENTER": {
        "as_int": 23,
        "as_hex": "0x00000017",
        "description": "Key code constant: Directional Pad Center key.\n May also be synthesized from trackball motions.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DPAD_DOWN": {
        "as_int": 20,
        "as_hex": "0x00000014",
        "description": "Key code constant: Directional Pad Down key.\n May also be synthesized from trackball motions.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DPAD_DOWN_LEFT": {
        "as_int": 269,
        "as_hex": "0x0000010d",
        "description": "Key code constant: Directional Pad Down-Left",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_DPAD_DOWN_RIGHT": {
        "as_int": 271,
        "as_hex": "0x0000010f",
        "description": "Key code constant: Directional Pad Down-Right",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_DPAD_LEFT": {
        "as_int": 21,
        "as_hex": "0x00000015",
        "description": "Key code constant: Directional Pad Left key.\n May also be synthesized from trackball motions.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DPAD_RIGHT": {
        "as_int": 22,
        "as_hex": "0x00000016",
        "description": "Key code constant: Directional Pad Right key.\n May also be synthesized from trackball motions.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DPAD_UP": {
        "as_int": 19,
        "as_hex": "0x00000013",
        "description": "Key code constant: Directional Pad Up key.\n May also be synthesized from trackball motions.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_DPAD_UP_LEFT": {
        "as_int": 268,
        "as_hex": "0x0000010c",
        "description": "Key code constant: Directional Pad Up-Left",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_DPAD_UP_RIGHT": {
        "as_int": 270,
        "as_hex": "0x0000010e",
        "description": "Key code constant: Directional Pad Up-Right",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_DVR": {
        "as_int": 173,
        "as_hex": "0x000000ad",
        "description": "Key code constant: DVR key.\n On some TV remotes, switches to a DVR mode for recorded shows.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_E": {
        "as_int": 33,
        "as_hex": "0x00000021",
        "description": "Key code constant: 'E' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_EISU": {
        "as_int": 212,
        "as_hex": "0x000000d4",
        "description": "Key code constant: Japanese alphanumeric key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_ENDCALL": {
        "as_int": 6,
        "as_hex": "0x00000006",
        "description": "Key code constant: End Call key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_ENTER": {
        "as_int": 66,
        "as_hex": "0x00000042",
        "description": "Key code constant: Enter key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_ENVELOPE": {
        "as_int": 65,
        "as_hex": "0x00000041",
        "description": "Key code constant: Envelope special function key.\n Used to launch a mail application.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_EQUALS": {
        "as_int": 70,
        "as_hex": "0x00000046",
        "description": "Key code constant: '=' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_ESCAPE": {
        "as_int": 111,
        "as_hex": "0x0000006f",
        "description": "Key code constant: Escape key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_EXPLORER": {
        "as_int": 64,
        "as_hex": "0x00000040",
        "description": "Key code constant: Explorer special function key.\n Used to launch a browser application.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_F": {
        "as_int": 34,
        "as_hex": "0x00000022",
        "description": "Key code constant: 'F' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_F1": {
        "as_int": 131,
        "as_hex": "0x00000083",
        "description": "Key code constant: F1 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F10": {
        "as_int": 140,
        "as_hex": "0x0000008c",
        "description": "Key code constant: F10 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F11": {
        "as_int": 141,
        "as_hex": "0x0000008d",
        "description": "Key code constant: F11 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F12": {
        "as_int": 142,
        "as_hex": "0x0000008e",
        "description": "Key code constant: F12 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F2": {
        "as_int": 132,
        "as_hex": "0x00000084",
        "description": "Key code constant: F2 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F3": {
        "as_int": 133,
        "as_hex": "0x00000085",
        "description": "Key code constant: F3 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F4": {
        "as_int": 134,
        "as_hex": "0x00000086",
        "description": "Key code constant: F4 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F5": {
        "as_int": 135,
        "as_hex": "0x00000087",
        "description": "Key code constant: F5 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F6": {
        "as_int": 136,
        "as_hex": "0x00000088",
        "description": "Key code constant: F6 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F7": {
        "as_int": 137,
        "as_hex": "0x00000089",
        "description": "Key code constant: F7 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F8": {
        "as_int": 138,
        "as_hex": "0x0000008a",
        "description": "Key code constant: F8 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_F9": {
        "as_int": 139,
        "as_hex": "0x0000008b",
        "description": "Key code constant: F9 key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_FEATURED_APP_1": {
        "as_int": 297,
        "as_hex": "0x00000129",
        "description": "Key code constant: Featured Application key #1.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_FEATURED_APP_2": {
        "as_int": 298,
        "as_hex": "0x0000012a",
        "description": "Key code constant: Featured Application key #2.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_FEATURED_APP_3": {
        "as_int": 299,
        "as_hex": "0x0000012b",
        "description": "Key code constant: Featured Application key #3.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_FEATURED_APP_4": {
        "as_int": 300,
        "as_hex": "0x0000012c",
        "description": "Key code constant: Featured Application key #4.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_FOCUS": {
        "as_int": 80,
        "as_hex": "0x00000050",
        "description": "Key code constant: Camera Focus key.\n Used to focus the camera.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_FORWARD": {
        "as_int": 125,
        "as_hex": "0x0000007d",
        "description": "Key code constant: Forward key.\n Navigates forward in the history stack.  Complement of KEYCODE_BACK.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_FORWARD_DEL": {
        "as_int": 112,
        "as_hex": "0x00000070",
        "description": "Key code constant: Forward Delete key.\n Deletes characters ahead of the insertion point, unlike KEYCODE_DEL.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_FUNCTION": {
        "as_int": 119,
        "as_hex": "0x00000077",
        "description": "Key code constant: Function modifier key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_G": {
        "as_int": 35,
        "as_hex": "0x00000023",
        "description": "Key code constant: 'G' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_GRAVE": {
        "as_int": 68,
        "as_hex": "0x00000044",
        "description": "Key code constant: '`' (backtick) key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_GUIDE": {
        "as_int": 172,
        "as_hex": "0x000000ac",
        "description": "Key code constant: Guide key.\n On TV remotes, shows a programming guide.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_H": {
        "as_int": 36,
        "as_hex": "0x00000024",
        "description": "Key code constant: 'H' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_HEADSETHOOK": {
        "as_int": 79,
        "as_hex": "0x0000004f",
        "description": "Key code constant: Headset Hook key.\n Used to hang up calls and stop media.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_HELP": {
        "as_int": 259,
        "as_hex": "0x00000103",
        "description": "Key code constant: Help key.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_HENKAN": {
        "as_int": 214,
        "as_hex": "0x000000d6",
        "description": "Key code constant: Japanese conversion key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_HOME": {
        "as_int": 3,
        "as_hex": "0x00000003",
        "description": "Key code constant: Home key.\n This key is handled by the framework and is never delivered to applications.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_I": {
        "as_int": 37,
        "as_hex": "0x00000025",
        "description": "Key code constant: 'I' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_INFO": {
        "as_int": 165,
        "as_hex": "0x000000a5",
        "description": "Key code constant: Info key.\n Common on TV remotes to show additional information related to what is\n currently being viewed.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_INSERT": {
        "as_int": 124,
        "as_hex": "0x0000007c",
        "description": "Key code constant: Insert key.\n Toggles insert / overwrite edit mode.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_J": {
        "as_int": 38,
        "as_hex": "0x00000026",
        "description": "Key code constant: 'J' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_K": {
        "as_int": 39,
        "as_hex": "0x00000027",
        "description": "Key code constant: 'K' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_KANA": {
        "as_int": 218,
        "as_hex": "0x000000da",
        "description": "Key code constant: Japanese kana key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_KATAKANA_HIRAGANA": {
        "as_int": 215,
        "as_hex": "0x000000d7",
        "description": "Key code constant: Japanese katakana / hiragana key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_KEYBOARD_BACKLIGHT_DOWN": {
        "as_int": 305,
        "as_hex": "0x00000131",
        "description": "Key code constant: Keyboard backlight down",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_KEYBOARD_BACKLIGHT_TOGGLE": {
        "as_int": 307,
        "as_hex": "0x00000133",
        "description": "Key code constant: Keyboard backlight toggle",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_KEYBOARD_BACKLIGHT_UP": {
        "as_int": 306,
        "as_hex": "0x00000132",
        "description": "Key code constant: Keyboard backlight up",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_L": {
        "as_int": 40,
        "as_hex": "0x00000028",
        "description": "Key code constant: 'L' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_LANGUAGE_SWITCH": {
        "as_int": 204,
        "as_hex": "0x000000cc",
        "description": "Key code constant: Language Switch key.\n Toggles the current input language such as switching between English and Japanese on\n a QWERTY keyboard.  On some devices, the same function may be performed by\n pressing Shift+Spacebar.",
        "added": 14,
        "deprecated": None,
    },
    "KEYCODE_LAST_CHANNEL": {
        "as_int": 229,
        "as_hex": "0x000000e5",
        "description": "Key code constant: Last Channel key.\n Goes to the last viewed channel.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_LEFT_BRACKET": {
        "as_int": 71,
        "as_hex": "0x00000047",
        "description": "Key code constant: '[' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_M": {
        "as_int": 41,
        "as_hex": "0x00000029",
        "description": "Key code constant: 'M' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_MACRO_1": {
        "as_int": 313,
        "as_hex": "0x00000139",
        "description": "Key code constant: A button whose usage can be customized by the user through\n                    the system.\n User customizable key #1.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_MACRO_2": {
        "as_int": 314,
        "as_hex": "0x0000013a",
        "description": "Key code constant: A button whose usage can be customized by the user through\n                    the system.\n User customizable key #2.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_MACRO_3": {
        "as_int": 315,
        "as_hex": "0x0000013b",
        "description": "Key code constant: A button whose usage can be customized by the user through\n                    the system.\n User customizable key #3.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_MACRO_4": {
        "as_int": 316,
        "as_hex": "0x0000013c",
        "description": "Key code constant: A button whose usage can be customized by the user through\n                    the system.\n User customizable key #4.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_MANNER_MODE": {
        "as_int": 205,
        "as_hex": "0x000000cd",
        "description": "Key code constant: Manner Mode key.\n Toggles silent or vibrate mode on and off to make the device behave more politely\n in certain settings such as on a crowded train.  On some devices, the key may only\n operate when long-pressed.",
        "added": 14,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_AUDIO_TRACK": {
        "as_int": 222,
        "as_hex": "0x000000de",
        "description": "Key code constant: Audio Track key.\n Switches the audio tracks.",
        "added": 19,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_CLOSE": {
        "as_int": 128,
        "as_hex": "0x00000080",
        "description": "Key code constant: Close media key.\n May be used to close a CD tray, for example.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_EJECT": {
        "as_int": 129,
        "as_hex": "0x00000081",
        "description": "Key code constant: Eject media key.\n May be used to eject a CD tray, for example.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_FAST_FORWARD": {
        "as_int": 90,
        "as_hex": "0x0000005a",
        "description": "Key code constant: Fast Forward media key.",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_NEXT": {
        "as_int": 87,
        "as_hex": "0x00000057",
        "description": "Key code constant: Play Next media key.",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_PAUSE": {
        "as_int": 127,
        "as_hex": "0x0000007f",
        "description": "Key code constant: Pause media key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_PLAY": {
        "as_int": 126,
        "as_hex": "0x0000007e",
        "description": "Key code constant: Play media key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_PLAY_PAUSE": {
        "as_int": 85,
        "as_hex": "0x00000055",
        "description": "Key code constant: Play/Pause media key.",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_PREVIOUS": {
        "as_int": 88,
        "as_hex": "0x00000058",
        "description": "Key code constant: Play Previous media key.",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_RECORD": {
        "as_int": 130,
        "as_hex": "0x00000082",
        "description": "Key code constant: Record media key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_REWIND": {
        "as_int": 89,
        "as_hex": "0x00000059",
        "description": "Key code constant: Rewind media key.",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_SKIP_BACKWARD": {
        "as_int": 273,
        "as_hex": "0x00000111",
        "description": "Key code constant: Skip backward media key.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_SKIP_FORWARD": {
        "as_int": 272,
        "as_hex": "0x00000110",
        "description": "Key code constant: Skip forward media key.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_STEP_BACKWARD": {
        "as_int": 275,
        "as_hex": "0x00000113",
        "description": "Key code constant: Step backward media key.\n Steps media backward, one frame at a time.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_STEP_FORWARD": {
        "as_int": 274,
        "as_hex": "0x00000112",
        "description": "Key code constant: Step forward media key.\n Steps media forward, one frame at a time.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_STOP": {
        "as_int": 86,
        "as_hex": "0x00000056",
        "description": "Key code constant: Stop media key.",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_MEDIA_TOP_MENU": {
        "as_int": 226,
        "as_hex": "0x000000e2",
        "description": "Key code constant: Media Top Menu key.\n Goes to the top of media menu.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_MENU": {
        "as_int": 82,
        "as_hex": "0x00000052",
        "description": "Key code constant: Menu key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_META_LEFT": {
        "as_int": 117,
        "as_hex": "0x00000075",
        "description": "Key code constant: Left Meta modifier key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_META_RIGHT": {
        "as_int": 118,
        "as_hex": "0x00000076",
        "description": "Key code constant: Right Meta modifier key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MINUS": {
        "as_int": 69,
        "as_hex": "0x00000045",
        "description": "Key code constant: '-'.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_MOVE_END": {
        "as_int": 123,
        "as_hex": "0x0000007b",
        "description": "Key code constant: End Movement key.\n Used for scrolling or moving the cursor around to the end of a line\n or to the bottom of a list.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MOVE_HOME": {
        "as_int": 122,
        "as_hex": "0x0000007a",
        "description": "Key code constant: Home Movement key.\n Used for scrolling or moving the cursor around to the start of a line\n or to the top of a list.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_MUHENKAN": {
        "as_int": 213,
        "as_hex": "0x000000d5",
        "description": "Key code constant: Japanese non-conversion key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_MUSIC": {
        "as_int": 209,
        "as_hex": "0x000000d1",
        "description": "Key code constant: Music special function key.\n Used to launch a music player application.",
        "added": 15,
        "deprecated": None,
    },
    "KEYCODE_MUTE": {
        "as_int": 91,
        "as_hex": "0x0000005b",
        "description": "Key code constant: Mute key.\n Mute key for the microphone (unlike KEYCODE_VOLUME_MUTE, which is the speaker mute\n key).",
        "added": 3,
        "deprecated": None,
    },
    "KEYCODE_N": {
        "as_int": 42,
        "as_hex": "0x0000002a",
        "description": "Key code constant: 'N' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_NAVIGATE_IN": {
        "as_int": 262,
        "as_hex": "0x00000106",
        "description": "Key code constant: Navigate in key.\n Activates the item that currently has focus or expands to the next level of a navigation\n hierarchy.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_NAVIGATE_NEXT": {
        "as_int": 261,
        "as_hex": "0x00000105",
        "description": "Key code constant: Navigate to next key.\n Advances to the next item in an ordered collection of items.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_NAVIGATE_OUT": {
        "as_int": 263,
        "as_hex": "0x00000107",
        "description": "Key code constant: Navigate out key.\n Backs out one level of a navigation hierarchy or collapses the item that currently has\n focus.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_NAVIGATE_PREVIOUS": {
        "as_int": 260,
        "as_hex": "0x00000104",
        "description": "Key code constant: Navigate to previous key.\n Goes backward by one item in an ordered collection of items.",
        "added": 23,
        "deprecated": None,
    },
    "KEYCODE_NOTIFICATION": {
        "as_int": 83,
        "as_hex": "0x00000053",
        "description": "Key code constant: Notification key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_NUM": {
        "as_int": 78,
        "as_hex": "0x0000004e",
        "description": "Key code constant: Number modifier key.\n Used to enter numeric symbols.\n This key is not Num Lock; it is more like KEYCODE_ALT_LEFT and is\n interpreted as an ALT key by MetaKeyKeyListener.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_0": {
        "as_int": 144,
        "as_hex": "0x00000090",
        "description": "Key code constant: Numeric keypad '0' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_1": {
        "as_int": 145,
        "as_hex": "0x00000091",
        "description": "Key code constant: Numeric keypad '1' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_2": {
        "as_int": 146,
        "as_hex": "0x00000092",
        "description": "Key code constant: Numeric keypad '2' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_3": {
        "as_int": 147,
        "as_hex": "0x00000093",
        "description": "Key code constant: Numeric keypad '3' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_4": {
        "as_int": 148,
        "as_hex": "0x00000094",
        "description": "Key code constant: Numeric keypad '4' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_5": {
        "as_int": 149,
        "as_hex": "0x00000095",
        "description": "Key code constant: Numeric keypad '5' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_6": {
        "as_int": 150,
        "as_hex": "0x00000096",
        "description": "Key code constant: Numeric keypad '6' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_7": {
        "as_int": 151,
        "as_hex": "0x00000097",
        "description": "Key code constant: Numeric keypad '7' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_8": {
        "as_int": 152,
        "as_hex": "0x00000098",
        "description": "Key code constant: Numeric keypad '8' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_9": {
        "as_int": 153,
        "as_hex": "0x00000099",
        "description": "Key code constant: Numeric keypad '9' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_ADD": {
        "as_int": 157,
        "as_hex": "0x0000009d",
        "description": "Key code constant: Numeric keypad '+' key (for addition).",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_COMMA": {
        "as_int": 159,
        "as_hex": "0x0000009f",
        "description": "Key code constant: Numeric keypad ',' key (for decimals or digit grouping).",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_DIVIDE": {
        "as_int": 154,
        "as_hex": "0x0000009a",
        "description": "Key code constant: Numeric keypad '/' key (for division).",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_DOT": {
        "as_int": 158,
        "as_hex": "0x0000009e",
        "description": "Key code constant: Numeric keypad '.' key (for decimals or digit grouping).",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_ENTER": {
        "as_int": 160,
        "as_hex": "0x000000a0",
        "description": "Key code constant: Numeric keypad Enter key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_EQUALS": {
        "as_int": 161,
        "as_hex": "0x000000a1",
        "description": "Key code constant: Numeric keypad '=' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_LEFT_PAREN": {
        "as_int": 162,
        "as_hex": "0x000000a2",
        "description": "Key code constant: Numeric keypad '(' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_MULTIPLY": {
        "as_int": 155,
        "as_hex": "0x0000009b",
        "description": "Key code constant: Numeric keypad '*' key (for multiplication).",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_RIGHT_PAREN": {
        "as_int": 163,
        "as_hex": "0x000000a3",
        "description": "Key code constant: Numeric keypad ')' key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUMPAD_SUBTRACT": {
        "as_int": 156,
        "as_hex": "0x0000009c",
        "description": "Key code constant: Numeric keypad '-' key (for subtraction).",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_NUM_LOCK": {
        "as_int": 143,
        "as_hex": "0x0000008f",
        "description": "Key code constant: Num Lock key.\n This is the Num Lock key; it is different from KEYCODE_NUM.\n This key alters the behavior of other keys on the numeric keypad.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_O": {
        "as_int": 43,
        "as_hex": "0x0000002b",
        "description": "Key code constant: 'O' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_P": {
        "as_int": 44,
        "as_hex": "0x0000002c",
        "description": "Key code constant: 'P' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_PAGE_DOWN": {
        "as_int": 93,
        "as_hex": "0x0000005d",
        "description": "Key code constant: Page Down key.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_PAGE_UP": {
        "as_int": 92,
        "as_hex": "0x0000005c",
        "description": "Key code constant: Page Up key.",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_PAIRING": {
        "as_int": 225,
        "as_hex": "0x000000e1",
        "description": "Key code constant: Pairing key.\n Initiates peripheral pairing mode. Useful for pairing remote control\n devices or game controllers, especially if no other input mode is\n available.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_PASTE": {
        "as_int": 279,
        "as_hex": "0x00000117",
        "description": "Key code constant: Paste key.",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_PERIOD": {
        "as_int": 56,
        "as_hex": "0x00000038",
        "description": "Key code constant: '.' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_PICTSYMBOLS": {
        "as_int": 94,
        "as_hex": "0x0000005e",
        "description": "Key code constant: Picture Symbols modifier key.\n Used to switch symbol sets (Emoji, Kao-moji).",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_PLUS": {
        "as_int": 81,
        "as_hex": "0x00000051",
        "description": "Key code constant: '+' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_POUND": {
        "as_int": 18,
        "as_hex": "0x00000012",
        "description": "Key code constant: '#' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_POWER": {
        "as_int": 26,
        "as_hex": "0x0000001a",
        "description": "Key code constant: Power key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_PROFILE_SWITCH": {
        "as_int": 288,
        "as_hex": "0x00000120",
        "description": "Key code constant: Used to switch current Account that is\n consuming content. May be consumed by system to set account globally.",
        "added": 29,
        "deprecated": None,
    },
    "KEYCODE_PROG_BLUE": {
        "as_int": 186,
        "as_hex": "0x000000ba",
        "description": 'Key code constant: Blue "programmable" key.\n On TV remotes, acts as a contextual/programmable key.',
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_PROG_GREEN": {
        "as_int": 184,
        "as_hex": "0x000000b8",
        "description": 'Key code constant: Green "programmable" key.\n On TV remotes, actsas a contextual/programmable key.',
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_PROG_RED": {
        "as_int": 183,
        "as_hex": "0x000000b7",
        "description": 'Key code constant: Red "programmable" key.\n On TV remotes, acts as a contextual/programmable key.',
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_PROG_YELLOW": {
        "as_int": 185,
        "as_hex": "0x000000b9",
        "description": 'Key code constant: Yellow "programmable" key.\n On TV remotes, acts as a contextual/programmable key.',
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_Q": {
        "as_int": 45,
        "as_hex": "0x0000002d",
        "description": "Key code constant: 'Q' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_R": {
        "as_int": 46,
        "as_hex": "0x0000002e",
        "description": "Key code constant: 'R' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_RECENT_APPS": {
        "as_int": 312,
        "as_hex": "0x00000138",
        "description": "Key code constant: To open recent apps view (a.k.a. Overview).\n This key is handled by the framework and is never delivered to applications.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_REFRESH": {
        "as_int": 285,
        "as_hex": "0x0000011d",
        "description": "Key code constant: Refresh key.",
        "added": 28,
        "deprecated": None,
    },
    "KEYCODE_RIGHT_BRACKET": {
        "as_int": 72,
        "as_hex": "0x00000048",
        "description": "Key code constant: ']' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_RO": {
        "as_int": 217,
        "as_hex": "0x000000d9",
        "description": "Key code constant: Japanese Ro key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_S": {
        "as_int": 47,
        "as_hex": "0x0000002f",
        "description": "Key code constant: 'S' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SCROLL_LOCK": {
        "as_int": 116,
        "as_hex": "0x00000074",
        "description": "Key code constant: Scroll Lock key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_SEARCH": {
        "as_int": 84,
        "as_hex": "0x00000054",
        "description": "Key code constant: Search key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SEMICOLON": {
        "as_int": 74,
        "as_hex": "0x0000004a",
        "description": "Key code constant: ';' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SETTINGS": {
        "as_int": 176,
        "as_hex": "0x000000b0",
        "description": "Key code constant: Settings key.\n Starts the system settings activity.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_SHIFT_LEFT": {
        "as_int": 59,
        "as_hex": "0x0000003b",
        "description": "Key code constant: Left Shift modifier key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SHIFT_RIGHT": {
        "as_int": 60,
        "as_hex": "0x0000003c",
        "description": "Key code constant: Right Shift modifier key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SLASH": {
        "as_int": 76,
        "as_hex": "0x0000004c",
        "description": "Key code constant: '/' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SLEEP": {
        "as_int": 223,
        "as_hex": "0x000000df",
        "description": "Key code constant: Sleep key.\n Puts the device to sleep.  Behaves somewhat like KEYCODE_POWER but it\n has no effect if the device is already asleep.",
        "added": 20,
        "deprecated": None,
    },
    "KEYCODE_SOFT_LEFT": {
        "as_int": 1,
        "as_hex": "0x00000001",
        "description": "Key code constant: Soft Left key.\n Usually situated below the display on phones and used as a multi-function\n feature key for selecting a software defined function shown on the bottom left\n of the display.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SOFT_RIGHT": {
        "as_int": 2,
        "as_hex": "0x00000002",
        "description": "Key code constant: Soft Right key.\n Usually situated below the display on phones and used as a multi-function\n feature key for selecting a software defined function shown on the bottom right\n of the display.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SOFT_SLEEP": {
        "as_int": 276,
        "as_hex": "0x00000114",
        "description": "Key code constant: put device to sleep unless a wakelock is held.",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_SPACE": {
        "as_int": 62,
        "as_hex": "0x0000003e",
        "description": "Key code constant: Space key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_STAR": {
        "as_int": 17,
        "as_hex": "0x00000011",
        "description": "Key code constant: '*' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_STB_INPUT": {
        "as_int": 180,
        "as_hex": "0x000000b4",
        "description": "Key code constant: Set-top-box input key.\n On TV remotes, switches the input mode on an external Set-top-box.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_STB_POWER": {
        "as_int": 179,
        "as_hex": "0x000000b3",
        "description": "Key code constant: Set-top-box power key.\n On TV remotes, toggles the power on an external Set-top-box.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_STEM_1": {
        "as_int": 265,
        "as_hex": "0x00000109",
        "description": "Key code constant: Generic stem key 1 for Wear",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_STEM_2": {
        "as_int": 266,
        "as_hex": "0x0000010a",
        "description": "Key code constant: Generic stem key 2 for Wear",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_STEM_3": {
        "as_int": 267,
        "as_hex": "0x0000010b",
        "description": "Key code constant: Generic stem key 3 for Wear",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_STEM_PRIMARY": {
        "as_int": 264,
        "as_hex": "0x00000108",
        "description": "Key code constant: Primary stem key for Wear\n Main power/reset button on watch.",
        "added": 24,
        "deprecated": None,
    },
    "KEYCODE_STYLUS_BUTTON_PRIMARY": {
        "as_int": 308,
        "as_hex": "0x00000134",
        "description": "Key code constant: The primary button on the barrel of a stylus.\n This is usually the button closest to the tip of the stylus.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_STYLUS_BUTTON_SECONDARY": {
        "as_int": 309,
        "as_hex": "0x00000135",
        "description": "Key code constant: The secondary button on the barrel of a stylus.\n This is usually the second button from the tip of the stylus.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_STYLUS_BUTTON_TAIL": {
        "as_int": 311,
        "as_hex": "0x00000137",
        "description": "Key code constant: A button on the tail end of a stylus.\n The use of this button does not usually correspond to the function of an eraser.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_STYLUS_BUTTON_TERTIARY": {
        "as_int": 310,
        "as_hex": "0x00000136",
        "description": "Key code constant: The tertiary button on the barrel of a stylus.\n This is usually the third button from the tip of the stylus.",
        "added": 34,
        "deprecated": None,
    },
    "KEYCODE_SWITCH_CHARSET": {
        "as_int": 95,
        "as_hex": "0x0000005f",
        "description": "Key code constant: Switch Charset modifier key.\n Used to switch character sets (Kanji, Katakana).",
        "added": 9,
        "deprecated": None,
    },
    "KEYCODE_SYM": {
        "as_int": 63,
        "as_hex": "0x0000003f",
        "description": "Key code constant: Symbol modifier key.\n Used to enter alternate symbols.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_SYSRQ": {
        "as_int": 120,
        "as_hex": "0x00000078",
        "description": "Key code constant: System Request / Print Screen key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_SYSTEM_NAVIGATION_DOWN": {
        "as_int": 281,
        "as_hex": "0x00000119",
        "description": "Key code constant: Consumed by the system for navigation down",
        "added": 25,
        "deprecated": None,
    },
    "KEYCODE_SYSTEM_NAVIGATION_LEFT": {
        "as_int": 282,
        "as_hex": "0x0000011a",
        "description": "Key code constant: Consumed by the system for navigation left",
        "added": 25,
        "deprecated": None,
    },
    "KEYCODE_SYSTEM_NAVIGATION_RIGHT": {
        "as_int": 283,
        "as_hex": "0x0000011b",
        "description": "Key code constant: Consumed by the system for navigation right",
        "added": 25,
        "deprecated": None,
    },
    "KEYCODE_SYSTEM_NAVIGATION_UP": {
        "as_int": 280,
        "as_hex": "0x00000118",
        "description": "Key code constant: Consumed by the system for navigation up",
        "added": 25,
        "deprecated": None,
    },
    "KEYCODE_T": {
        "as_int": 48,
        "as_hex": "0x00000030",
        "description": "Key code constant: 'T' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_TAB": {
        "as_int": 61,
        "as_hex": "0x0000003d",
        "description": "Key code constant: Tab key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_THUMBS_DOWN": {
        "as_int": 287,
        "as_hex": "0x0000011f",
        "description": "Key code constant: Thumbs down key. Apps can use this to let user downvote content.",
        "added": 29,
        "deprecated": None,
    },
    "KEYCODE_THUMBS_UP": {
        "as_int": 286,
        "as_hex": "0x0000011e",
        "description": "Key code constant: Thumbs up key. Apps can use this to let user upvote content.",
        "added": 29,
        "deprecated": None,
    },
    "KEYCODE_TV": {
        "as_int": 170,
        "as_hex": "0x000000aa",
        "description": "Key code constant: TV key.\n On TV remotes, switches to viewing live TV.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_TV_ANTENNA_CABLE": {
        "as_int": 242,
        "as_hex": "0x000000f2",
        "description": "Key code constant: Antenna/Cable key.\n Toggles broadcast input source between antenna and cable.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_AUDIO_DESCRIPTION": {
        "as_int": 252,
        "as_hex": "0x000000fc",
        "description": "Key code constant: Audio description key.\n Toggles audio description off / on.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_AUDIO_DESCRIPTION_MIX_DOWN": {
        "as_int": 254,
        "as_hex": "0x000000fe",
        "description": "Key code constant: Audio description mixing volume down key.\n Lessen audio description volume as compared with normal audio volume.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_AUDIO_DESCRIPTION_MIX_UP": {
        "as_int": 253,
        "as_hex": "0x000000fd",
        "description": "Key code constant: Audio description mixing volume up key.\n Louden audio description volume as compared with normal audio volume.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_CONTENTS_MENU": {
        "as_int": 256,
        "as_hex": "0x00000100",
        "description": "Key code constant: Contents menu key.\n Goes to the title list. Corresponds to Contents Menu (0x0B) of CEC User Control\n Code",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_DATA_SERVICE": {
        "as_int": 230,
        "as_hex": "0x000000e6",
        "description": "Key code constant: TV data service key.\n Displays data services like weather, sports.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT": {
        "as_int": 178,
        "as_hex": "0x000000b2",
        "description": "Key code constant: TV input key.\n On TV remotes, switches the input on a television screen.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_COMPONENT_1": {
        "as_int": 249,
        "as_hex": "0x000000f9",
        "description": "Key code constant: Component #1 key.\n Switches to component video input #1.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_COMPONENT_2": {
        "as_int": 250,
        "as_hex": "0x000000fa",
        "description": "Key code constant: Component #2 key.\n Switches to component video input #2.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_COMPOSITE_1": {
        "as_int": 247,
        "as_hex": "0x000000f7",
        "description": "Key code constant: Composite #1 key.\n Switches to composite video input #1.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_COMPOSITE_2": {
        "as_int": 248,
        "as_hex": "0x000000f8",
        "description": "Key code constant: Composite #2 key.\n Switches to composite video input #2.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_HDMI_1": {
        "as_int": 243,
        "as_hex": "0x000000f3",
        "description": "Key code constant: HDMI #1 key.\n Switches to HDMI input #1.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_HDMI_2": {
        "as_int": 244,
        "as_hex": "0x000000f4",
        "description": "Key code constant: HDMI #2 key.\n Switches to HDMI input #2.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_HDMI_3": {
        "as_int": 245,
        "as_hex": "0x000000f5",
        "description": "Key code constant: HDMI #3 key.\n Switches to HDMI input #3.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_HDMI_4": {
        "as_int": 246,
        "as_hex": "0x000000f6",
        "description": "Key code constant: HDMI #4 key.\n Switches to HDMI input #4.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_INPUT_VGA_1": {
        "as_int": 251,
        "as_hex": "0x000000fb",
        "description": "Key code constant: VGA #1 key.\n Switches to VGA (analog RGB) input #1.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_MEDIA_CONTEXT_MENU": {
        "as_int": 257,
        "as_hex": "0x00000101",
        "description": "Key code constant: Media context menu key.\n Goes to the context menu of media contents. Corresponds to Media Context-sensitive\n Menu (0x11) of CEC User Control Code.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_NETWORK": {
        "as_int": 241,
        "as_hex": "0x000000f1",
        "description": "Key code constant: Toggle Network key.\n Toggles selecting broacast services.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_NUMBER_ENTRY": {
        "as_int": 234,
        "as_hex": "0x000000ea",
        "description": "Key code constant: Number entry key.\n Initiates to enter multi-digit channel nubmber when each digit key is assigned\n for selecting separate channel. Corresponds to Number Entry Mode (0x1D) of CEC\n User Control Code.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_POWER": {
        "as_int": 177,
        "as_hex": "0x000000b1",
        "description": "Key code constant: TV power key.\n On HDMI TV panel devices and Android TV devices that don't support HDMI, toggles the power\n state of the device.\n On HDMI source devices, toggles the power state of the HDMI-connected TV via HDMI-CEC and\n makes the source device follow this power state.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_TV_RADIO_SERVICE": {
        "as_int": 232,
        "as_hex": "0x000000e8",
        "description": "Key code constant: Radio key.\n Toggles TV service / Radio service.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_SATELLITE": {
        "as_int": 237,
        "as_hex": "0x000000ed",
        "description": "Key code constant: Satellite key.\n Switches to digital satellite broadcast service.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_SATELLITE_BS": {
        "as_int": 238,
        "as_hex": "0x000000ee",
        "description": "Key code constant: BS key.\n Switches to BS digital satellite broadcasting service available in Japan.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_SATELLITE_CS": {
        "as_int": 239,
        "as_hex": "0x000000ef",
        "description": "Key code constant: CS key.\n Switches to CS digital satellite broadcasting service available in Japan.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_SATELLITE_SERVICE": {
        "as_int": 240,
        "as_hex": "0x000000f0",
        "description": "Key code constant: BS/CS key.\n Toggles between BS and CS digital satellite services.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_TELETEXT": {
        "as_int": 233,
        "as_hex": "0x000000e9",
        "description": "Key code constant: Teletext key.\n Displays Teletext service.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_TERRESTRIAL_ANALOG": {
        "as_int": 235,
        "as_hex": "0x000000eb",
        "description": "Key code constant: Analog Terrestrial key.\n Switches to analog terrestrial broadcast service.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_TERRESTRIAL_DIGITAL": {
        "as_int": 236,
        "as_hex": "0x000000ec",
        "description": "Key code constant: Digital Terrestrial key.\n Switches to digital terrestrial broadcast service.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_TIMER_PROGRAMMING": {
        "as_int": 258,
        "as_hex": "0x00000102",
        "description": "Key code constant: Timer programming key.\n Goes to the timer recording menu. Corresponds to Timer Programming (0x54) of\n CEC User Control Code.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_TV_ZOOM_MODE": {
        "as_int": 255,
        "as_hex": "0x000000ff",
        "description": "Key code constant: Zoom mode key.\n Changes Zoom mode (Normal, Full, Zoom, Wide-zoom, etc.)",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_U": {
        "as_int": 49,
        "as_hex": "0x00000031",
        "description": "Key code constant: 'U' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_UNKNOWN": {
        "as_int": 0,
        "as_hex": "0x00000000",
        "description": "Key code constant: Unknown key code.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_V": {
        "as_int": 50,
        "as_hex": "0x00000032",
        "description": "Key code constant: 'V' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_1": {
        "as_int": 289,
        "as_hex": "0x00000121",
        "description": "Key code constant: Video Application key #1.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_2": {
        "as_int": 290,
        "as_hex": "0x00000122",
        "description": "Key code constant: Video Application key #2.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_3": {
        "as_int": 291,
        "as_hex": "0x00000123",
        "description": "Key code constant: Video Application key #3.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_4": {
        "as_int": 292,
        "as_hex": "0x00000124",
        "description": "Key code constant: Video Application key #4.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_5": {
        "as_int": 293,
        "as_hex": "0x00000125",
        "description": "Key code constant: Video Application key #5.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_6": {
        "as_int": 294,
        "as_hex": "0x00000126",
        "description": "Key code constant: Video Application key #6.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_7": {
        "as_int": 295,
        "as_hex": "0x00000127",
        "description": "Key code constant: Video Application key #7.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VIDEO_APP_8": {
        "as_int": 296,
        "as_hex": "0x00000128",
        "description": "Key code constant: Video Application key #8.",
        "added": 33,
        "deprecated": None,
    },
    "KEYCODE_VOICE_ASSIST": {
        "as_int": 231,
        "as_hex": "0x000000e7",
        "description": "Key code constant: Voice Assist key.\n Launches the global voice assist activity. Not delivered to applications.",
        "added": 21,
        "deprecated": None,
    },
    "KEYCODE_VOLUME_DOWN": {
        "as_int": 25,
        "as_hex": "0x00000019",
        "description": "Key code constant: Volume Down key.\n Adjusts the speaker volume down.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_VOLUME_MUTE": {
        "as_int": 164,
        "as_hex": "0x000000a4",
        "description": "Key code constant: Volume Mute key.\n Mute key for speaker (unlike KEYCODE_MUTE, which is the mute key for the\n microphone). This key should normally be implemented as a toggle such that the first press\n mutes the speaker and the second press restores the original volume.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_VOLUME_UP": {
        "as_int": 24,
        "as_hex": "0x00000018",
        "description": "Key code constant: Volume Up key.\n Adjusts the speaker volume up.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_W": {
        "as_int": 51,
        "as_hex": "0x00000033",
        "description": "Key code constant: 'W' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_WAKEUP": {
        "as_int": 224,
        "as_hex": "0x000000e0",
        "description": "Key code constant: Wakeup key.\n Wakes up the device.  Behaves somewhat like KEYCODE_POWER but it\n has no effect if the device is already awake.",
        "added": 20,
        "deprecated": None,
    },
    "KEYCODE_WINDOW": {
        "as_int": 171,
        "as_hex": "0x000000ab",
        "description": "Key code constant: Window key.\n On TV remotes, toggles picture-in-picture mode or other windowing functions.\n On Android Wear devices, triggers a display offset.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_X": {
        "as_int": 52,
        "as_hex": "0x00000034",
        "description": "Key code constant: 'X' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_Y": {
        "as_int": 53,
        "as_hex": "0x00000035",
        "description": "Key code constant: 'Y' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_YEN": {
        "as_int": 216,
        "as_hex": "0x000000d8",
        "description": "Key code constant: Japanese Yen key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_Z": {
        "as_int": 54,
        "as_hex": "0x00000036",
        "description": "Key code constant: 'Z' key.",
        "added": 1,
        "deprecated": None,
    },
    "KEYCODE_ZENKAKU_HANKAKU": {
        "as_int": 211,
        "as_hex": "0x000000d3",
        "description": "Key code constant: Japanese full-width / half-width key.",
        "added": 16,
        "deprecated": None,
    },
    "KEYCODE_ZOOM_IN": {
        "as_int": 168,
        "as_hex": "0x000000a8",
        "description": "Key code constant: Zoom in key.",
        "added": 11,
        "deprecated": None,
    },
    "KEYCODE_ZOOM_OUT": {
        "as_int": 169,
        "as_hex": "0x000000a9",
        "description": "Key code constant: Zoom out key.",
        "added": 11,
        "deprecated": None,
    },
    "MAX_KEYCODE": {
        "as_int": 84,
        "as_hex": "0x00000054",
        "description": "This constant was deprecated\n      in API level 15.\n    There are now more than MAX_KEYCODE keycodes.\n Use getMaxKeyCode() instead.",
        "added": 1,
        "deprecated": 15,
    },
    "META_ALT_LEFT_ON": {
        "as_int": 16,
        "as_hex": "0x00000010",
        "description": "This mask is used to check whether the left ALT meta key is pressed.",
        "added": 1,
        "deprecated": None,
    },
    "META_ALT_MASK": {
        "as_int": 50,
        "as_hex": "0x00000032",
        "description": "This mask is a combination of META_ALT_ON, META_ALT_LEFT_ON\n and META_ALT_RIGHT_ON.",
        "added": 11,
        "deprecated": None,
    },
    "META_ALT_ON": {
        "as_int": 2,
        "as_hex": "0x00000002",
        "description": "This mask is used to check whether one of the ALT meta keys is pressed.",
        "added": 1,
        "deprecated": None,
    },
    "META_ALT_RIGHT_ON": {
        "as_int": 32,
        "as_hex": "0x00000020",
        "description": "This mask is used to check whether the right the ALT meta key is pressed.",
        "added": 1,
        "deprecated": None,
    },
    "META_CAPS_LOCK_ON": {
        "as_int": 1048576,
        "as_hex": "0x00100000",
        "description": "This mask is used to check whether the CAPS LOCK meta key is on.",
        "added": 11,
        "deprecated": None,
    },
    "META_CTRL_LEFT_ON": {
        "as_int": 8192,
        "as_hex": "0x00002000",
        "description": "This mask is used to check whether the left CTRL meta key is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_CTRL_MASK": {
        "as_int": 28672,
        "as_hex": "0x00007000",
        "description": "This mask is a combination of META_CTRL_ON, META_CTRL_LEFT_ON\n and META_CTRL_RIGHT_ON.",
        "added": 11,
        "deprecated": None,
    },
    "META_CTRL_ON": {
        "as_int": 4096,
        "as_hex": "0x00001000",
        "description": "This mask is used to check whether one of the CTRL meta keys is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_CTRL_RIGHT_ON": {
        "as_int": 16384,
        "as_hex": "0x00004000",
        "description": "This mask is used to check whether the right CTRL meta key is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_FUNCTION_ON": {
        "as_int": 8,
        "as_hex": "0x00000008",
        "description": "This mask is used to check whether the FUNCTION meta key is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_META_LEFT_ON": {
        "as_int": 131072,
        "as_hex": "0x00020000",
        "description": "This mask is used to check whether the left META meta key is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_META_MASK": {
        "as_int": 458752,
        "as_hex": "0x00070000",
        "description": "This mask is a combination of META_META_ON, META_META_LEFT_ON\n and META_META_RIGHT_ON.",
        "added": 11,
        "deprecated": None,
    },
    "META_META_ON": {
        "as_int": 65536,
        "as_hex": "0x00010000",
        "description": "This mask is used to check whether one of the META meta keys is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_META_RIGHT_ON": {
        "as_int": 262144,
        "as_hex": "0x00040000",
        "description": "This mask is used to check whether the right META meta key is pressed.",
        "added": 11,
        "deprecated": None,
    },
    "META_NUM_LOCK_ON": {
        "as_int": 2097152,
        "as_hex": "0x00200000",
        "description": "This mask is used to check whether the NUM LOCK meta key is on.",
        "added": 11,
        "deprecated": None,
    },
    "META_SCROLL_LOCK_ON": {
        "as_int": 4194304,
        "as_hex": "0x00400000",
        "description": "This mask is used to check whether the SCROLL LOCK meta key is on.",
        "added": 11,
        "deprecated": None,
    },
    "META_SHIFT_LEFT_ON": {
        "as_int": 64,
        "as_hex": "0x00000040",
        "description": "This mask is used to check whether the left SHIFT meta key is pressed.",
        "added": 1,
        "deprecated": None,
    },
    "META_SHIFT_MASK": {
        "as_int": 193,
        "as_hex": "0x000000c1",
        "description": "This mask is a combination of META_SHIFT_ON, META_SHIFT_LEFT_ON\n and META_SHIFT_RIGHT_ON.",
        "added": 11,
        "deprecated": None,
    },
    "META_SHIFT_ON": {
        "as_int": 1,
        "as_hex": "0x00000001",
        "description": "This mask is used to check whether one of the SHIFT meta keys is pressed.",
        "added": 1,
        "deprecated": None,
    },
    "META_SHIFT_RIGHT_ON": {
        "as_int": 128,
        "as_hex": "0x00000080",
        "description": "This mask is used to check whether the right SHIFT meta key is pressed.",
        "added": 1,
        "deprecated": None,
    },
    "META_SYM_ON": {
        "as_int": 4,
        "as_hex": "0x00000004",
        "description": "This mask is used to check whether the SYM meta key is pressed.",
        "added": 1,
        "deprecated": None,
    },
}
subprocess_method = subprocess.Popen

iswindows = "win" in platform.platform().lower()
if iswindows:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    creationflags = subprocess.CREATE_NO_WINDOW
    invisibledict = {
        "startupinfo": startupinfo,
        "creationflags": creationflags,
        "start_new_session": True,
    }
    from ctypes import wintypes
    import ctypes

    windll = ctypes.LibraryLoader(ctypes.WinDLL)
    kernel32 = windll.kernel32

    _GetShortPathNameW = kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    _GetShortPathNameW.restype = wintypes.DWORD

else:
    invisibledict = {}

re_split_quotes = re.compile("(['\"])")
from normaltext import lookup


@functools.cache
def get_short_path_name(long_name):
    if not iswindows:
        return long_name
    try:
        if not os.path.exists(long_name):
            return long_name

        output_buf_size = 4096
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        _ = _GetShortPathNameW(long_name, output_buf, output_buf_size)
        pa = output_buf.value
        return pa if os.path.exists(pa) else long_name
    except Exception:
        return long_name


def get_tmpfile(suffix=".txt"):
    tfp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    filename = tfp.name
    filename = os.path.normpath(filename)
    tfp.close()
    return filename, partial(os.remove, tfp.name)


def _format_command(
    adbpath,
    serial_number,
    cmd,
    su=False,
    use_busybox=False,
    errors="strict",
    use_short_adb_path=True,
    add_exit=True,
):
    wholecommand = [get_short_path_name(adbpath) if use_short_adb_path else adbpath]
    nolimitcommand = []

    base64_command = base64.standard_b64encode(cmd.encode("utf-8", errors)).decode(
        "utf-8", errors
    )
    base64_command = "'" + base64_command + "'"
    if serial_number:
        wholecommand.extend(["-s", serial_number])
    wholecommand.extend(["shell"])
    if su:
        wholecommand.extend(["su", "--"])

    nolimitcommand.extend(["echo", base64_command, "|"])
    if use_busybox:
        nolimitcommand.extend(["busybox"])
    nolimitcommand.extend(["base64", "-d", "|", "sh"])

    exit_u = "\nexit\n"
    exit_b = b"\nexit\n"
    if not add_exit:
        exit_u = ""
        exit_b = b""
    nolimitcommand_no_bytes = " ".join(nolimitcommand) + exit_u
    nolimitcommand_bytes = " ".join(nolimitcommand).encode("utf-8", errors) + exit_b
    return nolimitcommand_no_bytes, nolimitcommand_bytes, wholecommand


def split_text_at_quotes(text):
    return [
        f"'{x}'" if x not in '''\'""''' else repr(x)
        for x in re_split_quotes.split(text)
    ]


def split_text_in_letters(text):
    return [f"'{x}'" if x not in '''\'""''' else repr(x) for x in text]


def remove_accents_from_text(text):
    textlist = []
    for t in text.splitlines():
        t = t.replace("ß", "ss").replace("ẞ", "SS")
        t = "".join(
            [
                lookup(k, case_sens=True, replace="", add_to_printable="")["suggested"]
                for k in t
            ]
        )
        textlist.append(t)
    text = "\n".join(textlist)
    return text


def split_text_in_chars_or_parts(text, sleep_after_letter):
    if sum(sleep_after_letter) == 0:
        return split_text_at_quotes(text)
    else:
        return split_text_in_letters(text)


def sleep_random_time(sleep_after_letter):
    if sum(sleep_after_letter) > 0:
        sleep(random.uniform(*sleep_after_letter))


def format_input_command(input_device, action, command):
    if input_device:
        cmd2send = f"input {input_device} {action} {command}"
    else:
        cmd2send = f"input {action} {command}"
    return cmd2send


def input_text_subprocess(
    adbpath,
    serial_number,
    text,
    su=False,
    use_busybox=False,
    errors="strict",
    use_short_adb_path=True,
    add_exit=True,
    remove_accents=False,
    sleep_after_letter=(0, 0),
    print_stdout=False,
    print_stderr=True,
    decode_stdout_print=True,
    input_device: valid_input_devices = "",
    **kwargs,
):
    if remove_accents:
        text = remove_accents_from_text(text)
    stdoutlist = []
    stderrlist = []
    splitext = split_text_in_chars_or_parts(text, sleep_after_letter)
    for c in splitext:
        cmd2send = format_input_command(input_device, action="text", command=c)

        nolimitcommand_no_bytes, nolimitcommand_bytes, wholecommand = _format_command(
            adbpath,
            serial_number,
            cmd2send,
            su=su,
            use_busybox=use_busybox,
            errors=errors,
            use_short_adb_path=use_short_adb_path,
            add_exit=add_exit,
        )
        p = subprocess.run(
            wholecommand,
            input=nolimitcommand_bytes,
            capture_output=True,
            **invisibledict,
        )

        stdout = replace_rn_n(p.stdout.splitlines())
        stderr = replace_rn_n(p.stderr.splitlines())
        print_stdout_stderr(
            print_stdout, print_stderr, stdout, stderr, decode_stdout_print=True
        )
        stdoutlist.extend(stdout)
        stderrlist.extend(stderr)

        sleep_random_time(sleep_after_letter)
    return stdoutlist, stderrlist


def print_stdout_stderr(
    print_stdout, print_stderr, stdout, stderr, decode_stdout_print=True
):
    if print_stderr:
        for errorline in stderr:
            if errorline:
                sys.stderr.write(errorline.decode("utf-8", "backslashreplace"))
    if print_stdout:
        for line in stdout:
            if line:
                if decode_stdout_print:
                    sys.stdout.write(line.decode("utf-8", "backslashreplace"))
                else:
                    print(line)


def replace_rn_n(text):
    if isinstance(text, bytes):
        return text.replace(b"\r\n", b"\n")
    return [x.replace(b"\r\n", b"\n") for x in text]


def input_text_ps(
    adbpath,
    serial_number,
    text,
    su=False,
    use_busybox=False,
    errors="strict",
    use_short_adb_path=True,
    add_exit=True,
    remove_accents=False,
    sleep_after_letter=(0, 0),
    delete_tempfiles=True,
    print_stdout=False,
    print_stderr=True,
    decode_stdout_print=True,
    input_device: valid_input_devices = "",
    **kwargs,
):
    if remove_accents:
        text = remove_accents_from_text(text)
    stdoutlist = []
    stderrlist = []
    splitext = split_text_in_chars_or_parts(text, sleep_after_letter)
    for c in splitext:
        cmd2send = format_input_command(input_device, action="text", command=c)

        stdout, stderr = adb_shell_ps(
            adbpath,
            serial_number,
            cmd=cmd2send,
            timeout=0,
            sleeptime=0,
            su=su,
            use_busybox=use_busybox,
            errors=errors,
            use_short_adb_path=use_short_adb_path,
            add_exit=add_exit,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
            delete_tempfiles=delete_tempfiles,
            **kwargs,
        )
        stdoutlist.extend(stdout)
        stderrlist.extend(stderr)
        sleep_random_time(sleep_after_letter)

    return stdoutlist, stderrlist


def kill_subproc(p, t=()):
    try:
        p.stdin.close()
    except Exception:
        pass
    try:
        p.stdout.close()
    except Exception:
        pass
    try:
        p.stderr.close()
    except Exception:
        pass
    try:
        p.kill()
    except Exception:
        pass
    if t:
        for tt in t:
            try:
                tt.kill()
            except Exception:
                pass


def adb_shell_subprocess(
    adbpath,
    serial_number,
    cmd,
    timeout=0,
    sleeptime=0.00001,
    su=False,
    use_busybox=False,
    errors="strict",
    use_short_adb_path=False,
    add_exit=True,
    print_stdout=False,
    print_stderr=True,
    decode_stdout_print=True,
    **kwargs,
):
    def read_stdout_thread():
        try:
            nonlocal finish
            for q in iter(p.stdout.readline, b""):
                l = q.replace(b"\r\n", b"\n")
                if print_stdout:
                    if decode_stdout_print:
                        sys.stdout.write(l.decode("utf-8", "backslashreplace"))
                    else:
                        print(l)
                stdoutlist.append(l)
            p.stdout.close()
            finish = True
        except Exception:
            pass

    def read_stderr_thread():
        nonlocal finish
        try:
            for q in iter(p.stderr.readline, b""):
                l = q.replace(b"\r\n", b"\n")

                if print_stderr:
                    sys.stderr.write(l.decode("utf-8", "backslashreplace"))
                stderrlist.append(l)
            p.stderr.close()
            finish = True
        except Exception:
            pass

    finish = False
    nolimitcommand_no_bytes, nolimitcommand_bytes, wholecommand = _format_command(
        adbpath,
        serial_number,
        cmd,
        su=su,
        use_busybox=use_busybox,
        errors=errors,
        use_short_adb_path=use_short_adb_path,
        add_exit=add_exit,
    )
    kwargs.update(
        {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    )
    kwargs.update(invisibledict)
    p = subprocess.Popen(wholecommand, **kwargs)
    p.stdin.write(nolimitcommand_bytes)
    p.stdin.close()
    t1 = kthread.KThread(target=read_stdout_thread, name="read_stdout_thread")
    t2 = kthread.KThread(target=read_stderr_thread, name="read_stderr_thread")
    stdoutlist = []
    stderrlist = []
    t1.start()
    t2.start()
    if timeout > 0:
        timeout = timeout + time.time()
    try:
        while not finish:
            if timeout:
                if time.time() > timeout:
                    kill_subproc(p, t=[t1, t2])
                    break
            if sleeptime:
                sleep(sleeptime)
    except KeyboardInterrupt:
        kill_subproc(p, t=[t1, t2])
    return stdoutlist, stderrlist


def adb_shell_ps(
    adbpath,
    serial_number,
    cmd,
    timeout=0,
    sleeptime=0,
    su=False,
    use_busybox=False,
    errors="strict",
    use_short_adb_path=False,
    add_exit=True,
    print_stdout=False,
    print_stderr=True,
    decode_stdout_print=True,
    delete_tempfiles=True,
    **kwargs,
):
    if not timeout:
        psutil_timeout = 100000000
    else:
        psutil_timeout = timeout
    nolimitcommand_no_bytes, nolimitcommand_bytes, wholecommand = _format_command(
        adbpath,
        serial_number,
        cmd,
        su=su,
        use_busybox=use_busybox,
        errors=errors,
        use_short_adb_path=use_short_adb_path,
        add_exit=add_exit,
    )
    p = DetachedPopen(
        args=wholecommand,
        bufsize=-1,
        executable=None,
        stdin=nolimitcommand_no_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=None,
        close_fds=True,
        shell=False,
        cwd=None,
        env=None,
        universal_newlines=None,
        startupinfo=None,
        creationflags=0,
        restore_signals=True,
        start_new_session=False,
        pass_fds=(),
        user=None,
        group=None,
        extra_groups=None,
        encoding=None,
        errors=None,
        text=None,
        umask=-1,
        pipesize=-1,
        window_style="Hidden",
        wait=False,
        verb=None,
        what_if=False,
        print_stdout=False,
        print_stderr=False,
        capture_stdout=True,
        capture_stderr=True,
        stdoutbuffer=None,
        stderrbuffer=None,
        psutil_timeout=psutil_timeout,
        delete_tempfiles=delete_tempfiles,
        read_stdout_stderr_async=False,
        args_to_83=False,
    )

    stdout = replace_rn_n(p.stdout.readlines())
    stderr = replace_rn_n(p.stderr.readlines())
    print_stdout_stderr(print_stdout, print_stderr, stdout, stderr, decode_stdout_print)
    return stdout, stderr


def format_adb_command(cmd):
    return absolut_wpath_to_83(
        cmd,
        valid_string_ends=(
            "<",
            ">",
            ":",
            '"',
            "|",
            "?",
            "*",
            "\n",
            "\r",
            " ",
        ),
    )


def adb_subprocess(
    adbpath,
    serial_number,
    cmd,
    to_83=True,
    timeout=0,
    sleeptime=0.00001,
    print_stdout=True,
    print_stderr=True,
    decode_stdout_print=True,
    delete_tempfiles=True,
    **kwargs,
):
    def read_stdout_thread():
        try:
            nonlocal finish
            for q in iter(p.stdout.readline, b""):
                l = q.replace(b"\r\n", b"\n")
                if print_stdout:
                    if decode_stdout_print:
                        sys.stdout.write(l.decode("utf-8", "backslashreplace"))
                    else:
                        print(l)
                stdoutlist.append(l)
            p.stdout.close()
            finish = True
        except Exception:
            pass

    def read_stderr_thread():
        nonlocal finish
        try:
            for q in iter(p.stderr.readline, b""):
                l = q.replace(b"\r\n", b"\n")

                if print_stderr:
                    sys.stderr.write(l.decode("utf-8", "backslashreplace"))
                stderrlist.append(l)
            p.stderr.close()
            finish = True
        except Exception:
            pass

    if to_83:
        cmd = format_adb_command(cmd)
    wholecommand = f"{adbpath} -s {serial_number} {cmd}"
    finish = False
    kwargs.update(
        {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    )
    kwargs.update(invisibledict)
    p = subprocess.Popen(wholecommand, **kwargs)
    t1 = kthread.KThread(target=read_stdout_thread, name="read_stdout_thread")
    t2 = kthread.KThread(target=read_stderr_thread, name="read_stderr_thread")
    stdoutlist = []
    stderrlist = []
    t1.start()
    t2.start()
    if timeout > 0:
        timeout = timeout + time.time()
    try:
        while not finish:
            if timeout:
                if time.time() > timeout:
                    kill_subproc(p, t=[t1, t2])
                    break
            if sleeptime:
                sleep(sleeptime)
    except KeyboardInterrupt:
        kill_subproc(p, t=[t1, t2])
    return stdoutlist, stderrlist


def adb_ps(
    adbpath,
    serial_number,
    cmd,
    to_83=True,
    timeout=0,
    sleeptime=0.00001,
    print_stdout=True,
    print_stderr=True,
    decode_stdout_print=True,
    delete_tempfiles=True,
    **kwargs,
):
    if not timeout:
        psutil_timeout = 100000000
    else:
        psutil_timeout = timeout
    if to_83:
        cmd = format_adb_command(cmd)
    wholecommand = [f"{adbpath}", "-s", f"{serial_number}" f" {cmd.lstrip()}"]
    p = DetachedPopen(
        args=wholecommand,
        bufsize=-1,
        executable=None,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=None,
        close_fds=True,
        shell=False,
        cwd=None,
        env=None,
        universal_newlines=None,
        startupinfo=None,
        creationflags=0,
        restore_signals=True,
        start_new_session=False,
        pass_fds=(),
        user=None,
        group=None,
        extra_groups=None,
        encoding=None,
        errors=None,
        text=None,
        umask=-1,
        pipesize=-1,
        window_style="Hidden",
        wait=False,
        verb=None,
        what_if=False,
        print_stdout=False,
        print_stderr=False,
        capture_stdout=True,
        capture_stderr=True,
        stdoutbuffer=None,
        stderrbuffer=None,
        psutil_timeout=psutil_timeout,
        delete_tempfiles=delete_tempfiles,
        read_stdout_stderr_async=False,
        args_to_83=False,
    )

    stdout = replace_rn_n(p.stdout.readlines())
    stderr = replace_rn_n(p.stderr.readlines())
    print_stdout_stderr(print_stdout, print_stderr, stdout, stderr, decode_stdout_print)
    return stdout, stderr


def is_keyboard_shown(
    adbpath,
    serial_number,
    use_busybox=False,
    use_short_adb_path=True,
    **kwargs,
):
    stdout, stderr = adb_shell_subprocess(
        adbpath,
        serial_number,
        cmd=module_cfg.ADB_IS_KEYBOARD_SHOWN,
        timeout=0,
        sleeptime=0.00001,
        su=False,
        use_busybox=use_busybox,
        errors="strict",
        use_short_adb_path=use_short_adb_path,
        add_exit=True,
        print_stdout=False,
        print_stderr=True,
        decode_stdout_print=True,
        **kwargs,
    )
    keyboardthere = False
    for q in stdout:
        if b"mInputShown=true" in q:
            keyboardthere = True
            break
    return keyboardthere


def get_active_keyboard(
    adbpath,
    serial_number,
    use_busybox=False,
    use_short_adb_path=True,
    **kwargs,
):
    stdout, stderr = adb_shell_subprocess(
        adbpath,
        serial_number,
        cmd=module_cfg.ADB_GET_DEFAULT_KEYBOARD,
        timeout=0,
        sleeptime=0.00001,
        su=False,
        use_busybox=use_busybox,
        errors="strict",
        use_short_adb_path=use_short_adb_path,
        add_exit=True,
        print_stdout=False,
        print_stderr=True,
        decode_stdout_print=True,
        **kwargs,
    )
    active_keyboartd = []
    for q in stdout:
        if not q[:1].isspace():
            active_keyboartd.append(q.decode("utf-8", "backslashreplace").strip())
    return active_keyboartd[0]


def change_keyboard(
    adbpath,
    serial_number,
    keyboard="com.android.inputmethod.latin/.LatinIME",
    use_busybox=False,
    use_short_adb_path=True,
    print_stdout=True,
    print_stderr=True,
    decode_stdout_print=True,
):
    actkeyb = get_active_keyboard(
        adbpath,
        serial_number,
        use_busybox=use_busybox,
        use_short_adb_path=use_short_adb_path,
    )
    stdoutlist = []
    stderrlist = []
    if actkeyb != keyboard:
        stdout, stderr = adb_shell_subprocess(
            adbpath,
            serial_number,
            cmd=module_cfg.ADB_DISABLE_KEYBOARD % actkeyb,
            timeout=0,
            sleeptime=0.00001,
            su=False,
            use_busybox=use_busybox,
            errors="strict",
            use_short_adb_path=use_short_adb_path,
            add_exit=True,
            print_stdout=False,
            print_stderr=True,
            decode_stdout_print=True,
        )
        stdoutlist.extend(stdout)
        stderrlist.extend(stderr)

        stdout, stderr = adb_shell_subprocess(
            adbpath,
            serial_number,
            cmd=module_cfg.ADB_ENABLE_KEYBOARD % keyboard,
            timeout=0,
            sleeptime=0.00001,
            su=False,
            use_busybox=use_busybox,
            errors="strict",
            use_short_adb_path=use_short_adb_path,
            add_exit=True,
            print_stdout=False,
            print_stderr=True,
            decode_stdout_print=True,
        )
        stdoutlist.extend(stdout)
        stderrlist.extend(stderr)
        stdout, stderr = adb_shell_subprocess(
            adbpath,
            serial_number,
            cmd=module_cfg.ADB_SET_KEYBOARD % keyboard,
            timeout=0,
            sleeptime=0.00001,
            su=False,
            use_busybox=use_busybox,
            errors="strict",
            use_short_adb_path=use_short_adb_path,
            add_exit=True,
            print_stdout=False,
            print_stderr=True,
            decode_stdout_print=True,
        )
        stdoutlist.extend(stdout)
        stderrlist.extend(stderr)
        actkeyb = get_active_keyboard(
            adbpath,
            serial_number,
            use_busybox=use_busybox,
            use_short_adb_path=use_short_adb_path,
        )
    print_stdout_stderr(
        print_stdout, print_stderr, stdoutlist, stderrlist, decode_stdout_print
    )

    if actkeyb != keyboard:
        return False
    return True


def change_to_adb_keyboard(
    adbpath,
    serial_number,
    use_busybox=False,
    use_short_adb_path=True,
    print_stdout=True,
    print_stderr=True,
    decode_stdout_print=True,
):
    return change_keyboard(
        adbpath,
        serial_number,
        keyboard=module_cfg.ADB_KEYBOARD_NAME,
        use_busybox=use_busybox,
        use_short_adb_path=use_short_adb_path,
        print_stdout=print_stdout,
        print_stderr=print_stderr,
        decode_stdout_print=decode_stdout_print,
    )


def input_text_adbkeyboard(
    adbpath,
    serial_number,
    text,
    use_subprocess=True,
    change_back=True,
    timeout=0,
    sleeptime=(0, 0),
    su=False,
    use_busybox=False,
    errors="strict",
    use_short_adb_path=False,
    add_exit=True,
    print_stdout=False,
    print_stderr=True,
    decode_stdout_print=True,
    delete_tempfiles=True,
    **kwargs,
):
    active_keyboard = ""
    if change_back:
        active_keyboard = get_active_keyboard(adbpath, serial_number)
        print(active_keyboard)
    if not change_to_adb_keyboard(adbpath, serial_number):
        raise OSError("Could not activate ADB-Keyboard")
    stdout_list, stderr_list = [], []
    as_letters = sum(sleeptime) > 0
    if as_letters:
        text = list(text)
    else:
        text = [text]

    for t in text:
        charsb64 = base64.b64encode(t.encode("utf-8")).decode()

        if use_subprocess:
            stdout, stderr = adb_shell_subprocess(
                adbpath,
                serial_number,
                cmd=module_cfg.ADB_KEYBOARD_COMMAND % charsb64,
                timeout=timeout,
                sleeptime=0.005,
                su=su,
                use_busybox=use_busybox,
                errors=errors,
                use_short_adb_path=use_short_adb_path,
                add_exit=add_exit,
                print_stdout=print_stdout,
                print_stderr=print_stderr,
                decode_stdout_print=decode_stdout_print,
                **kwargs,
            )
        else:
            stdout, stderr = adb_shell_ps(
                adbpath,
                serial_number,
                cmd=module_cfg.ADB_KEYBOARD_COMMAND % charsb64,
                timeout=timeout,
                sleeptime=0.005,
                su=su,
                use_busybox=use_busybox,
                errors=errors,
                use_short_adb_path=use_short_adb_path,
                add_exit=add_exit,
                print_stdout=print_stdout,
                print_stderr=print_stderr,
                decode_stdout_print=decode_stdout_print,
                delete_tempfiles=delete_tempfiles,
                **kwargs,
            )
        stdout_list.extend(stdout)
        stderr_list.extend(stderr)
        sleep_random_time(sleeptime)
    if change_back:
        sleep(0.1)
        active_keyboard2 = get_active_keyboard(adbpath, serial_number)
        while active_keyboard != active_keyboard2:
            change_keyboard(adbpath, serial_number, active_keyboard)
            active_keyboard2 = get_active_keyboard(adbpath, serial_number)

    return stdout_list, stderr_list


def install_adb_keyboard(
    adbpath,
    serial_number,
    url=r"https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk",
    use_short_adb_path=True,
    **kwargs,
):
    tmpfile_, removetmpfile = get_tmpfile(".apk")

    with requests.get(url) as r:
        keyb = r.content
        if r.status_code != 200:
            raise Exception(f"Could not download ADBKeyboard.apk from {url}")
        with open(tmpfile_, mode="wb") as f:
            f.write(keyb)
    kwargs = kwargs.copy()
    kwargs.update(invisibledict)
    subprocess.run(
        f"{get_short_path_name(adbpath) if use_short_adb_path else adbpath} -s {serial_number} install {tmpfile_}",
        **kwargs,
    )

    while True:
        try:
            removetmpfile()
            break
        except Exception:
            sleep(1)
            continue


class AdbEasyKey:
    def __init__(self, adb_path, device_serial, use_busybox=False):
        self.adb_path = adb_path
        self.adbpath = get_short_path_name(adb_path)
        self.device_serial = device_serial
        self.use_busybox = use_busybox
        key_events_with_press = deepcopy(module_cfg.key_events)
        for key, item in module_cfg.key_events.items():
            key_events_with_press[key]["press_ps"] = PressKey(
                adb_shell_ps,
                self.adbpath,
                self.device_serial,
                item["as_int"],
                item["description"],
                False,
            )
            key_events_with_press[key]["longpress_ps"] = PressKey(
                adb_shell_ps,
                self.adbpath,
                self.device_serial,
                item["as_int"],
                item["description"],
                True,
            )
            key_events_with_press[key]["press_subproc"] = PressKey(
                adb_shell_subprocess,
                self.adbpath,
                self.device_serial,
                item["as_int"],
                item["description"],
                False,
            )
            key_events_with_press[key]["longpress_subproc"] = PressKey(
                adb_shell_subprocess,
                self.adbpath,
                self.device_serial,
                item["as_int"],
                item["description"],
                True,
            )

        self.keyevents = PunktDict(key_events_with_press)

    def connect_to_device_subprocess(
        self,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
        **kwargs,
    ):
        p = subprocess.run(
            f"{self.adbpath} connect {self.device_serial}",
            capture_output=True,
            **kwargs,
            **invisibledict,
        )
        stdout = p.stdout.splitlines()
        stderr = p.stderr.splitlines()
        print_stdout_stderr(
            print_stdout, print_stderr, stdout, stderr, decode_stdout_print
        )
        return stdout, stderr

    def connect_to_device_ps(
        self,
        timeout=0,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        if not timeout:
            psutil_timeout = 100000000
        else:
            psutil_timeout = timeout
        wholecommand = [f"{self.adbpath}", "connect", f"{self.device_serial}"]
        p = DetachedPopen(
            args=wholecommand,
            bufsize=-1,
            executable=None,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=None,
            close_fds=True,
            shell=False,
            cwd=None,
            env=None,
            universal_newlines=None,
            startupinfo=None,
            creationflags=0,
            restore_signals=True,
            start_new_session=False,
            pass_fds=(),
            user=None,
            group=None,
            extra_groups=None,
            encoding=None,
            errors=None,
            text=None,
            umask=-1,
            pipesize=-1,
            window_style="Hidden",
            wait=False,
            verb=None,
            what_if=False,
            print_stdout=False,
            print_stderr=False,
            capture_stdout=True,
            capture_stderr=True,
            stdoutbuffer=None,
            stderrbuffer=None,
            psutil_timeout=psutil_timeout,
            delete_tempfiles=True,
            read_stdout_stderr_async=False,
            args_to_83=False,
        )

        stdout = replace_rn_n(p.stdout.readlines())
        stderr = replace_rn_n(p.stderr.readlines())
        print_stdout_stderr(
            print_stdout, print_stderr, stdout, stderr, decode_stdout_print
        )
        return stdout, stderr

    def input_text_adb_keyboard_subprocess(
        self, text, change_back=True, sleeptime=(0, 0), add_exit=True
    ):
        return input_text_adbkeyboard(
            self.adbpath,
            self.device_serial,
            text,
            use_subprocess=True,
            change_back=change_back,
            timeout=0,
            sleeptime=sleeptime,
            su=False,
            use_busybox=self.use_busybox,
            errors="strict",
            use_short_adb_path=False,
            add_exit=add_exit,
            print_stdout=False,
            print_stderr=True,
            decode_stdout_print=True,
            delete_tempfiles=True,
        )

    def input_text_adb_keyboard_ps(
        self, text, change_back=True, sleeptime=(0, 0), add_exit=True
    ):
        return input_text_adbkeyboard(
            self.adbpath,
            self.device_serial,
            text,
            use_subprocess=False,
            change_back=change_back,
            timeout=0,
            sleeptime=sleeptime,
            su=False,
            use_busybox=self.use_busybox,
            errors="strict",
            use_short_adb_path=False,
            add_exit=add_exit,
            print_stdout=False,
            print_stderr=True,
            decode_stdout_print=True,
            delete_tempfiles=True,
        )

    def input_text_subprocess(
        self,
        text,
        remove_accents=False,
        sleeptime=(0, 0),
        add_exit=True,
        input_device: valid_input_devices = "",
    ):
        return input_text_subprocess(
            self.adbpath,
            self.device_serial,
            text,
            su=False,
            use_busybox=self.use_busybox,
            errors="strict",
            use_short_adb_path=False,
            add_exit=add_exit,
            remove_accents=remove_accents,
            sleep_after_letter=sleeptime,
            input_device=input_device,
        )

    def input_text_ps(
        self,
        text,
        remove_accents=False,
        sleeptime=(0, 0),
        add_exit=True,
        input_device: valid_input_devices = "",
    ):
        return input_text_ps(
            self.adbpath,
            self.device_serial,
            text,
            su=False,
            use_busybox=self.use_busybox,
            errors="strict",
            use_short_adb_path=False,
            add_exit=add_exit,
            remove_accents=remove_accents,
            sleep_after_letter=sleeptime,
            input_device=input_device,
        )

    def adb_shell_subprocess(
        self,
        cmd,
        timeout=0,
        sleeptime=0.0001,
        su=False,
        add_exit=True,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        return adb_shell_subprocess(
            self.adbpath,
            self.device_serial,
            cmd=cmd,
            timeout=timeout,
            sleeptime=sleeptime,
            su=su,
            use_busybox=self.use_busybox,
            errors="strict",
            use_short_adb_path=False,
            add_exit=add_exit,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
        )

    def adb_shell_ps(
        self,
        cmd,
        timeout=0,
        sleeptime=0.0001,
        su=False,
        add_exit=True,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        return adb_shell_ps(
            self.adbpath,
            self.device_serial,
            cmd=cmd,
            timeout=timeout,
            sleeptime=sleeptime,
            su=su,
            use_busybox=self.use_busybox,
            errors="strict",
            use_short_adb_path=False,
            add_exit=add_exit,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
        )

    def adb_subprocess(
        self,
        cmd,
        to_83=True,
        timeout=0,
        sleeptime=0.00001,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        return adb_subprocess(
            self.adbpath,
            self.device_serial,
            cmd=cmd,
            to_83=to_83,
            timeout=timeout,
            sleeptime=sleeptime,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
        )

    def adb_ps(
        self,
        cmd,
        to_83=True,
        timeout=0,
        sleeptime=0.00001,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        return adb_ps(
            self.adbpath,
            self.device_serial,
            cmd=cmd,
            to_83=to_83,
            timeout=timeout,
            sleeptime=sleeptime,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
            delete_tempfiles=True,
        )

    def install_adb_keyboard(
        self, url=r"https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk"
    ):
        install_adb_keyboard(
            self.adbpath,
            self.device_serial,
            url=url,
            use_short_adb_path=False,
        )

    def change_keyboard(
        self,
        keyboard="com.android.inputmethod.latin/.LatinIME",
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        return change_keyboard(
            self.adbpath,
            self.device_serial,
            keyboard=keyboard,
            use_busybox=self.use_busybox,
            use_short_adb_path=False,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
        )

    def change_to_adb_keyboard(
        self,
        print_stdout=True,
        print_stderr=True,
        decode_stdout_print=True,
    ):
        return change_to_adb_keyboard(
            self.adbpath,
            self.device_serial,
            use_busybox=self.use_busybox,
            use_short_adb_path=False,
            print_stdout=print_stdout,
            print_stderr=print_stderr,
            decode_stdout_print=decode_stdout_print,
        )

    def is_keyboard_shown(self):
        return is_keyboard_shown(
            self.adbpath,
            self.device_serial,
            use_busybox=self.use_busybox,
            use_short_adb_path=False,
        )

    def get_active_keyboard(self):
        return get_active_keyboard(
            self.adbpath,
            self.device_serial,
            use_busybox=self.use_busybox,
            use_short_adb_path=False,
        )
