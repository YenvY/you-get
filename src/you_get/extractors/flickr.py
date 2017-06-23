#!/usr/bin/env python

__all__ = ['flickr_download_main']

from ..common import *

import json

pattern_url_photoset = r'https?://www\.flickr\.com/photos/.+/(?:(?:sets)|(?:albums))?/([^/]+)'
pattern_url_photostream = r'https?://www\.flickr\.com/photos/([^/]+)(?:/|(?:/page))?$'
pattern_url_single_photo = r'https?://www\.flickr\.com/photos/[^/]+/(\d+)'
pattern_url_gallery = r'https?://www\.flickr\.com/photos/[^/]+/galleries/(\d+)'
pattern_url_group = r'https?://www\.flickr\.com/groups/([^/]+)'
pattern_url_favorite = r'https?://www\.flickr\.com/photos/([^/]+)/favorites'

pattern_inline_title = r'<title>([^<]*)</title>'
pattern_inline_api_key = r'api\.site_key\s*=\s*"([^"]+)"'
pattern_inline_img_url = r'"url":"([^"]+)","key":"[^"]+"}}'
pattern_inline_NSID = r'"nsid"\s*:\s*"([^"]+)"'
pattern_inline_video_mark = r'("mediaType":"video")'

# (api_key, method, ext, page)
tmpl_api_call = (
    'https://api.flickr.com/services/rest?'
    '&format=json&nojsoncallback=1'
    # UNCOMMENT FOR TESTING
    #'&per_page=5'
    '&per_page=500'
    # this parameter CANNOT take control of 'flickr.galleries.getPhotos'
    # though the doc said it should.
    # it's always considered to be 500
    '&api_key=%s'
    '&method=flickr.%s'
    '&extras=url_sq,url_q,url_t,url_s,url_n,url_m,url_z,url_c,url_l,url_h,url_k,url_o,media'
    '%s&page=%d'
)

tmpl_api_call_video_info = (
    'https://api.flickr.com/services/rest?'
    '&format=json&nojsoncallback=1'
    '&method=flickr.video.getStreamInfo'
    '&api_key=%s'
    '&photo_id=%s'
    '&secret=%s'
)

tmpl_api_call_photo_info = (
    'https://api.flickr.com/services/rest?'
    '&format=json&nojsoncallback=1'
    '&method=flickr.photos.getInfo'
    '&api_key=%s'
    '&photo_id=%s'
)

# looks that flickr won't return urls for all sizes
# we required in 'extras field without a acceptable header
dummy_header = {
    'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0'
}
def get_content_headered(url):
    return get_content(url, dummy_header)

def get_photoset_id(url, page):
    return match1(url, pattern_url_photoset)

def get_photo_id(url, page):
    return match1(url, pattern_url_single_photo)

def get_gallery_id(url, page):
    return match1(url, pattern_url_gallery)

def get_api_key(page):
    match = match1(page, pattern_inline_api_key)
    # this happens only when the url points to a gallery page
    # that contains no inline api_key(and never makes xhr api calls)
    # in fact this might be a better approch for getting a temporary api key
    # since there's no place for a user to add custom infomation that may
    # misguide the regex in the homepage
    if not match:
        return match1(get_html('https://flickr.com'), r'"site_key"\s*:\s*"([^"]+)"')
    return match

def get_NSID(url, page):
    return match1(page, pattern_inline_NSID)

# [
# (
#   regex_match_url,
#   remote_api_method,
#   additional_query_parameter_for_method,
#   parser_for_additional_parameter,
#   field_where_photourls_are_saved
# )
# ]
url_patterns = [
    # www.flickr.com/photos/{username|NSID}/sets|albums/{album-id}
    (
        pattern_url_photoset,
        'photosets.getPhotos',
        'photoset_id',
        get_photoset_id,
        'photoset'
    ),
    # www.flickr.com/photos/{username|NSID}/{pageN}?
    (
        pattern_url_photostream,
        # according to flickr api documentation, this method needs to be
        # authenticated in order to filter photo visible to the calling user
        # but it seems works fine anonymously as well
        'people.getPhotos',
        'user_id',
        get_NSID,
        'photos'
    ),
    # www.flickr.com/photos/{username|NSID}/galleries/{gallery-id}
    (
        pattern_url_gallery,
        'galleries.getPhotos',
        'gallery_id',
        get_gallery_id,
        'photos'
    ),
    # www.flickr.com/groups/{groupname|groupNSID}/
    (
        pattern_url_group,
        'groups.pools.getPhotos',
        'group_id',
        get_NSID,
        'photos'
    ),
    # www.flickr.com/photos/{username|NSID}/favorites/*
    (
        pattern_url_favorite,
        'favorites.getList',
        'user_id',
        get_NSID,
        'photos'
    )
]

