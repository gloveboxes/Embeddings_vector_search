''' Summarize a youtube transcript using chatgpt'''

import random
import sys
import os
import queue
import csv
import threading
import time
import openai

API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
RESOURCE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

openai.api_type = "azure"
openai.api_key = API_KEY
openai.api_base = RESOURCE_ENDPOINT
openai.api_version = "2023-07-01-preview"


segments = []
output_segments = []

csv_fieldnames = ['videoId', 'title',
                  'description', 'speaker', 'start', 'text', 'summary']

# create a thread safe counter


class Counter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.value += 1


counter = Counter()


def chatgpt_summary(text):
    '''generate a summary using chatgpt'''
    # create a retry time of 10 seconds with some added jitter
    # https://learn.microsoft.com/en-us/answers/questions/1282041/rate-limits-in-azure-openai-service-how-does-it-wo
    request_retry_time = 5 + random.randint(0, 5)

    result = ""
    try:

        messages = [{"role": "system", "content": "You're an AI Assistant, write a 100 word summary of the transcript suitable for experts."},
                    {"role": "user", "content": text}]

        response = openai.ChatCompletion.create(
            engine="glovebox-chat",
            messages=messages,
            temperature=0.4,
            max_tokens=2048,
            top_p=0.0,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None)

        # check that the context key exists
        if 'choices' in response:
            # check that the context key exists
            if len(response.choices) > 0:
                # check that the context key exists
                if 'message' in response.choices[0]:
                    # check that the context key exists
                    if 'content' in response.choices[0]['message']:
                        result = response.choices[0]['message']['content']
                    else:
                        print("No content key in response")
                        return text

    except openai.error.InvalidRequestError as invalid_request_exception:
        print(f"Invalid request: {invalid_request_exception}")
        print("Error with segment: ", text)
        # just return the original text
        return text

    # https://callmefred.com/how-to-fix-openai-error-ratelimiterror-the-server-had-an-error/
    # https://platform.openai.com/docs/guides/error-codes/handling-errors

    except openai.error.RateLimitError:
        # retry_time = rate_limit_exception.retry_after if hasattr(
        #     rate_limit_exception, 'retry_after') else 20
        print(
            f"Rate limit exceeded. Retrying in {request_retry_time} seconds...")
        time.sleep(request_retry_time)
        return chatgpt_summary(text)

    except openai.error.APIError:
        # retry_time = api_error_exception.retry_after if hasattr(
        #     api_error_exception, 'retry_after') else 20
        print(
            f"API error occurred. Retrying in {request_retry_time} seconds...")
        time.sleep(request_retry_time)
        return chatgpt_summary(text)

    except openai.error.ServiceUnavailableError:
        print(
            f"Service is unavailable. Retrying in {request_retry_time} seconds...")
        time.sleep(request_retry_time)
        return chatgpt_summary(text)

    except openai.error.Timeout as timeout_exception:
        print(
            f"Request timed out: {timeout_exception}. Retrying in {request_retry_time} seconds...")
        time.sleep(request_retry_time)
        return chatgpt_summary(text)

    except openai.error.OpenAIError as openai_error_exception:
        print(
            f"OpenAI error occurred: {openai_error_exception}. Retrying in {request_retry_time} seconds...")
        time.sleep(request_retry_time)
        return chatgpt_summary(text)

    except Exception as general_exception:
        print(general_exception)
        print("Error with chunk: ", text)
        return text

    return result


def process_queue():
    '''process the queue'''
    while not q.empty():
        segment = q.get()
        # get a summary of the text using chatgpt
        summary = chatgpt_summary(segment['text'])

        counter.increment()
        print(f"Processed {counter.value} segments")

        # add the summary to the segment dictionary
        segment['summary'] = summary
        
        output_segments.append(segment.copy())
        q.task_done()


reader = csv.DictReader(
    sys.stdin, fieldnames=csv_fieldnames, skipinitialspace=True)
next(reader)  # skip header row
segments = list(reader)

print("Total segments to be processed: ", len(segments))

# add segment list to a queue
q = queue.Queue()
for segment in segments:
    q.put(segment)

# create multiple threads to process the queue
threads = []
for i in range(7):
    t = threading.Thread(target=process_queue)
    t.start()
    threads.append(t)

# wait for all threads to finish
for t in threads:
    t.join()

# write the sessions to a csv file
with open('./output/master_summarized.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
    writer.writeheader()
    for segment in output_segments:
        writer.writerow(segment)