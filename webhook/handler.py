# This function provides all the webhook functionality. It takes the data from
# the POST from Github, parses it to find an event we care about and if it's
# valid, pushes a message to the SNS topic. If the topic does not exist, the
# Lambda creates it.
#

import json

def webhook(event, context):

    # All the data we need is provided inside the event object.

    if event['headers']['X-GitHub-Event']:
        # Post is a github event. We only care about certain types of these.

        if event['headers']['X-GitHub-Event'] == 'ping':
            body = '{"status": "success", "message": "Ping OK"}'
            statuscode = 200
        elif event['headers']['X-GitHub-Event'] == 'push':
            # Github gives us a heap of useful information, but all we actually
            # care about is the name of the respository that was updated. We
            # feed this through to our consumer which then updates our checked
            # out copy of that repository *if* we have it present.
            #
            # Because we only pull repositories that we already have configured
            # in r10k, this webhook is secure to have public - any attempts to
            # have us pull other modules will just get discarded.

            github_event = json.loads(event['body'])

            push_event = {
                'repo_name': github_event['repository']['name'],
                'repo_url': github_event['repository']['url'],
                'user': github_event['pusher']['email']
            }

            body = '{"status": "success", "message": "Recieved webhook from Github for repository '+ push_event['repo_name'] +' by user '+ push_event['user'] +'}'
            statuscode = 200
        else:
            body = '{"status": "success", "message": "Ignored unsupported webhook event type: ' + event['headers']['X-GitHub-Event'] + '"}'
            statuscode = 200
    else:
        body = '{"status": "failed", "message": "Not a valid GitHub webhook event."}'
        statuscode = 400


    # Advise the requester
    response = {
        "statusCode": statuscode,
        "body": body
    }

    return response
