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

	if len(words) > 3 and (words[0] == "what's" or words[0] == "how's") and words[1] == "the"		\
	and words[2] == "weather" and (words[3] == "in" or words[3] == "for"):
		return True, 0
	elif len(words) > 4 and ((words[0] == "what's" or words[0] == "how's") and words[1] == "the"	\
	and words[2] == "weather" and words[3] == "like" and (words[4] == "in" or words[4] == "for"))	\
	or ((words[0] == "what" or words[0] == "how" or words[0] == "show")								\
	and (words[1] == "is" or words[1] == "me") and words[2] == "the"								\
	and words[3] == "weather" and (words[4] == "in" or words[4] == "for")):
		return True, 1
	elif len(words) > 5 and (words[0] == "what" or words[0] == "how" or words[0] == "show")			\
	and (words[1] == "is" or words[1] == "me") and words[2] == "the" and words[3] == "weather"		\
	and words[4] == "like" and (words[5] == "in" or words[5] == "for"):
		return True, 2

	return False, 0

def do_action(lcars, string, case):
	words = string.split()
	target = ' '.join(words[(case + 4):])
	target.replace(' ', '+')
	link = "https://www.google.com/search?&q=weather+"

	lcars.background(["google-chrome", link + target])
	reply = "Here is the weather for " + target
	lcars.reply_with(reply)
	os.system("sleep 1")
	os.system("xdotool windowactivate --sync $(xdotool search --class Chrome | tail -n 1)")

	return reply
