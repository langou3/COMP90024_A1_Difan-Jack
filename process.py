import json
import re
import pandas as pd
from mpi4py import MPI
from datetime import datetime
from collections import Counter
from collections import defaultdict
import os

def merge(dict1, dict2):
    ''' Function for merging the dictionary with the structure like dict(Counter).
    :param dict1:
    :param dict2:
    :return dict3:
    '''
    dict3 = defaultdict(lambda: defaultdict(int))
    for d in (dict1, dict2):
        for key, value in d.items():
            for subkey, subvalue in value.items():
                dict3[key][subkey] += subvalue
    return dict3

def from_gcc(gcc):
    ''' Check whether the current 'gcc' is a greater capital city.
    :param gcc:
    :return boolean:
    '''
    if gcc[1] == 'g'or gcc[1] == 'a'or gcc[1] == 'o':
        return True
    return False

def find_gcc(place_split):
    ''' Function for find the gcc of the tweet's place information corresponding to the gcc in sal.json.
    :param place_split:
    :return gcc:
    '''
    gcc = None
    if len(place_split) < 2:
        gcc = None
    else:
        if place_split[0] in sal_data.keys():
            gcc = sal_data[place_split[0]]['gcc']
        else:
            # Situation for the same suburb name in different states.
            if place_split[1] in state_code.keys():
                # Change it into sal.json format. (e.g. abbotsford, New South Wales  ------>  abbotsford (nsw) )
                place_split[0] = place_split[0]+ ' ' + state_code[place_split[1]]
            if place_split[0] in sal_data.keys():
                gcc = sal_data[place_split[0]]['gcc']
    return gcc

def process(data):
    """ Function for processing the data.
    num_tweets records the number of tweets in each gcc.
    most_tweets records the number of tweets which the author has made. (Including the tweets in rural region)
    tweeter records the tweets that each author has made in gcc.
    :param data:
    :return num_tweets,most_tweets,tweeter:
    """
    num_tweets = Counter()
    most_tweets = Counter()
    tweeter = defaultdict(Counter)
    for element in data:
        author_id, place = element
        # Finding the number of tweets in each capital city
        place_split = re.split('[,-]+', place)
        place_split[0] = place_split[0].lower()
        gcc = find_gcc(place_split)
        if gcc != None and from_gcc(gcc):
            num_tweets[gcc] += 1
            tweeter[author_id][gcc] += 1
        most_tweets[author_id] += 1
    return num_tweets,most_tweets,tweeter

def num_location(tweeter):
    """
    Change the output format. (e.g. 1gsyd ---> #gysd)
    :param tweeter:
    :return sorted_location[:-1]:
    """
    sorted_location = ''
    # sorted_tweeter = dict(sorted(tweeter.items(), key=lambda x:x[1],reverse=True))
    for state in tweeter.keys():
        gcc = state[1:]
        num = str(tweeter.get(state))
        sorted_location = sorted_location + num + gcc + ","
    return sorted_location[:-1]

def readInChunks(file_per_core, chunkSize = 1024) :
    """
    Break the file into chunks, avoiding out of memory. Assuming the default chunk size is 1024.
    :param file_per_core:
    :param chunkSize:
    :return:
    """
    start, end = file_per_core
    chunks = []
    with open(TWITTERPATH, 'rb') as f:
        f.seek(start)

        # Set the pointer.
        end_pointer = f.tell()

        # Read the file in chunk, until the end.
        while end_pointer < end:
            start_pointer = end_pointer
            f.seek(start_pointer + chunkSize)
            line = f.readline()

            # According to the json format, check whether current line is the end of one tweet.
            # If not, continue reading the file, until read one tweet in complete.
            end_of_twit = line.startswith(b'  }')
            while not end_of_twit:
                line = f.readline()
                end_of_twit = line.startswith(b'  }')
                end_pointer = f.tell()
                if end_pointer > end:
                    end_pointer = end
                    break
            chunks.append((start_pointer,end_pointer))
            end_pointer = end_pointer + 1
    return chunks

def readFile(file_per_core):
    """Read the file in chunks.
    :param file_per_core:
    :return file:
    """
    file = []
    with open(TWITTERPATH, 'rb') as f:
        for chunkStart, chunkEnd in readInChunks(file_per_core):
            try :
                f.seek(chunkStart)
                step = chunkEnd - chunkStart
                line = f.read(step).decode('utf-8').strip()

                #Take ',' out, turn the line into json format.
                if line[-1] == ",":
                    line = line[:-1]
                line = "[" + line + "]"
                #Load and read the line.
                data = json.loads(line)
                for d in data:
                    author_id = d['data']['author_id']
                    place = d["includes"]["places"][0]["full_name"]
                    file.append([author_id, place])
            except :
                continue
    return file

def split_file(file_size_processor,file_size_total):
    """ Spit the whole file into small pieces for parallel.
    :param file_size_processor:
    :param file_size_total:
    :return split_list:
    """
    with open(TWITTERPATH, 'rb') as f:
        end_pointer = f.tell()
        split_list = []
        # According to the json foramt, take the first and last character out of the file, which are the two brackets [.....].
        while end_pointer < file_size_total -1:
            start_pointer = end_pointer
            f.seek(start_pointer + file_size_processor)
            line = f.readline()

            # According to the json format, check whether current line is the end of one tweet.
            # If not, continue reading the file, until read one tweet in complete.
            end_of_twit = line.startswith(b'  }')
            while not end_of_twit :
                line = f.readline()
                end_of_twit = line.startswith(b'  }')
                end_pointer = f.tell()
                if end_pointer > file_size_total - 1 :
                    end_pointer = file_size_total -1
                    break
            split_list.append((start_pointer,end_pointer))
    return split_list

