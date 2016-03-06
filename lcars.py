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
import glob
import select
import collections
from socket import *
from time import sleep
from Queue import Queue
from daemon import Daemon
from threading import Thread
import speech_recognition as sr

max_msg_size = 1024

sys.path.append("./common")
home_dir = os.environ['HOME']
sys.path.append(home_dir + "/.lcars/common")
import lcars_common as lcars

config_file = home_dir + "/.lcars/config"
socket_file = "/tmp/lcars_socket"

lcars_plugin = collections.namedtuple("lcars_plugin", "name module")

def load_config():
	section = None
	if os.path.exists(config_file):
		print("Opening " + config_file)
		try:
			f = open(config_file, "r")
			data = f.readlines()
			i = 0
			while i < len(data):
				line = data[i]
				line = line.strip()
				if not len(line) or line[0] is "#":
					i += 1
					continue
				if "core" in line:
					section = "core"
				elif "plugins" in line:
					section = "plugins"
				elif section == "core":
					if not "=" in line:
						i += 1
						continue
					name, value = line.split("=")
					value = value.strip("\"")
					if name == "trigger":
						lcars.trigger = value
					elif name == "response":
						lcars.response = value
					elif name == "disable_trigger":
						lcars.disable_trigger = value
					elif name == "run_in_background":
						lcars.run_in_background = value
				elif section == "plugins":
					if "[" in line and "]" in line and not "=" in line:
						plugin = line.strip("[]")
						i += 1
						line = data[i].strip()
						name, value = line.split("=")
						value = value.strip("\"")
						if name == "enabled":
							if value == "true":
								lcars.plugins_loaded.append(plugin)
							else:
								lcars.plugins_disabled.append(plugin)
				i += 1
			f.close()
			return True
		except:
			lcars.trigger = "computer"
			lcars.response = "computer-beep-response.wav"
			lcars.disable_trigger = "false"
			lcars.run_in_background = "true"
			return False

def load_module(module_name):
	try:
		module = __import__(module_name)
		if not hasattr(module, "condition"):
			print("Error: '" + module_name + ".py' missing required method 'condition'")
			modules.remove(module)
		elif not hasattr(module, "do_action"):
			print("Error: '" + module_name + ".py' missing required method 'do_action'")
			modules.remove(module)
		print("Info: Loaded module " + module_name)
		return module
	except:
		print("Error: Failed to load " + module_name)
		return None

def load_modules():
	module_paths = []
	module_paths.append(os.environ['HOME'] + "/.lcars/modules/")

	for path in module_paths:
		os.system("rm " + path + "*.pyc > /dev/null 2>&1")
		sys.path.append(path)

	module_path = os.environ['HOME'] + "/.lcars/modules/"
	module_names = glob.glob(module_path + "*.py")
	module_names = [module_name.replace(module_path, "") for module_name in module_names]
	module_names = [module_name.replace(".py", "") for module_name in module_names]

	for module_name in module_names:
		if not module_name.startswith("lcars_"):
			module_names.remove(module_name)

	if "lcars_default" in module_names:
		module_names.remove("lcars_default")
		module_names.append("lcars_default")

	load_config()

	modules = []
	for module_name in module_names:
		try:
			module = load_module(module_name)
			if module:
				name = module_name.lstrip("lcars_")
				plugin = lcars_plugin(name, module)
				modules.append(plugin)
				if name not in lcars.plugins_loaded and name not in lcars.plugins_disabled:
					lcars.plugins_loaded.append(name)
		except:
			pass

	return modules

