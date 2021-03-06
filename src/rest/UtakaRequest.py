#Copyright 2009 Humanitarian International Services Group
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

from mod_python import apache
from mod_python import util
from utaka.src.authentication.HMAC_SHA1_Authentication import getUser
import utaka.src.Config as Config
import utaka.src.exceptions.BadRequestException as BadRequestException


'''
UtakaRequest
wraps an apache request
adds:
	user
	key
	bucket
	subresources - dict of query string keys and vals
	customHeaderPrefix -
	customHeaderTable - dict of headers that began with the customHeaderPrefix, prefix has been stripped
'''
class UtakaRequest:

	def __init__(self, req, virtualBucket=False):

		self.req = req
		self.bucket = self.key = self.user = self.accesskey = self.signature = self.stringToSign = self.computedSig = None
		self.isUserAdmin = False
		self.subresources = {}
		self.__writeBuffer = ''
		self.virtualBucket = False

		#Query string digest
		if self.req.args:
			self.subresources = util.parse_qs(self.req.args, True)

		#URI digest
		basehost = Config.get('server', 'hostname')
		if self.req.hostname == basehost:
			uriDigestResults = self.uriDigest(req.uri)
			self.bucket = uriDigestResults.get('bucket')
			self.key = uriDigestResults.get('key')
		else:
			splitHost = self.req.hostname.split("." + basehost)
			if len(splitHost) == 2:
				uriDigestResults = self.uriDigest(splitHost[0] + '/' + req.uri)
				self.bucket = uriDigestResults.get('bucket')
				self.key = uriDigestResults.get('key')
				self.virtualBucket = True
			else:
				self.req.write("HOST: " + self.req.hostname + "\r\n")
				raise Exception, 'wrong hostname?'

		#custom header table
		self.customHeaderPrefix = Config.get('common', 'customHeaderPrefix').lower()
		self.customHeaderTable = {}
		for tag, val in self.req.headers_in.iteritems():
			if tag.lower().startswith(self.customHeaderPrefix):
				self.customHeaderTable[tag.lower()[len(self.customHeaderPrefix):]] = val

		#authenticate -- must happen after custom header table is created
		self.accesskey, self.signature = self.__getAccessKeyAndSignature()
		if self.accesskey:
			self.stringToSign = self.__buildStringToSign()
			self.user, self.isUserAdmin, self.computedSig = getUser(self.signature, self.accesskey, self.stringToSign)

		#Check date
		#check customDateHeader then date header

		if 'signature' in self.subresources:
			self.req.headers_out['Signature'] = str(self.computedSig)
			self.write(str(self.computedSig) + "\r\n")
			self.write(str(self.stringToSign) + "\r\n")
			self.send()

	def write(self, msg):
		self.__writeBuffer += msg

	def send(self):
		self.req.set_content_length(len(self.__writeBuffer))
		self.req.write(self.__writeBuffer)

	def uriDigest(self, uri):
		results = {}
		splitURI = uri.split('/', 2)
		for segment in splitURI[:]:
			if len(segment) == 0:
				splitURI.remove(segment)
		if len(splitURI) == 2:
			results['bucket'], results['key'] = splitURI[0], splitURI[1]
		elif len(splitURI) == 1:
			results['bucket'] = splitURI[0]
		return results

	def __buildStringToSign(self):
		nl = '\n'

		#http headers
		methodString = self.req.method
		contentMd5String = self.req.headers_in.get('content-md5', '')
		contentTypeString = self.req.headers_in.get('content-type', '')
		dateString = self.req.headers_in.get('date', '')

		#Canonicalize Custom Headers
		__customHeaderPrefix = Config.get('common', 'customHeaderPrefix').lower()
		__customDateHeader = __customHeaderPrefix + "-date"

		customHeaderList = []
		canCustomHeaders = ''

		for tag, val in self.customHeaderTable.iteritems():
			#self.req.write(tag + ":" + value + "\r\n")
			customHeaderList.append(self.customHeaderPrefix + tag + ":" + val.lstrip() + nl)
			if val == 'date':
					dateString = ''
		customHeaderList.sort()
		for val in customHeaderList:
			canCustomHeaders += val

		#Canoicalize URI
		import urllib
		uriString = ""
		if self.virtualBucket:
			uriString = "/" + urllib.quote(self.bucket)
		uriString += (self.req.unparsed_uri).split('?')[0]
		for val in ('location', 'acl', 'logging', 'torrent'):
			#self.write("CHECKING FOR ACL\r\n")
			if val in self.subresources:
				#self.write("FOUND ACL\r\n")
				uriString += '?' + val
		return (methodString + nl + contentMd5String + nl +
			contentTypeString + nl + dateString + nl + canCustomHeaders + uriString)


	def __getAccessKeyAndSignature(self):
		header = Config.get('authentication', 'header')
		prefix = Config.get('authentication', 'prefix') + ' '
		accesskey = signature = None
		try:
			authString = self.req.headers_in[header]
		except KeyError:
			pass
		else:
			splitAuth = authString.split(prefix)
			if len(splitAuth) == 2 and len(splitAuth[0]) == 0 and not splitAuth[1].startswith(' '):
				try:
					accesskey, signature = splitAuth[1].split(':')
				except ValueError:
					raise BadRequestException.InvalidArgumentAuthorizationException(argValue = authString)
			elif not len(splitAuth) == 2:
				raise BadRequestException.InvalidArgumentAuthorizationException(argValue = authString)
			else:
				raise BadRequestException.InvalidArgumentAuthorizationSpacingException(argValue = authString)
		return accesskey, signature

	def validateSubresources(self):
		if 'location' in self.subresources:
			for val in ('acl', 'logging', 'torrent'):
				if val in self.subresources:
					raise BadRequest.InvalidArgumentQueryStringConflictException(val, 'location')
		elif 'acl' in self.subresources:
			for val in('logging', 'torrent'):
				if val in self.subresources:
					raise BadRequest.InvalidArgumentQueryStringConflictException(val, 'acl')
		elif 'logging' in self.subresources:
			if 'torrent' in self.subresources:
				raise BadRequest.InvalidArgumentQueryStringConflictException('torrent', 'logging')