TWITTERPATH = 'bigTwitter.json'
SALPATH = 'sal.json'

f_sal = open(SALPATH, 'r')
sal_json = f_sal.read()
sal_data = json.loads(sal_json)

START_TIME = datetime.now()
END_TIME = None

COMM = MPI.COMM_WORLD
RANK = COMM.Get_rank()
SIZE = COMM.Get_size()

state_code = {" New South Wales":"(nsw)", " Victoria":"(vic.)", " Queensland":"(qld)", " South Australia":"(sa)", " Western Australia":"(wa)", " Tasmania":"(tas.)", " Northern Territory":"(nt)", " Australian Capital Territory":"(act)"}
full_name = {"1gsyd" : "Greater Sydney", "2gmel": "Greater Melbourne", "3gbri": "Greater Bribane", "4gade": "Greater Adelade", "5gper": "Greater Perth", "6ghob": "Greater Hobart", "7gdar": "Greater Darwin", "8acte": "Australian Capital Territory", "9oter" : "Other Territories"}

# print("Current Node is ", RANK)
if RANK == 0:
    file_size_total = os.path.getsize(TWITTERPATH)
    file_size_processor = file_size_total // SIZE
    splitFile = split_file(file_size_processor, file_size_total)
    # END_TIME = datetime.now()
    # print("Time for splitting file is", END_TIME - START_TIME)
else:
    splitFile = None
COMM.Barrier()

file_per_core = COMM.scatter(splitFile, root=0)
data_per_core = readFile(file_per_core)
# END_TIME = datetime.now()
# print("Time for reading file on", RANK, "is ", datetime.now()-END_TIME)

num_tweets_result ,most_tweets_result ,tweeter_result  = process(data_per_core)

num_tweets_results = COMM.gather(num_tweets_result , root=0)
most_tweets_results = COMM.gather(most_tweets_result , root=0)
tweeter_results = COMM.gather(tweeter_result , root=0)
COMM.Barrier()


if RANK == 0:
    # print("Time for processing file on", RANK, "is ", datetime.now() - END_TIME)
    # END_TIME = datetime.now()
    num_tweets = Counter()
    most_tweets = Counter()
    tweeter = defaultdict(Counter)

    # Merging the processed results from cores together.
    for n in range(SIZE):
        num_tweets += num_tweets_results[n]
        most_tweets += most_tweets_results[n]
        tweeter = merge(tweeter,tweeter_results[n])
    # print("Time time for merging is: " + str(datetime.now() - END_TIME))
    # END_TIME = datetime.now()

    # Converting the tweet location dictionary into a pandas dataframe
    top_tweet_loc = pd.DataFrame(num_tweets.items())
    top_tweet_loc = top_tweet_loc.rename({0: 'Greater Capital City', 1: 'Number of Tweets Made'}, axis=1)
    top_tweet_loc['Greater Capital City'] = top_tweet_loc['Greater Capital City'].apply(lambda row: row + "(" + full_name[row] + ')')
    top_tweet_loc = top_tweet_loc.sort_values(by='Number of Tweets Made', ascending=False)
    top_tweet_loc.index = top_tweet_loc.index + 1
    print(top_tweet_loc)

    print("==============================================")
    # Converting the tweet id dictionary into a pandas dataframe
    top_tweeters = pd.DataFrame(most_tweets.items())
    top_tweeters = top_tweeters.rename({0: 'Author Id', 1: 'Number of Tweets Made'}, axis=1)
    top_tweeters = top_tweeters.sort_values(by='Number of Tweets Made', ascending=False)
    top_tweeters = top_tweeters.head(10).reset_index(drop = True)
    top_tweeters.insert(0, "Rank", ["#" + str(i+1) for i in list(range(10))], True)
    print(top_tweeters)

    print("==============================================")
    # Converting the tweeter dictionary into a pandas dataframe
    top_tweeter_loc = pd.DataFrame(tweeter.items())
    top_tweeter_loc = top_tweeter_loc.rename({0: 'Author Id', 1: 'Tweets Location'}, axis=1)

    top_tweeter_loc['Sum of Unique City'] = top_tweeter_loc['Tweets Location'].apply(lambda row: len(row) )
    top_tweeter_loc['Sum of Total Tweets'] = top_tweeter_loc['Tweets Location'].apply(lambda row: sum(row.values()))
    top_tweeter_loc['Sorted location'] = top_tweeter_loc['Tweets Location'].apply(num_location)
    top_tweeter_loc = top_tweeter_loc.sort_values(by=['Sum of Unique City','Sum of Total Tweets'] , ascending=False)

    top_tweeter_loc['Number of Unique City Locations and #Tweets'] = top_tweeter_loc.apply(lambda row: f"{row['Sum of Unique City']}(#{row['Sum of Total Tweets']}tweets-{row['Sorted location']})", axis=1)
    top_tweeter_loc = top_tweeter_loc.drop(['Sum of Unique City','Sum of Total Tweets', 'Tweets Location', 'Sorted location'], axis=1)
    top_tweeter_loc = top_tweeter_loc.head(10).reset_index(drop = True)
    top_tweeter_loc.insert(0, "Rank", ["#" + str(i+1) for i in list(range(10))], True)

    print(top_tweeter_loc)

    # print("Time time for printing is: " + str(datetime.now() - END_TIME))
    END_TIME = datetime.now()
    print("Total running time is: " + (END_TIME - START_TIME))
MPI.Finalize

