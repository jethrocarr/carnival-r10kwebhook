# Carnival r10k Webhook

This repository provides a webhook for triggers r10k updates on servers when
a change is pushed to the Github repository.

# Features

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


# Webhook Lambda

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


# r10k Event Agent (Consumer)
