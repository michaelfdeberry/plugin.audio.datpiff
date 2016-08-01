import sys 
import xbmcgui
import xbmcplugin
import requests
import urllib
import re
from bs4 import BeautifulSoup
from urlparse import parse_qsl

_url = sys.argv[0]
_handle = int(sys.argv[1]) 
_default_icon = 'special://home/addons/plugin.audio.datpiff/icon.png'
_default_fanart = 'special://home/addons/plugin.audio.datpiff/fanart.jpg'
_media_url = 'special://home/addons/plugin.audio.datpiff/resources/media/'
_artist_url = 'http://www.datpiff.com/mixtapes-artist.php?filter=month&l='
_title_url = 'http://www.datpiff.com/mixtapes-title.php?filter=month&l='
_most_listens_url = 'http://www.datpiff.com/mixtapes-popular.php?filter=month&sort=listens&p='
_most_downloads_url = 'http://www.datpiff.com/mixtapes-popular.php?filter=month&sort=downloads&p='
_most_favorited_url = 'http://www.datpiff.com/mixtapes-popular.php?filter=month&sort=rating&p='
_highest_rating_url = 'http://www.datpiff.com/mixtapes-popular.php?filter=month&sort=favorites&p='
_newest_url = 'http://www.datpiff.com/mixtapes.php?filter=all&p='
_celebrated_url = 'http://www.datpiff.com/mixtapes/'
_hot_this_week_url = 'http://www.datpiff.com/mixtapes-hot.php'
_search_url = 'http://www.datpiff.com/mixtapes-search.php?criteria={SEARCH_CRITERIA}&sort=relevance&search=&search[]=title&search[]=artists&search[]=djs&p='

def get_page(url): 
    return BeautifulSoup(requests.get(url).text, 'html.parser')
	
def build_url(query):    
    return '{0}?{1}'.format(_url, urllib.urlencode(query))

def parse_duration(durationText):
	match = re.match(r'PT(.*?)M(.*?)S', durationText, re.I)	
	if match:
		minutes = int(match.group(1))
		seconds = int(match.group(2))
		return minutes * 60 + seconds
		
	return 0
	
def guess_mp3_url(directory, id, title, length):
	# can't find it just quit and return the title
	if length < 40:
		return title
	
	truncatedTitle = title[:length].replace(' ', '%20');
	url = 'http://hw-mp3.datpiff.com/mixtapes/{0}/{1}/{2}.mp3'.format(directory, id, truncatedTitle)	
	
	#Head doesn't work, so try to download the first 50 bytes of the mp3
	r = requests.get(url, headers = { 'Range': 'bytes=0-50' })
	if r.status_code >= 400:		
		return guess_mp3_url(directory, id, title, length - 1)
	
	return truncatedTitle
	
def parse_mp3_url(mixtape_id, mixtape_hash, track_number, track_title): 
	removedChars = ['-', '.', '\'', ',', '{', '}', '@', '$']
	directory = mixtape_id[0]
	id = re.match(r'.*?id=(.*?)&', mixtape_hash, re.I).group(1) 	
	track = '{0}'.format(track_number).rjust(2, '0')
	
	title = track_title
	for char in removedChars:
		title = title.replace(char, '')
		
	title = '{0} - {1}'.format(track, title)
	
	#The URL length is inconsistent, but the title part max seems to be bewteen 49 - 55 characters
	if len(title) > 49: 
		title = guess_mp3_url(directory, id, title, min(len(title) - 1, 56))
	
	title = title.replace(' ', '%20')

	return 'http://hw-mp3.datpiff.com/mixtapes/{0}/{1}/{2}.mp3'.format(directory, id, title)
	
def parse_tracks(url):
	tracks = []
	page = get_page(url)
	
	art = page.find(id = 'coverImage1')['src']
	artist = page.find(class_ = 'tapeDetails').find(class_ = 'artist').text.encode("ascii", "ignore")
	album = page.find(class_ = 'tapeDetails').find(class_ = 'title').text.encode("ascii", "ignore")
	playcount = int(page.find(class_ = 'tapeDetails').find(class_ = 'listens').text.replace(',', ''))	
	mixtape_id = page.find('meta', {'name': 'al:ios:url'})['content'].replace('datpiff://mixtape/', '')
	
	track_nodes = page.find(class_ = 'tracklist').find_all('li')	
	for node in track_nodes:
		track = { 'art': art, 'artist': artist, 'album': album, 'playcount': playcount }	
		track['title'] = node.find(class_ = 'trackTitle').text
		track['trackNumber'] = int(node.find(class_ = 'tracknumber').text.replace('.', ''))
		track['duration'] = parse_duration(node.find('meta', { 'itemprop': 'duration' })['content']) 
		track['url'] = parse_mp3_url(mixtape_id, node.find('meta', { 'itemprop': 'url' })['content'], track['trackNumber'], track['title'])				
		tracks.append(track)
	
	return tracks

