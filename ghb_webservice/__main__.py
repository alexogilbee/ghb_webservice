import os
import aiohttp

from aiohttp import web

from gidgethub import routing, sansio
from gidgethub import aiohttp as gh_aiohttp

from datetime import datetime

router = routing.Router()

routes = web.RouteTableDef()

eta = 60 # minutes also TEMP
fmt = '%Y-%m-%d %H:%M:%S'
tstamp1 = datetime.datetime.now()
tstamp2 = datetime.datetime.now()

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
    tstamp1 = datetime.datetime.now()
    tstamp1 = tstamp1.strftime(fmt)

    message = f"Thanks for the report @{author}! This should take around {eta} minutes to resolve! (I'm a bot)."
    await gh.post(url, data={'body': message})

@router.register("issues", action="closed")
async def issue_closed_event(event, gh, *args, **kwargs):
    """ When an issue is closed, comment and say how long it took to resolve """

    url = event.data["issue"]["comments_url"]
    author = event.data["issue"]["user"]["login"]

    # mark down end time
    tstamp2 = datetime.datetime.now()
    tstamp2 = tstamp2.strftime(fmt)
    td = tstamp2 - tstamp1
    td_mins = int(round(td.total_seconds() / 60))

    eta = (eta + td_mins) / 2

    message = f"Thanks @{author} for clsoing this issue! It took {td_mins} minutes to resolve! (I'm still a bot)."
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
