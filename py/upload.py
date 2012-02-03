from optparse import OptionParser
parser = OptionParser(usage="usage: %prog [options] filename")
#parser.add_option("-r", "--raw",action="store_true", dest="raw",help="include raw JSON")
parser.add_option("-v", "--verbose", action="store_true", help="verbose")
parser.add_option("-r", "--relogin", action="store_true", help="force relogin")
parser.add_option("-f", "--authfile", action="store", type="string", dest="authfile",
					help="authentication credentials file", default=".AUTH")

(options, args) = parser.parse_args()

if len(args) < 1:
	parser.print_help()
	exit()

SID = ''
try:
	SID = open(options.authfile, "r").read()
except:
	pass

import urllib

if SID == '' or options.relogin:
	import getpass
	email = raw_input("Enter Google Music Email Address: ")
	pwd = getpass.getpass("Enter Google Music Password: ")
	payload = {
		'Email': email,
		'Passwd': pwd,
		'service': 'sj',
		'accountType': 'GOOGLE'
	}
	r = urllib.urlopen("https://google.com/accounts/ClientLogin", 
						urllib.urlencode(payload)).read()
	SID = r.split("\n")[0]
	print "Logged In Successfully"
	open(options.authfile, "w").write(SID)


import httplib
android = httplib.HTTPSConnection("android.clients.google.com")

def protopost(path, proto):
	global SID, android
	android.request("POST", "/upsj/"+path, proto.SerializeToString(), {
		"Cookie": SID,
		"Content-Type": "application/x-google-protobuf"
	})
	r = android.getresponse()
	print "Response from", path, "Status", r.status, r.reason
	return r.read()


from uuid import getnode as getmac
mac = hex(getmac())[2:-1]
mac = ':'.join([mac[x:x+2] for x in range(0, 10, 2)])

from socket import gethostname
hostname = gethostname()

if options.verbose: print mac, hostname

import metadata_pb2


uauth = metadata_pb2.UploadAuth()
uauth.address = mac
uauth.hostname = hostname

#print uauth.SerializeToString()

uauthresp = metadata_pb2.UploadAuthResponse()
uauthresp.ParseFromString(protopost("upauth", uauth))
if options.verbose: print uauthresp

clientstate = metadata_pb2.ClientState()
clientstate.address = mac

#print uauth.SerializeToString()

clientstateresp = metadata_pb2.ClientStateResponse()
clientstateresp.ParseFromString(protopost("clientstate", clientstate))
print clientstateresp.quota

metadata = metadata_pb2.MetadataRequest()
metadata.address = mac

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import random
import string
import os

filemap = {} #this maps a generated ClientID with a filename

for filename in args:
	track = metadata.tracks.add()

	audio = MP3(filename, ID3 = EasyID3)

	chars = string.ascii_letters + string.digits 
	id = ''.join(random.choice(chars) for i in range(20))
	filemap[id] = filename
	track.id = id

	filesize = os.path.getsize(filename)

	track.fileSize = filesize

	track.bitrate = audio.info.bitrate / 1000
	track.duration = int(audio.info.length * 1000)
	if "album" in audio: track.album = audio["album"][0]

	if "title" in audio: track.title = audio["title"][0]
	if "artist" in audio: track.artist = audio["artist"][0]
	if "composer" in audio: track.composer = audio["composer"][0]
	#if "albumartistsort" in audio: track.albumArtist = audio["albumartistsort"][0]
	if "genre" in audio: track.genre = audio["genre"][0]
	if "date" in audio: track.year = int(audio["date"][0])
	if "bpm" in audio: track.beatsPerMinute = int(audio["bpm"][0])
	#if "tracknumber" in audio: track.track = int(audio["tracknumber"][0])
	#if "discnumber" in audio: track.disc = int(audio["discnumber"][0])


metadataresp = metadata_pb2.MetadataResponse()
metadataresp.ParseFromString(protopost("metadata?version=1", metadata))
#print utfencode(metadataresp)
if options.verbose: print metadataresp

import time
import json
jumper = httplib.HTTPConnection('uploadsj.clients.google.com')

for song in metadataresp.response.uploads:
	filename = filemap[song.id]
	audio = MP3(filename, ID3 = EasyID3)
	print filename
	if options.verbose: print song
	payload = {
	  "clientId": "Jumper Uploader",
	  "createSessionRequest": {
	    "fields": [
	      {
	        "inlined": {
	          "content": "jumper-uploader-title-42",
	          "contentType": "text/plain",
	          "name": "title"
	        }
	      },
	      {
	        "external": {
	          "filename": filename,
	          "name": os.path.abspath(filename),
	          "put": {},
	          "size": os.path.getsize(filename)
	        }
	      },
	      {
	        "inlined": {
	          "content": song.id,
	          "name": "ClientId"
	        }
	      },
	      {
	        "inlined": {
	          "content": str(len(args)),
	          "name": "ClientTotalSongCount"
	        }
	      },
	      {
	        "inlined": {
	          "content": "0",
	          "name": "CurrentTotalUploadedCount"
	        }
	      },
	      {
	        "inlined": {
	          "content": audio["title"][0],
	          "name": "CurrentUploadingTrack"
	        }
	      },
	      {
	        "inlined": {
	          "content": song.serverId,
	          "name": "ServerId"
	        }
	      },
	      {
	        "inlined": {
	          "content": "true",
	          "name": "SyncNow"
	        }
	      },
	      {
	        "inlined": {
	          "content": str(audio.info.bitrate),
	          "name": "TrackBitRate"
	        }
	      },
	      {
	        "inlined": {
	          "content": "false",
	          "name": "TrackDoNotRematch"
	        }
	      },
	      {
	        "inlined": {
	          "content": mac,
	          "name": "UploaderId"
	        }
	      }
	    ]
	  },
	  "protocolVersion": "0.8"
	}
	while True:
		print "Trying to begin upload"
		jumper.request("POST", "/uploadsj/rupio", json.dumps(payload), {
			"Content-Type": "application/x-www-form-urlencoded", #wtf? shouldn't it be json? but that's what the google client sends
			"Cookie": SID
		})
		r = json.loads(jumper.getresponse().read())
		if options.verbose: print r
		if 'sessionStatus' in r: break
		time.sleep(3)
	up = r['sessionStatus']['externalFieldTransfers'][0]
	print "Uploading a file... this may take a while"
	jumper.request("POST", up['putInfo']['url'], open(filename), {
		'Content-Type': up['content_type']
	})
	r = json.loads(jumper.getresponse().read())
	if options.verbose: print r
	if r['sessionStatus']['state'] == 'FINALIZED':
		print "Uploaded File Successfully"
