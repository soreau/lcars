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
	action = string.split(' ', 1)[0]

	if len(string.split()) > 1 and action == "google":
		return True, 0

	return False, 0

def do_action(lcars, string, case):
	target = string.split(' ', 1)[1]
	target.replace(' ', '+')
	link = "https://www.google.com/search?&q=" + target

	lcars.background(["google-chrome", link])
	reply = "Googling " + target
	lcars.reply_with(reply)
	os.system("sleep 1")
	os.system("xdotool windowactivate --sync $(xdotool search --class Chrome | tail -n 1)")

	return reply