class SocketThread(Thread):
	def __init__(self, in_q, out_q):
		Thread.__init__(self)
		if os.path.exists(socket_file):
			os.remove(socket_file)
		self.in_q = in_q
		self.out_q = out_q
		self.sock = socket(AF_UNIX, SOCK_STREAM)
		self.sock.bind(socket_file)
		self.sock.settimeout(1)
		self.sock.listen(1)
		self.running = True

	def stop(self):
		self.running = False

	def run(self):
		self.running = True
		while self.running:
			try:
				self.conn = self.sock.accept()[0]
				print("Clearing queue")
				with self.out_q.mutex:
					self.out_q.queue.clear()
			except:
				sleep(0.1)
				continue
			try:
				self.msg = self.conn.recv(max_msg_size)
			except:
				self.conn.close()
				sleep(0.1)
				continue
			if not self.msg:
				print("[server]: msg is null")
				self.conn.close()
				sleep(0.1)
				continue
			print("[server]: Recieved message from client:", self.msg)

			self.out_q.put("[plugins_loaded]: ")
			for plugin in lcars.plugins_loaded:
				self.out_q.put(plugin)
			self.out_q.put(" :[plugins_loaded]")
			self.out_q.put("[plugins_disabled]: ")
			for plugin in lcars.plugins_disabled:
				self.out_q.put(plugin)
			self.out_q.put(" :[plugins_disabled]")

			while self.running:
				ready = select.select([self.conn,], [], [], 0.1)
				if ready[0]:
					try:
						self.msg = self.conn.recv(max_msg_size)
						if not self.msg:
							break
					except:
						break
					try:
						msgs = str(self.msg).split("\x1F")
						for msg in msgs:
							if not msg:
								continue
							print("[server]: Recieved message from client:", msg)
							if len(msg) > 11 and "[trigger]: " in msg:
								if len(msg[11:]):
									lcars.trigger = msg[11:]
									print("new trigger: " + lcars.trigger)
							if len(msg) > 12 and "[response]: " in msg:
								if len(msg[12:]):
									lcars.response = msg[11:]
									print("new response: " + lcars.response)
							if len(msg) > 19 and "[disable_trigger]: " in msg:
									lcars.disable_trigger = msg[19:]
									print("disable_trigger: " + lcars.disable_trigger)
							if len(msg) > 21 and "[run_in_background]: " in msg:
									lcars.run_in_background = msg[21:]
									print("run_in_background: " + lcars.run_in_background)
							if len(msg) > 10 and "[plugin]: " in msg:
								if len(msg[10:]):
									plugin, state = str(msg[10:]).split("=")
									print(plugin, state)
									if state == "enable":
										if plugin not in lcars.plugins_loaded:
											lcars.plugins_loaded.append(plugin)
										if plugin in lcars.plugins_disabled:
											lcars.plugins_disabled.remove(plugin)
									else:
										if plugin in lcars.plugins_loaded:
											lcars.plugins_loaded.remove(plugin)
										if plugin not in lcars.plugins_disabled:
											lcars.plugins_disabled.append(plugin)
					except:
						pass
				while not self.out_q.empty():
					data = str(self.out_q.get())
					print("[server]: From queue: " + data)
					try:
						self.conn.send(data + "\x1F")
						print("[server]: Data sent")
					except:
						self.conn.close()
						sleep(0.1)
						continue
				sleep(0.1)
			self.conn.close()
			sleep(0.1)
		print("Thread finished running")

class LCARS_Daemon(Daemon):
        def run(self):
		os.chdir(os.path.dirname(os.path.realpath(__file__)))
		modules = load_modules()
		self.run_thread = False
		in_q = Queue()
		out_q = Queue()
		self.socket_thread = SocketThread(in_q, out_q)
		self.socket_thread.start()

		os.chdir(self.pwd)
		r = sr.Recognizer()
		m = sr.Microphone()
		process_query = 0
		default_timeout = getdefaulttimeout()
		while True:
			with m as source:
				if process_query == 0:
					r.adjust_for_ambient_noise(source)
					print("Set minimum energy threshold to {}".format(r.energy_threshold))
				print("Listening...")
				setdefaulttimeout(10)
				audio = r.listen(source)
				if audio == -1:
					process_query = 0
					continue
				print("Processing...")
				try:
					# recognize speech using Google Speech Recognition
					setdefaulttimeout(default_timeout)
					value = r.recognize_google(audio)
		
					if str is bytes:
						result_string = u"{}".format(value).encode("utf-8")
					else:
						print("Requires python version 2")
					result_string = result_string.lower()
					action, space, target = result_string.partition(' ')
					words = result_string.split()
					print('"' + result_string + '"')
					out_q.put("[i]: " + result_string)
					if action and (action == "exit" or action == "quit"):
						self.socket_thread.stop()
						break
					if len(words) > 1 and words[0] == "thank" and words[1] == "you":
						reply = "You're welcome"
						lcars.reply_with(reply)
						out_q.put("[o]: " + reply)
						process_query = 0
						continue
					if lcars.disable_trigger == "true":
						print("lcars.disable_trigger == true")
						process_query = 1
					if len(words) < 2 and process_query == 0 and not action == lcars.trigger:
						continue
					if process_query == 1:
						process_query = 0
						for plugin in modules:
							name = plugin.name
							module = plugin.module
							if name not in lcars.plugins_loaded or name in lcars.plugins_disabled:
								continue
							ret, case = module.condition(lcars, result_string)
							if ret:
								out_q.put("[o]: " + module.do_action(lcars, result_string, case))
								break
					if result_string == lcars.trigger and lcars.disable_trigger == "false":
						#lcars.reply_with("Yes, how can I help you?")
						os.system("aplay " + lcars.response + " > /dev/null 2>&1")
						out_q.put("[o]: Yes, how can I help you?")
						process_query = 1
				except sr.UnknownValueError:
					print("Oops! Didn't understand")
				except sr.RequestError:
					print("Error: Couldn't request results from Google Speech Recognition service")
		os.system("rm " + socket_file + " > /dev/null 2>&1")

if __name__ == "__main__":
	process_name = sys.argv[0]
	proc_name = process_name.rsplit('/', 1)[1]
	process_name = proc_name.split(".")[0]
	daemon = LCARS_Daemon(proc_name, "/tmp/" + process_name + "-daemon.pid", "/dev/stdin", "/dev/stdout", "/dev/stderr")

	if len(sys.argv) == 2:
		if 'start' == sys.argv[1]:
			daemon.start()
		elif 'stop' == sys.argv[1]:
			daemon.stop()
		elif 'restart' == sys.argv[1]:
			daemon.restart()
		else:
			print "Unknown command"
			sys.exit(2)
		sys.exit(0)
	else:
		print "usage: %s start|stop|restart" % sys.argv[0]
		sys.exit(2)
