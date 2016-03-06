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
from random import randint
from pygoogle import pygoogle

def condition(lcars, string):
	action = string.split(' ', 1)[0]

	if action == "play":
		return True, 0

	return False, 0

def do_action(lcars, string, case):
	target = string.split(' ', 1)[1]

	g = pygoogle("site:youtube.com " + target)
	g.pages = 1
	urls = g.get_urls()
	if len(urls) == 0:
		reply = "No results found for" + target
		lcars.reply_with(reply)
		return reply
	link = urls[0]

	if "user" in link or "store" in link or "feed" in link or "playlist" in link or "channel" in link:
		for url in urls:
			if "user" in url:
				link = "http://youtube.nestharion.de/" + url.split('/')[-1]
				break
		if not link:
			for url in urls:
				if "store" in url or "feed" in url or "playlist" in url or "channel" in url:
					continue
				else:
					link = url
					break
	if not link:
		link = urls[randint(0, len(urls) - 1)]

	lcars.background(["google-chrome", link])
	reply = "Playing " + target
	lcars.reply_with(reply)

	return reply
