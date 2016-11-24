# This function provides all the webhook functionality. It takes the data from
# the POST from Github, parses it to find an event we care about and if it's
# valid, pushes a message to the SNS topic. If the topic does not exist, the
# Lambda creates it.
#

import json
import os
import boto3

def webhook(event, context):

    # All the data we need is provided inside the event object.

    if event['headers']['X-GitHub-Event']:
        # Post is a github event. We only care about certain types of these.
        print "Recieved event from Github"

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

            print "Event type is a push event."
            github_event = json.loads(event['body'])

            # Warning: This push event data is unfiltered, so it must be
            # properly validated if it's used in a shell CLI or inside a DB.
            push_event = {
                'repo_name': github_event['repository']['name'],
                'repo_url': github_event['repository']['url'],
                'user': github_event['pusher']['email']
            }

            # Connect to the SNS topic. We know the topic lives in our region
            # and account, but we need to get the name of this lambda and the
            # stage from Environments which has been loaded in by Serverless.
            print "Connecting to SNS and sending event details..."

            print "Using SNS topic: " + os.environ['SNSTOPIC']

            try:
                client = boto3.client('sns')
                snstopic = client.create_topic(
                    Name=os.environ['SNSTOPIC']
                )

                message = client.publish(
                    TopicArn=snstopic['TopicArn'],
                    Message=json.dumps(push_event)
                )

                print "Pushed message ID: " + message['MessageId']


                # Return OK to Github
                body = '{"status": "success", "message": "Recieved webhook from Github for repository '+ push_event['repo_name'] +' by user '+ push_event['user'] +'}'
                statuscode = 200

            except Exception as e:
                print e
                body = '{"status": "failed", "message": "Unable to deliver webhook event to SNS."}'
                statuscode = 500

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