def create_track_listings(params): 
	listings = []
	category = None
	for track in parse_tracks(params['url']):
		if category is None:
			category = '{0} - {1}'.format(track['artist'], track['album'])
			
		li = xbmcgui.ListItem(label = '{0} - {1}'.format(track['trackNumber'], track['title']))
		li.setArt({ 'thumb': track['art'], 'icon': track['art'] })
		li.setInfo('music', {
			'album': track['album'], 
			'artist': track['artist'],  
			'tracknumber': track['trackNumber'],
			'title': track['title'],
			'duration': track['duration'],
			'playcount': track['playcount'] 		
		})
		li.setProperty('IsPlayable', 'true')
		url = build_url({ 'action': 'play', 'url': track['url'] })
		listings.append((url, li, False))
	
	xbmcplugin.addDirectoryItems(_handle, listings, len(listings))
	xbmcplugin.endOfDirectory(_handle) 	
	xbmcplugin.setPluginCategory(_handle, category)
	
def parse_mixtapes(url):
	print "Scraping: " + url
	mixtapes = []
	page = get_page(url)	
	
	mixtape_nodes = page.find(id = 'leftColumnWide').find_all(class_ = 'contentItemInner')
	for node in mixtape_nodes:
		mixtape = {}
		mixtape['artist'] = node.find(class_ = 'artist').text.encode("ascii", "ignore")
		mixtape['title'] = node.find(class_ = 'title').text.encode("ascii", "ignore")
		mixtape['art'] = node.find(class_ = 'contentThumb').a.img['src']
		mixtape['url'] = 'http://www.datpiff.com{}'.format(node.find(class_ = 'title').a['href'])
		mixtapes.append(mixtape)		
		
	return mixtapes

def is_pageable(url):
	return url != _hot_this_week_url
	
def get_mixtape_url(url, page_number):
	if url == _hot_this_week_url:
		return url 
	elif url.startswith(_artist_url) or url.startswith(_title_url):
		return '{0}&p={1}'.format(url, page_number)
	else:
		return '{0}{1}'.format(url, page_number)
		
def create_mixtape_listings(params):
	xbmcplugin.setPluginCategory(_handle, params['category'])

	listings = []	
	page_number = int(params.get('page_number', '1'))	
	page_url = params['url']
	
	for mixtape in parse_mixtapes(get_mixtape_url(page_url, page_number)):
		li = xbmcgui.ListItem(label = '{0} - {1}'.format(mixtape['artist'], mixtape['title']))
		li.setArt({ 'thumb': mixtape['art'], 'icon': mixtape['art'], 'fanart': _default_fanart })
		li.setInfo('music', { 
			'album': mixtape['title'], 
			'artist': mixtape['artist']
		}) 
		url = build_url({ 'action': 'tracks', 'url': mixtape['url'] })
		listings.append((url, li, True))
	
	if(is_pageable(page_url)):
		li =  xbmcgui.ListItem(label = 'More...')
		url = build_url({'action': 'mixtapes', 'url': page_url, 'page_number': page_number + 1, 'category': params['category'] })
		listings.append((url, li, True))
	
	xbmcplugin.addDirectoryItems(_handle, listings, len(listings)) 
	xbmcplugin.endOfDirectory(_handle)
	
def create_alpha_listing(params):	
	alphabet = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'
	listings = []	
	type_url_base = _artist_url;
	
	if params['type'] == 'title':
		type_url_base = _title_url
	
	for i in xrange(0, 27): 
		char = alphabet[i]
		art = '{0}alpha_{1}.png'.format(_media_url, char)
		li = xbmcgui.ListItem(label = char)
		li.setArt({ 'thumb': art, 'icon': art, 'fanart': _default_fanart }) 
		mixtapes_url = '{0}{1}'.format(type_url_base, char)		
		url = build_url({ 'action': 'mixtapes', 'url': mixtapes_url, 'category': '{0} - {1}'.format(params['type'].title(), char) })		
		listings.append((url, li, True))
	
	xbmcplugin.setPluginCategory(_handle, params['category'])
	xbmcplugin.addDirectoryItems(_handle, listings, len(listings)) 
	xbmcplugin.endOfDirectory(_handle)
	
