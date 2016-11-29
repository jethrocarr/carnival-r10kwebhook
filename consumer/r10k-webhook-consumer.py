#!/usr/bin/env python
#
# The r10k webhook consumer python program subscribes to an SNS topic and when
# a message is recieved, it instructs r10k to deploy the latest version of that
# module.
#
# This script is relatively simple, we rely on the OS service manager (eg
# systemd) to re-launch the process upon unexpected termination.
#
#
#   Copyright (c) 2016 Sailthru, Inc., https://www.sailthru.com/
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

import os
import re
import boto3
import socket
import json

print "Launching r10k webhook consumer..."

# Get configuration from envirommentals or generate some sensible defaults.
try:
    cfg_sns_topic = os.environ['SNSTOPIC']
except KeyError, e:
    cfg_sns_topic = 'r10k-webhook-staging'

try:
    cfg_sqs_queue = os.environ['SQSQUEUE']
except KeyError, e:
    cfg_sqs_queue = cfg_sns_topic + '-' + socket.gethostname()

try:
    cfg_aws_region = os.environ['AWS_REGION']
except KeyError, e:
    cfg_aws_region = 'us-east-1'

print "Using SNS topic: " + cfg_sns_topic
print "Using SQS queue: " + cfg_sqs_queue
print "Using AWS region: " + cfg_aws_region


# Setup the SQS queue and subscribe to SNS
client_sqs = boto3.client('sqs', region_name=cfg_aws_region)
client_sns = boto3.client('sns', region_name=cfg_aws_region)

sqs_queue = client_sqs.create_queue(
    QueueName=cfg_sqs_queue,
    Attributes={
        'ReceiveMessageWaitTimeSeconds': '20', # Long polling \m/
        'VisibilityTimeout': '1800' # Give r10k up to 30mins to complete.
    }
)

sqs_queue_attributes = client_sqs.get_queue_attributes(
    QueueUrl=sqs_queue['QueueUrl'],
    AttributeNames=['QueueArn'],
)

# So this is ugly, but basically boto3 offers no way of getting the ARN of the
# SNS topic from it's name... so we generate it ourselves. Only other option is
# to grant list all topics, but that exposes more information that we'd like
# from a security perspective
sns_arn = re.sub(r':sqs:', ':sns:', sqs_queue_attributes['Attributes']['QueueArn'])
sns_arn = re.sub(r':[A-Za-z0-9\-]*$', ":" + cfg_sns_topic, sns_arn)

print "Subcribing SQS queue (" + sqs_queue_attributes['Attributes']['QueueArn'] + ") to SNS topic ("+ sns_arn +")"
client_sns.subscribe(
    TopicArn=sns_arn,
    Protocol='sqs',
    Endpoint=sqs_queue_attributes['Attributes']['QueueArn']
)

print "Attaching policy to SQS allowing access from SNS"
client_sqs.set_queue_attributes(
    QueueUrl=sqs_queue['QueueUrl'],
    Attributes={
        'Policy': '{"Version": "2012-10-17", "Id": "SNStoSQS", "Statement": [ { "Sid":"rule1", "Effect": "Allow", "Principal": "*", "Action": "sqs:*", "Resource": "'+ sqs_queue_attributes['Attributes']['QueueArn'] +'", "Condition" : { "ArnEquals" : { "aws:SourceArn":"'+ sns_arn +'" } } } ] }'
    }
)


# Long poll for messages. This means we open one connection to SQS every 20
# seconds, but return immediately if a message arrives.
while (True):
    print "Checking for new SQS message (long-poll)..."

    message_response = client_sqs.receive_message(
        QueueUrl=sqs_queue['QueueUrl'],
        MaxNumberOfMessages=1
    )

    try:
        for message in message_response['Messages']:
            print "Recieved message ID: "+ message["MessageId"]

            # Warning: This message data must be validated when consumed, since
            # we can't trust the legitimacy of the information.
            message_body = json.loads(message['Body'])
            push_event = json.loads(message_body['Message'])
            print push_event

            # Extract (probable) module name from message. This works on the
            # the (common) but assumed convention that:
            #
            # 1. The module name matches the repo suffix (eg module "soe" is
            #    stored in repo "myorg/puppet-soe").
            # 2. Dash is used as a seporator between org and module.
            # 3. The enviromment module is simply a module called either
            #    "puppet", or "environment".

            module_name = push_event["repo_name"].split("-")[-1]
            print "Module name is: " + module_name

            if module_name == 'puppet' or module_name == 'environment' or push_event["repo_name"] == 'puppet':
                # Perform full r10k run.
                print "Performing FULL/HEAVY r10k run for environment module update..."
                os.system("r10k deploy environment -p --verbose info")
            else:
                # Ensure the module name is a word and not some nasty shell
                # injection :-)
                if re.search(r"^[A-Za-z0-9]*$", module_name):
                    # Perform module-specific run. Note that we get no information
                    # from r10k on whether or not this actually works :-/
                    print "Performing SINGLE MODULE r10k run..."
                    os.system("r10k deploy module "+ module_name +" --verbose info")
                else:
                    print "Invalid module name, unable to process: " + module_name

            # Delete the message after successful processing.
            client_sqs.delete_message(
                QueueUrl=sqs_queue['QueueUrl'],
                ReceiptHandle=message['ReceiptHandle']
            )
    except KeyError, e:
        print "No new message"
