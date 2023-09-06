# Import the modules
import os
import sys
import json
import threading
import queue
import googleapiclient.discovery
import googleapiclient.errors
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import WebVTTFormatter

playlist_id = "PLlrxD0HtieHi0mwteKBOfEeOYf0LJU4O1"
OUTPUT_FOLDER = './the_ai_show_transcripts/'
max_results = 50

# Initialize the Google developer API client
GOOGLE_DEVELOPER_API_KEY = os.environ['GOOGLE_DEVELOPER_API_KEY']
api_service_name = "youtube"
api_version = "v3"

formatter = WebVTTFormatter()
videos = []
q = queue.Queue()


class Counter:
    '''thread safe counter'''

    def __init__(self):
        '''initialize the counter'''
        self.value = 0
        self.lock = threading.Lock()

    def increment(self):
        '''increment the counter'''
        with self.lock:
            self.value += 1


counter = Counter()


def print_to_stderr(*a):
    '''print to stderr'''
    # Here a is the array holding the objects
    # passed as the argument of the function
    print(*a, file=sys.stderr)


def gen_metadata(playlist_item):
    '''Generate metadata for a video'''

    videoId = playlist_item['snippet']['resourceId']['videoId']

    filename = os.path.join(OUTPUT_FOLDER, videoId + '.json')
    metadata = {}
    metadata['speaker'] = ''
    metadata['title'] = playlist_item['snippet']['title']
    metadata['videoId'] = playlist_item['snippet']['resourceId']['videoId']
    metadata['description'] = playlist_item['snippet']['description']

    # save the metadata as a .json file
    json.dump(metadata, open(filename, 'w', encoding='utf-8'))


def get_transcript(playlist_item, counter_id):
    '''Get the transcript for a video'''

    video_id = playlist_item['snippet']['resourceId']['videoId']
    filename = os.path.join(OUTPUT_FOLDER, video_id + '.vtt')

    # if video transcript already exists, skip it
    if os.path.exists(filename):
        print_to_stderr(f"skipping video {counter_id}, {video_id}")
        return False

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        print_to_stderr(f"Transcription download completed: {counter_id}, {video_id}")
    except Exception:
        print_to_stderr("Transcription not found for video: " + video_id)
        return False

    # save the transcript as a .vtt file
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(formatter.format_transcript(transcript))

    return True


def process_queue():
    '''process the queue'''
    while not q.empty():
        video = q.get()

        counter.increment()
        # print_to_stderr(f"Processed {counter.value} videos")

        if get_transcript(video, counter.value):
            gen_metadata(video)

        q.task_done()


print_to_stderr("Starting transcript download")

youtube = googleapiclient.discovery.build(
    api_service_name, api_version, developerKey=GOOGLE_DEVELOPER_API_KEY)

# Create a request object with the playlist ID and the max results
request = youtube.playlistItems().list(
    part="snippet",
    playlistId=playlist_id,
    maxResults=max_results
)

# Loop through the pages of results until there is no next page token
while request is not None:
    # Execute the request and get the response
    response = request.execute()

    # Iterate over the items in the response and append the video IDs to the list
    for item in response["items"]:
        q.put(item)

    # Get the next page token from the response and create a new request object
    next_page_token = response.get("nextPageToken")
    if next_page_token is not None:
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=max_results,
            pageToken=next_page_token
        )
    else:
        request = None

print_to_stderr("Total videos to be processed: ", q.qsize())

# create multiple threads to process the queue
threads = []
for i in range(30):
    t = threading.Thread(target=process_queue)
    t.start()
    threads.append(t)

# wait for all threads to finish
for t in threads:
    t.join()

print_to_stderr("Finished processing all videos")

# for video in videos:
#     if get_transcript(video):
#         gen_metadata(video)