def search(params):
	kb = xbmc.Keyboard(heading = 'Search') 
	kb.doModal()
	
	if kb.isConfirmed() and kb.getText() != "":
		search_term = kb.getText()
		params['url'] = _search_url.replace('{SEARCH_CRITERIA}', urllib.quote_plus(search_term))
		params['category'] = 'Searching Results for {0}'.format(search_term)
		create_mixtape_listings(params)

def play_track(params):
	xbmcplugin.setResolvedUrl(_handle, True, listitem = xbmcgui.ListItem(path = params['url']))
	
def route(params):
	print 'Entering Router...'
	if params:
		if params['action'] == 'alpha':
			create_alpha_listing(params)
		if params['action'] == 'mixtapes':
			create_mixtape_listings(params)
		if params['action'] == 'tracks':
			create_track_listings(params)
		if params['action'] == 'search':
			search(params)
		if params['action'] == 'play':
			play_track(params)
	else:
		listings = []
		home = [
			{'title': 'Artist [#A-Z]', 'url': build_url({'action': 'alpha', 'type': 'artist', 'category': 'Artist [#A-Z]' })},
			{'title': 'Title [#A-Z]', 'url': build_url({'action': 'alpha', 'type': 'title', 'category': 'Title [#A-Z]' })},
			{'title': 'Most Listens', 'url': build_url({'action': 'mixtapes', 'url': _most_listens_url, 'category': 'Most Listens' })},
			{'title': 'Most Downloads', 'url': build_url({'action': 'mixtapes', 'url': _most_downloads_url, 'category': 'Most Downloads' })},
			{'title': 'Most Favorited', 'url':  build_url({'action': 'mixtapes', 'url': _most_favorited_url, 'category': 'Most Favorited' })},
			{'title': 'Highest Rating', 'url':  build_url({'action': 'mixtapes', 'url': _highest_rating_url, 'category': 'Highest Rating' })},
			{'title': 'Hot This Week', 'url':  build_url({'action': 'mixtapes', 'url': _hot_this_week_url, 'category': 'Hot This Week' })},
			{'title': 'Newest', 'url':  build_url({ 'action': 'mixtapes', 'url': _newest_url, 'category': 'Newest' })},
			{'title': 'Celebrated: 2x Platinum', 'url': build_url({ 'action': 'mixtapes', 'url': '{0}2xplatinum/'.format(_celebrated_url), 'category': 'Celebrated: 2x Platinum' })},
			{'title': 'Celebrated: Platinum', 'url': build_url({ 'action': 'mixtapes', 'url': '{0}platinum/'.format(_celebrated_url), 'category': 'Celebrated: Platinum' })},
			{'title': 'Celebrated: Gold', 'url': build_url({ 'action': 'mixtapes', 'url': '{0}gold/'.format(_celebrated_url), 'category': 'Celebrated: Gold' })},
			{'title': 'Celebrated: Silver', 'url': build_url({ 'action': 'mixtapes', 'url': '{0}sliver/'.format(_celebrated_url), 'category': 'Celebrated: Silver' })},
			{'title': 'Celebrated: Bronze', 'url': build_url({ 'action': 'mixtapes', 'url': '{0}bronze/'.format(_celebrated_url), 'category': 'Celebrated: Bronze' })},
			{'title': 'Search', 'url': build_url({ 'action': 'search' })}
		]
		
		for item in home:
			print 'Adding ListItem: ' + item['title'] 
			li = xbmcgui.ListItem(label = item['title'])
			li.setArt({ 'thumb': _default_icon, 'icon': _default_icon, 'fanart': _default_fanart }) 
			li.setInfo('music', { 'title': item['title'] })
			listings.append((item['url'], li, True))
			
		xbmcplugin.addDirectoryItems(_handle, listings, len(listings)) 
		xbmcplugin.endOfDirectory(_handle)

if __name__ == '__main__':
	route(dict(parse_qsl(sys.argv[2][1:])))