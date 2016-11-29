# Carnival r10k Webhook

This repository provides a webhook for triggers r10k updates on servers when
a change is pushed to the Github repository.

## Features

* Provides an AWS Lambda (using Serverless Framework) which collects webhook
  events from Github and turns them into a message that gets pushed to SNS.

* Provides an SNS consumer that creates an SQS queue (if one does not already
  exist) and subscribes it to the SNS topic used by the webhook Lambda. When
  new events come in, the program executes `r10k` deployment commands on the
  server.

* Supports independent or shared-state Puppet masters. If running Puppet masters
  on shared disk (eg EFS), the consumer should run on each server, but can share
  the queue. If each Puppet master is completely independent, the consumer must
  run on each server and create their own independent SQS queues. The queue name
  is configurable in the consumer.

* Because of the use of SQS/SNS, a single webhook can drive systems in multiple
  VPCs, or even multiple regions/accounts. This can simplify your Git repo
  configuration significantly, since it does not require a webhook to be added
  for each and every environment.

* Written in Python 2.7 and using Boto3 for optimal compatibility with AWS
  Lambda and popular GNU/Linux distributions.


## High Level Overview

![r10k-webhook-consumer-overview](https://cloud.githubusercontent.com/assets/23325523/20652726/8c4efce0-b563-11e6-9aa9-615bbdc8fc02.png)


# Webhook Lambda

The webhook Lambda listens to webhooks from GitHub and turns them into messages
on an SNS topic.

## Deployment

To deploy or update the webhook Lambda:

    cd webhook/
    ENVIRONMENT=staging
    serverless deploy --stage $ENVIRONMENT

The `serverless deploy` command will advise what endpoint is created in API
gateway, or you can request it at any time with `serverless info`.

Change `ENVIRONMENT` to suit, generally most sites will have a `staging` and
`production` convention to allow testing of new versions of the Lambda. Note
that this is *not* the same as Puppet environments, a single Lambda can handle
events for all Puppet environments.

The SNS topic used by the Lambda is automatically created in the same region as
the Lambda itself. The topic name is `r10k-webhook-$stage`.



## GitHub Configuration

When adding the webhook to Github, you should set the following fields:

| Field        | Value                                                      |
|--------------|------------------------------------------------------------|
| Payload URL  | The endpoint URL returned from `serverless deploy` command |
| Content Type | application/json                                           |
| Secret       | Unset                                                      |
| Verify SSL   | true (AWS API G/W provides us a valid cert)                |
| Which Events | Just the push event                                        |
| Active       | true                                                       |


## Testing

The following two examples simulate testing a ping and a push event:

    ENDPOINT=<as returned by `serverless info`>

    curl -i \
    -X POST \
    -H "X-GitHub-Event: ping" \
    --data "test" $ENDPOINT

    curl -i \
    -X POST \
    -H "X-GitHub-Event: push" \
    --data '{"repository": {"name": "test-repo", "url": "git://example-url/test-repo"}, "pusher": {"email": "example@example.com"} }' $ENDPOINT

GitHub makes testing very easy as well. Once a webhook is configured on a
project, you can view and debug the communications to/from the webhook by
clicking on the webhook entry in the web interface. This interface also permits
redelivery for testing purposes.

TODO: Review and implement unit testing for webhook.


# Server-Side Consumer

The consumer subscribes to the SNS topic and listens for event messages. When
one arrives, it parses the data and if the module is present in r10k, it checks
out the new version.

## Deployment

The consumer can be installed onto a systemd-enabled Linux system with:

    apt-get install python-boto3
    cp r10k-webhook-consumer.py /usr/local/bin/r10k-webhook-consumer
    cp r10k-webhook-consumer.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable r10k-webhook-consumer
    systemctl restart r10k-webhook-consumer

You may wish to change some of the default configuration, which can be done by
adjusting the environmentals inside the r10k-webhook-consumer.service file.

| Env Key          | Value                         | Details                                                      |
|------------------|-------------------------------|--------------------------------------------------------------|
| PYTHONUNBUFFERED | true                          | Ensures logging works in real-time when running as a daemon. |
| SNSTOPIC         | r10k-webhook-staging          | Name of the SNS topic to subscribe to.                       |
| SQSQUEUE         | r10k-webhook-staging-hostname | Name of the SQS queue to use. Self-generates unique names.   |
| AWS_REGION       | us-east-1                     | AWS region                                                   |


The server must have the following IAM role configured:

    {
    "Version": "2012-10-17",
    "Statement": [ {
        "Action": [
          "SNS:Subscribe"
        ],
        "Resource": "arn:aws:sns:us-east-1:123456:r10k-webhook-*",
        "Effect": "Allow"
      },
      {
        "Action": [
          "SQS:CreateQueue",
          "SQS:ReceiveMessage",
          "SQS:DeleteMessage",
          "SQS:GetQueueAttributes",
          "SQS:SetQueueAttributes",
          "SQS:AddPermission"
        ],
        "Resource": "arn:aws:sqs:us-east-1:123456:r10k-webhook-*",
        "Effect": "Allow"
      } ]
    }


## Testing

The easiest way to test is to copy the consumer to a server and execute the
command with environmentals. Make sure the server IAM roles have been
setup as per above information.


# Contributions

All contributions are welcome via Pull Requests including documentation fixes.


# License

    Copyright (c) 2016 Sailthru, Inc., https://www.sailthru.com/

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