def download_urls_recorded(parsed, title, info_only, output_dir='.', 
    refer=None, merge=True, faker=False, headers={}, **kwargs):
    urls = parsed['urls']
    urls_ordered = parsed['urls_ordered']
    total = len(urls_ordered)
    now = 1
    for url in urls_ordered:
        basename = match1(url, r'/([^\./]+)\.[^/]+$')
        ext = match1(url, r'\.([^/]+)$')
        if urls[url] == 0:
            mime, ext, size = url_info(url)
            title_indexed = title + ('[%d/%d]' % (now, total))
            print_info('Flickr.com', title_indexed, mime, size)
            if not info_only:
                download_urls([url], basename, ext, False, output_dir, refer, merge, faker)
                urls[url] = 1
        else:
            print('skip finished download: %s.%s.' % (basename, ext))
        
        now = now + 1

def flickr_download_main(url, output_dir = '.', merge = False, info_only = False, **kwargs):
    size = 'o' # works for collections only
    title = None
    parsed = None

    if 'stream_id' in kwargs:
        size = kwargs['stream_id']
    
    list_path = os.path.join(output_dir, '$you-get-list.json')
    if os.path.exists(list_path):
        with open(list_path, 'r') as list_file:
            parsed = json.loads(list_file.read())
            title = parsed['title']
    else:     
        if match1(url, pattern_url_single_photo):
            url, title = get_single_photo_url(url)
            urls = [url]
        else:
            urls, title = fetch_photo_url_list(url, size)
        parsed = {'title':title, 'urls':{url:0 for url in urls}, 'urls_ordered':urls}
        with open(list_path, 'w') as list_file:
            list_file.write(json.dumps(parsed, separators=(',', ':')))
    try:
        download_urls_recorded(parsed, title, info_only, output_dir, None, False, True)
    except Exception as e:
        print(e)
    finally:        
        with open(list_path, 'w') as list_file:
            list_file.write(json.dumps(parsed, separators=(',', ':')))

def fetch_photo_url_list(url, size):
    for pattern in url_patterns:
        # FIXME: fix multiple matching since the match group is dropped
        if match1(url, pattern[0]):
            return fetch_photo_url_list_impl(url, size, *pattern[1:])
    raise NotImplementedError('Flickr extractor is not supported for %s.' % url)

def fetch_photo_url_list_impl(url, size, method, id_field, id_parse_func, collection_name):
    page = get_html(url)
    api_key = get_api_key(page)
    ext_field = ''
    if id_parse_func:
        ext_field = '&%s=%s' % (id_field, id_parse_func(url, page))
    page_number = 1
    urls = []
    while True:
        call_url = tmpl_api_call % (api_key, method, ext_field, page_number)
        photoset = json.loads(get_content_headered(call_url))[collection_name]
        pagen = photoset['page']
        pages = photoset['pages']
        for info in photoset['photo']:
            url = get_url_of_largest(info, api_key, size)
            urls.append(url)
        page_number = page_number + 1
        # the typeof 'page' and 'pages' may change in different methods
        if str(pagen) == str(pages):
            break
    return urls, match1(page, pattern_inline_title)

# image size suffixes used in inline json 'key' field
# listed in descending order
size_suffixes = ['o', 'k', 'h', 'l', 'c', 'z', 'm', 'n', 's', 't', 'q', 'sq']

def get_orig_video_source(api_key, pid, secret):
    parsed = json.loads(get_content_headered(tmpl_api_call_video_info % (api_key, pid, secret)))
    for stream in parsed['streams']['stream']:
        if stream['type'] == 'orig':
            return stream['_content'].replace('\\', '')
    return None

def get_url_of_largest(info, api_key, size):
    if info['media'] == 'photo':
        sizes = size_suffixes
        if size in sizes:
            sizes = sizes[sizes.index(size):]
        for suffix in sizes:
            if 'url_' + suffix in info:
                return info['url_' + suffix].replace('\\', '')
        return None
    else:
        return get_orig_video_source(api_key, info['id'], info['secret'])

def get_single_photo_url(url):
    page = get_html(url)
    pid = get_photo_id(url, page)
    title = match1(page, pattern_inline_title)
    if match1(page, pattern_inline_video_mark):
        api_key = get_api_key(page)
        reply = get_content(tmpl_api_call_photo_info % (api_key, get_photo_id(url, page)))
        secret = json.loads(reply)['photo']['secret']
        return get_orig_video_source(api_key, pid, secret), title
    #last match always has the best resolution
    match = match1(page, pattern_inline_img_url)
    return 'https:' + match.replace('\\', ''), title

site_info = "Flickr.com"
download = flickr_download_main
download_playlist = playlist_not_supported('flickr');
