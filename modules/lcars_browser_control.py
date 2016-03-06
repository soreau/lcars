#!/usr/bin/env python

# Linux Command Active Recognition System
# Copyright (C) 2015-2016  Scott Moreau

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import sys

def condition(lcars, string):
	words = string.split()
	if words[0] == "close" and words[1] == "tab":
		return True, 0

	return False, 0

def do_action(lcars, string, case):
	os.system("focus_wid=$(xdotool getwindowfocus); xdotool windowactivate --sync $(xdotool search --class Chrome | tail -n 1) key Control_L+w & sleep 0.3; xdotool windowactivate $focus_wid")

	return "Closing tab"
