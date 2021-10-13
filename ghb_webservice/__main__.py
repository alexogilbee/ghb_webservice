import os
import aiohttp

from aiohttp import web

from gidgethub import routing, sansio
from gidgethub import aiohttp as gh_aiohttp

from datetime import datetime as dt

from pymongo import MongoClient
from pprint import pprint

url = os.environ.get("MDB_URL")

client = MongoClient(url)
db = client.issueBot

router = routing.Router()

routes = web.RouteTableDef()

eta = 60 # minutes also TEMP
fmt = '%Y-%m-%d %H:%M:%S'
tstamp1 = dt.now()
tstamp2 = dt.now()

# issue opened event
# need to add estimated time, prob stored in DB?
# also need an issue closed event, to record the time taken to resolve the issue
# can use this ^ to also comment on the issue, stating how long it took for the issue to be resolved
# still dunno if we wanna incorporate tags in this or not (i've never used them tbh)
@router.register("issues", action="opened")
async def issue_opened_event(event, gh, *args, **kwargs):
    """ Whenever an issue is opened, greet the author and say thanks."""
    
    url = event.data["issue"]["comments_url"]
    author = event.data["issue"]["user"]["login"]

    # mark down start time
    global tstamp1
    tstamp1 = dt.now()
    #tstamp1 = tstamp1.strftime(fmt)
    
    # insert issue into database
    issue = {
        'repo_name' : event.data["repository"]["full_name"], # subject to change
        'repo_id' : event.data["repository"]["id"],
        'issue_number' : event.data["issue"]["number"],
        'issue_id' : event.data["issue"]["id"],
        'title' : event.data["issue"]["title"],
        'user' : author,
        'start_time' : event.data["issue"]["created_at"],
        'python_start' : tstamp1
    }
    result = db.reviews.insert_one(issue)

    # determine ETA from DB
    eta_list = db.reviews.find({'duration': {'$gt': 0}})
    eta_count = db.reviews.find({'duration': {'$gt': 0}}).count()
    eta_sum = 0
    for dura in eta_list:
        eta_sum += dura['duration']
    if eta_sum > 0:
        eta = int(eta_sum / eta_count)

    message = f"Thanks for the report @{author}! This should take around {eta} minutes to resolve! (I'm a bot)."
    await gh.post(url, data={'body': message})

@router.register("issues", action="closed")
async def issue_closed_event(event, gh, *args, **kwargs):
    """ When an issue is closed, comment and say how long it took to resolve """

    url = event.data["issue"]["comments_url"]
    author = event.data["issue"]["user"]["login"]

    # mark down end time
    global tstamp1
    global tstamp2
    tstamp2 = dt.now()
    #tstamp2 = tstamp2.strftime(fmt)

    # update DB entry
    issue_id = event.data["issue"]["id"]
    old_data = db.reviews.find_one({'issue_id': issue_id})

    td = tstamp2 - old_data.get('python_start')
    td_mins = int(round(td.total_seconds() / 60))

    result = db.reviews.update_one({'issue_id' : issue_id}, {'$set': {'end_time': event.data["issue"]["closed_at"], 'python_end': tstamp2, 'duration': td_mins}})

    time_str = ""
    num_days = 0
    num_hours = 0
    if td_mins >= 1440: # 1 day in minutes
        num_days = int(td_mins / 1440)
        time_str = time_str + str(num_days) + " day"
        if num_days > 1: # 2 days for plural
            time_str = time_str + "s"
        time_str = time_str + ", "
    if td_mins >= 60: # 1 hour
        num_hours = int((td_mins - (num_days * 1440)) / 60) # subtract whole days, left with remainder hours
        time_str = time_str + str(num_hours) + " hour"
        if num_hours > 1:
            time_str = time_str + "s"
        time_str = time_str + ", "
    num_mins = int(td_mins - (num_days * 1440) - (num_hours * 60))
    time_str = time_str + str(num_mins) + " minute"
    if num_mins > 1:
        time_str = time_str + "s"

    message = f"Thanks @{author} for clsoing this issue! It took {time_str} to resolve! (I'm still a bot)."
    await gh.post(url, data={'body': message})

@routes.post("/")
async def main(request):
    # read the GitHub webhook payload
    body = await request.read()

    # our authentication token and secret
    secret = os.environ.get("GH_SECRET")
    oauth_token = os.environ.get("GH_AUTH")

    # a representation of GitHub webhook event
    event = sansio.Event.from_http(request.headers, body, secret=secret)

    # instead of mariatta, use your own username
    async with aiohttp.ClientSession() as session:
        gh = gh_aiohttp.GitHubAPI(session, "alexogilbee",
                                  oauth_token=oauth_token)

        # call the appropriate callback for the event
        await router.dispatch(event, gh)

    # return a "Success"
    return web.Response(status=200)


if __name__ == "__main__":
    app = web.Application()
    app.add_routes(routes)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)

    web.run_app(app, port=port)

